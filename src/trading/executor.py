from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from pathlib import Path

from src.alerts.notifier import AlertManager
from src.data.company_registry import CompanyInfo
from src.data.database import get_connection, save_signal, save_trade, save_portfolio_snapshot
from src.market.data_feed import fetch_history
from src.settings import PortfolioSettings
from src.signals.generator import SignalDirection, TradingSignal
from src.trading.broker import Broker, BrokerPosition, OrderResult
from src.trading.kelly import compute_kelly_from_trades, kelly_position_size
from src.trading.portfolio import Portfolio, calculate_position_size
from src.trading.risk import check_max_exposure, check_position_size_limit
from src.trading.sector_limits import check_sector_concentration
from src.trading.trailing_stop import TrailingStop
from src.trading.volatility_sizing import compute_atr, volatility_adjusted_shares

logger = logging.getLogger(__name__)


class TradingExecutor:
    def __init__(
        self,
        broker: Broker,
        settings: PortfolioSettings,
        db_path: Path | str,
        alert_manager: AlertManager | None = None,
        company_registry: dict[str, CompanyInfo] | None = None,
    ) -> None:
        self.broker = broker
        self.settings = settings
        self.db_path = Path(db_path)
        self.alerts = alert_manager
        self.company_registry = company_registry or {}
        self.trailing_stops: dict[str, TrailingStop] = {}
        self._trade_pnls: list[float] = []

    def sync_positions(self) -> dict[str, BrokerPosition]:
        positions = self.broker.get_positions()
        for ticker, pos in positions.items():
            if ticker not in self.trailing_stops:
                self.trailing_stops[ticker] = TrailingStop.create(
                    ticker, pos.avg_entry_price, self.settings.trailing_stop_pct,
                )
            else:
                self.trailing_stops[ticker] = self.trailing_stops[ticker].update(pos.current_price)
        expired = [t for t in self.trailing_stops if t not in positions]
        for t in expired:
            del self.trailing_stops[t]
        return positions

    def check_trailing_stops(self) -> list[OrderResult]:
        results: list[OrderResult] = []
        positions = self.broker.get_positions()

        for ticker, ts in list(self.trailing_stops.items()):
            pos = positions.get(ticker)
            if pos is None:
                continue

            ts = ts.update(pos.current_price)
            self.trailing_stops[ticker] = ts

            if ts.is_triggered(pos.current_price):
                logger.warning(
                    "%s: trailing stop triggered at $%.2f (stop=$%.2f, high=$%.2f)",
                    ticker, float(pos.current_price), float(ts.stop_price), float(ts.highest_price),
                )
                result = self.broker.submit_order(ticker, pos.qty, "sell")
                if hasattr(self.broker, "wait_for_fill"):
                    result = self.broker.wait_for_fill(result.order_id)

                if result.is_filled:
                    pnl = float((pos.current_price - pos.avg_entry_price) / pos.avg_entry_price * 100)
                    self._record_trade(
                        ticker, "sell", pos.qty, pos.current_price,
                        entry_price=pos.avg_entry_price, pnl_pct=pnl,
                    )
                    if self.alerts:
                        self.alerts.stop_loss_alert(
                            ticker, float(pos.avg_entry_price), float(pos.current_price),
                        )
                    del self.trailing_stops[ticker]

                results.append(result)
        return results

    def execute_signal(
        self,
        signal: TradingSignal,
        current_price: Decimal,
    ) -> OrderResult | None:
        ticker = signal.ticker

        self._persist_signal(signal)

        if signal.direction == SignalDirection.HOLD:
            return None

        if signal.direction == SignalDirection.BUY:
            return self._execute_buy(signal, current_price)
        elif signal.direction == SignalDirection.SELL:
            return self._execute_sell(signal, current_price)
        return None

    def _execute_buy(self, signal: TradingSignal, price: Decimal) -> OrderResult | None:
        ticker = signal.ticker
        positions = self.broker.get_positions()

        if ticker in positions:
            logger.info("%s: already have position, skipping BUY", ticker)
            return None

        account = self.broker.get_account()
        portfolio = Portfolio(cash=account.cash)
        portfolio.positions = {}
        for t, p in positions.items():
            from src.trading.portfolio import Position
            portfolio.positions[t] = Position(
                ticker=t, shares=p.qty,
                entry_price=p.avg_entry_price,
                entry_date=datetime.date.today(),
            )

        if not check_max_exposure(portfolio, self.settings.max_exposure_pct):
            return None

        proposed_shares = self._compute_position_size(portfolio, price, ticker)
        if proposed_shares <= 0:
            logger.info("%s: position size is 0", ticker)
            return None

        proposed_cost = price * proposed_shares
        if not check_position_size_limit(portfolio, proposed_cost, self.settings.max_position_pct):
            return None

        if not check_sector_concentration(
            portfolio, self.company_registry, ticker,
            proposed_cost, self.settings.max_sector_pct,
        ):
            return None

        logger.info(
            "%s: BUY %d shares @ $%.2f (composite=%.2f, confidence=%s)",
            ticker, proposed_shares, float(price), signal.composite_score,
            getattr(signal, "confidence", "N/A"),
        )
        result = self.broker.submit_order(ticker, proposed_shares, "buy")
        if hasattr(self.broker, "wait_for_fill"):
            result = self.broker.wait_for_fill(result.order_id)

        if result.is_filled:
            fill_price = result.filled_avg_price or price
            self.trailing_stops[ticker] = TrailingStop.create(
                ticker, fill_price, self.settings.trailing_stop_pct,
            )
            self._record_trade(ticker, "buy", result.filled_qty, fill_price)
            if self.alerts:
                self.alerts.trade_executed_alert(
                    ticker, "BUY", result.filled_qty, float(fill_price),
                )

        return result

    def _execute_sell(self, signal: TradingSignal, price: Decimal) -> OrderResult | None:
        ticker = signal.ticker
        positions = self.broker.get_positions()

        pos = positions.get(ticker)
        if pos is None:
            logger.info("%s: no position to sell", ticker)
            return None

        logger.info(
            "%s: SELL %d shares @ $%.2f (composite=%.2f)",
            ticker, pos.qty, float(price), signal.composite_score,
        )
        result = self.broker.submit_order(ticker, pos.qty, "sell")
        if hasattr(self.broker, "wait_for_fill"):
            result = self.broker.wait_for_fill(result.order_id)

        if result.is_filled:
            fill_price = result.filled_avg_price or price
            pnl = float((fill_price - pos.avg_entry_price) / pos.avg_entry_price * 100)
            self._trade_pnls.append(pnl)
            self._record_trade(
                ticker, "sell", result.filled_qty, fill_price,
                entry_price=pos.avg_entry_price, pnl_pct=pnl,
            )
            if ticker in self.trailing_stops:
                del self.trailing_stops[ticker]
            if self.alerts:
                self.alerts.trade_executed_alert(
                    ticker, "SELL", result.filled_qty, float(fill_price),
                )

        return result

    def _compute_position_size(
        self, portfolio: Portfolio, price: Decimal, ticker: str,
    ) -> int:
        if self.settings.use_kelly_sizing and len(self._trade_pnls) >= 10:
            kelly = compute_kelly_from_trades(self._trade_pnls)
            shares = kelly_position_size(portfolio, price, kelly, self.settings.max_position_pct)
            if shares > 0:
                return shares

        if self.settings.use_volatility_sizing:
            try:
                end = datetime.date.today()
                start = end - datetime.timedelta(days=30)
                df = fetch_history(ticker, start, end)
                if not df.empty:
                    atr = compute_atr(df)
                    if atr > 0:
                        return volatility_adjusted_shares(
                            portfolio, price, atr,
                            self.settings.max_position_pct,
                            self.settings.risk_per_trade_pct,
                        )
            except Exception:
                logger.debug("Volatility sizing failed for %s, using default", ticker, exc_info=True)

        return calculate_position_size(portfolio, price, self.settings.max_position_pct)

    def _persist_signal(self, signal: TradingSignal) -> None:
        try:
            with get_connection(self.db_path) as conn:
                save_signal(
                    conn, signal.ticker, signal.date, signal.direction.value,
                    signal.astro_score, signal.trend_signal, signal.composite_score,
                    signal.dominant_aspect,
                    confidence=getattr(signal, "confidence", None),
                )
        except Exception:
            logger.error("Failed to persist signal for %s", signal.ticker, exc_info=True)

    def _record_trade(
        self, ticker: str, side: str, qty: int, price: Decimal,
        entry_price: Decimal | None = None, pnl_pct: float | None = None,
    ) -> None:
        try:
            with get_connection(self.db_path) as conn:
                save_trade(
                    conn, ticker, datetime.date.today(), price, qty,
                    exit_date=datetime.date.today() if side == "sell" else None,
                    exit_price=price if side == "sell" else None,
                    pnl_pct=pnl_pct,
                )
        except Exception:
            logger.error("Failed to record trade for %s", ticker, exc_info=True)

    def snapshot_portfolio(self) -> None:
        try:
            account = self.broker.get_account()
            positions = self.broker.get_positions()
            pos_dict = {
                t: {"qty": p.qty, "price": str(p.current_price)}
                for t, p in positions.items()
            }
            with get_connection(self.db_path) as conn:
                save_portfolio_snapshot(
                    conn, datetime.date.today(),
                    account.cash, account.equity,
                    float(sum(p.market_value for p in positions.values()) / account.equity)
                    if account.equity > 0 else 0.0,
                    pos_dict,
                )
        except Exception:
            logger.error("Failed to snapshot portfolio", exc_info=True)
