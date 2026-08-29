"""Intraday executor — manages multiple buy/sell cycles per day per stock."""
from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from pathlib import Path

from src.alerts.notifier import AlertManager
from src.data.company_registry import CompanyInfo
from src.data.database import get_connection, save_signal, save_trade
from src.market.data_feed import fetch_history, get_trend_signal
from src.settings import PortfolioSettings
from src.signals.intraday import (
    IntradaySignal,
    IntradayState,
    compute_natal_score_for_day,
    generate_intraday_signal,
)
from src.signals.generator import SignalDirection
from src.trading.broker import Broker

logger = logging.getLogger(__name__)


class IntradayExecutor:
    def __init__(
        self,
        broker: Broker,
        settings: PortfolioSettings,
        db_path: Path | str,
        alert_manager: AlertManager | None = None,
        max_trades_per_stock: int = 8,
        sunrise_hour: float = 6.0,
    ) -> None:
        self.broker = broker
        self.settings = settings
        self.db_path = Path(db_path)
        self.alerts = alert_manager
        self.max_trades = max_trades_per_stock
        self.sunrise_hour = sunrise_hour
        self._states: dict[str, IntradayState] = {}
        self._natal_scores: dict[str, object] = {}
        self._daily_pnl: float = 0.0

    def init_day(self, companies: dict[str, CompanyInfo], date: datetime.date) -> None:
        logger.info("Initializing intraday session for %d stocks", len(companies))
        self._states.clear()
        self._natal_scores.clear()
        self._daily_pnl = 0.0

        positions = self.broker.get_positions()

        for ticker, company in companies.items():
            try:
                natal = compute_natal_score_for_day(company, date)
                self._natal_scores[ticker] = natal

                self._states[ticker] = IntradayState(
                    ticker=ticker,
                    has_position=ticker in positions,
                    entry_price=float(positions[ticker].avg_entry_price) if ticker in positions else 0.0,
                )
            except Exception:
                logger.error("Failed to compute natal for %s", ticker, exc_info=True)

        logger.info(
            "Day initialized: %d stocks ready, %d with existing positions",
            len(self._natal_scores),
            sum(1 for s in self._states.values() if s.has_position),
        )

    def tick(
        self,
        companies: dict[str, CompanyInfo],
        dt: datetime.datetime,
    ) -> list[dict]:
        """Run one hourly tick. Returns list of actions taken."""
        actions = []

        for ticker, company in companies.items():
            natal = self._natal_scores.get(ticker)
            if natal is None:
                continue

            state = self._states.get(ticker)
            if state is None:
                continue

            # Get short-term trend if possible
            trend = 0
            try:
                df = fetch_history(ticker, dt.date() - datetime.timedelta(days=5), dt.date())
                if not df.empty:
                    trend = get_trend_signal(df, short_window=5, long_window=15)
            except Exception:
                pass

            signal = generate_intraday_signal(
                company, dt, natal,
                trend_signal=trend,
                has_position=state.has_position,
                sunrise_hour=self.sunrise_hour,
                max_trades_per_day=self.max_trades,
                trades_today=state.trades_today,
            )

            action = self._act_on_signal(signal, state, dt)
            if action:
                actions.append(action)

        return actions

    def _act_on_signal(
        self,
        signal: IntradaySignal,
        state: IntradayState,
        dt: datetime.datetime,
    ) -> dict | None:
        ticker = signal.ticker

        if signal.direction == SignalDirection.HOLD:
            return None

        price = self.broker.get_current_price(ticker)
        if price is None:
            return None

        if signal.direction == SignalDirection.BUY and not state.has_position:
            account = self.broker.get_account()
            max_per_trade = float(account.equity) * self.settings.max_position_pct
            shares = int(Decimal(str(max_per_trade)) / price)
            if shares <= 0:
                return None

            result = self.broker.submit_order(ticker, shares, "buy")
            if hasattr(self.broker, "wait_for_fill"):
                result = self.broker.wait_for_fill(result.order_id)

            if result.is_filled:
                fill_price = float(result.filled_avg_price or price)
                state.has_position = True
                state.entry_price = fill_price
                state.entry_time = dt
                state.trades_today += 1

                self._persist_trade(ticker, "buy", result.filled_qty, Decimal(str(fill_price)), dt)

                if self.alerts:
                    self.alerts.trade_executed_alert(ticker, "BUY", result.filled_qty, fill_price)

                logger.info(
                    "[INTRADAY] BUY %s %d @ %.2f | hora=%s | score=%.1f | %s",
                    ticker, result.filled_qty, fill_price,
                    signal.hora_ruler.name, signal.combined_score, signal.reason,
                )
                return {
                    "action": "BUY", "ticker": ticker, "shares": result.filled_qty,
                    "price": fill_price, "hora": signal.hora_ruler.name,
                    "reason": signal.reason, "confidence": signal.confidence,
                }

        elif signal.direction == SignalDirection.SELL and state.has_position:
            positions = self.broker.get_positions()
            pos = positions.get(ticker)
            if pos is None:
                state.has_position = False
                return None

            result = self.broker.submit_order(ticker, pos.qty, "sell")
            if hasattr(self.broker, "wait_for_fill"):
                result = self.broker.wait_for_fill(result.order_id)

            if result.is_filled:
                fill_price = float(result.filled_avg_price or price)
                pnl = (fill_price - state.entry_price) / state.entry_price * 100
                self._daily_pnl += pnl
                state.has_position = False
                state.pnl_today += pnl
                state.trades_today += 1

                self._persist_trade(
                    ticker, "sell", result.filled_qty, Decimal(str(fill_price)), dt,
                    entry_price=Decimal(str(state.entry_price)), pnl_pct=pnl,
                )

                if self.alerts:
                    self.alerts.trade_executed_alert(ticker, "SELL", result.filled_qty, fill_price)

                logger.info(
                    "[INTRADAY] SELL %s %d @ %.2f | pnl=%.2f%% | hora=%s | %s",
                    ticker, result.filled_qty, fill_price, pnl,
                    signal.hora_ruler.name, signal.reason,
                )
                return {
                    "action": "SELL", "ticker": ticker, "shares": result.filled_qty,
                    "price": fill_price, "pnl_pct": pnl,
                    "hora": signal.hora_ruler.name, "reason": signal.reason,
                }

        return None

    def close_all_positions(self, dt: datetime.datetime) -> list[dict]:
        """End-of-day: close any remaining open positions."""
        actions = []
        positions = self.broker.get_positions()

        for ticker, pos in positions.items():
            state = self._states.get(ticker)
            if state is None or not state.has_position:
                continue

            price = Decimal(str(pos.current_price))
            result = self.broker.submit_order(ticker, pos.qty, "sell")
            if hasattr(self.broker, "wait_for_fill"):
                result = self.broker.wait_for_fill(result.order_id)

            if result.is_filled:
                fill_price = float(result.filled_avg_price or price)
                pnl = (fill_price - state.entry_price) / state.entry_price * 100
                self._daily_pnl += pnl
                state.has_position = False
                state.pnl_today += pnl

                self._persist_trade(
                    ticker, "sell", result.filled_qty, Decimal(str(fill_price)), dt,
                    entry_price=Decimal(str(state.entry_price)), pnl_pct=pnl,
                )

                logger.info("[EOD] Closed %s %d @ %.2f | pnl=%.2f%%", ticker, result.filled_qty, fill_price, pnl)
                actions.append({
                    "action": "EOD_SELL", "ticker": ticker,
                    "price": fill_price, "pnl_pct": pnl,
                })

        return actions

    def get_day_summary(self) -> dict:
        total_trades = sum(s.trades_today for s in self._states.values())
        traded_stocks = [s.ticker for s in self._states.values() if s.trades_today > 0]
        per_stock_pnl = {s.ticker: s.pnl_today for s in self._states.values() if s.trades_today > 0}

        return {
            "total_trades": total_trades,
            "stocks_traded": traded_stocks,
            "daily_pnl_pct": self._daily_pnl,
            "per_stock_pnl": per_stock_pnl,
        }

    def _persist_trade(
        self, ticker: str, side: str, qty: int, price: Decimal,
        dt: datetime.datetime,
        entry_price: Decimal | None = None, pnl_pct: float | None = None,
    ) -> None:
        try:
            with get_connection(self.db_path) as conn:
                save_trade(
                    conn, ticker, dt.date(), price, qty, side=side,
                    exit_date=dt.date() if side == "sell" else None,
                    exit_price=price if side == "sell" else None,
                    pnl_pct=pnl_pct,
                )
        except Exception:
            logger.error("Failed to persist intraday trade for %s", ticker, exc_info=True)
