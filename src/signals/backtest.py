from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from src.data.company_registry import CompanyInfo
from src.market.data_feed import fetch_history
from src.signals.filters import apply_filters
from src.signals.generator import SignalDirection, generate_signal

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    ticker: str
    entry_date: datetime.date
    entry_price: Decimal
    exit_date: datetime.date | None = None
    exit_price: Decimal | None = None

    @property
    def pnl_pct(self) -> float | None:
        if self.exit_price is None:
            return None
        return float((self.exit_price - self.entry_price) / self.entry_price * 100)


@dataclass
class BacktestResult:
    ticker: str
    start_date: datetime.date
    end_date: datetime.date
    trades: list[BacktestTrade] = field(default_factory=list)
    initial_capital: Decimal = Decimal("100000")

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def closed_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if t.exit_price is not None]

    @property
    def win_rate(self) -> float | None:
        closed = self.closed_trades
        if not closed:
            return None
        winners = sum(1 for t in closed if t.pnl_pct and t.pnl_pct > 0)
        return winners / len(closed)

    @property
    def total_return_pct(self) -> float:
        capital = float(self.initial_capital)
        for t in self.closed_trades:
            if t.pnl_pct is not None:
                capital *= (1 + t.pnl_pct / 100)
        return (capital - float(self.initial_capital)) / float(self.initial_capital) * 100

    @property
    def max_drawdown_pct(self) -> float:
        if not self.closed_trades:
            return 0.0
        capital = float(self.initial_capital)
        peak = capital
        max_dd = 0.0
        for t in self.closed_trades:
            if t.pnl_pct is not None:
                capital *= (1 + t.pnl_pct / 100)
            peak = max(peak, capital)
            dd = (peak - capital) / peak * 100
            max_dd = max(max_dd, dd)
        return max_dd


def run_backtest(
    company: CompanyInfo,
    start: datetime.date,
    end: datetime.date,
    buy_threshold: float = 3.0,
    sell_threshold: float = -3.0,
    stop_loss_pct: float = 7.0,
) -> BacktestResult:
    df = fetch_history(company.ticker, start, end)
    if df.empty:
        logger.warning("No data for %s, returning empty backtest", company.ticker)
        return BacktestResult(ticker=company.ticker, start_date=start, end_date=end)

    result = BacktestResult(ticker=company.ticker, start_date=start, end_date=end)
    active_trade: BacktestTrade | None = None

    for row_date, row in df.iterrows():
        date = row_date.date() if hasattr(row_date, "date") else row_date
        close = Decimal(str(round(row["Close"], 2)))

        if active_trade is not None:
            drop = float((active_trade.entry_price - close) / active_trade.entry_price * 100)
            if drop >= stop_loss_pct:
                active_trade.exit_date = date
                active_trade.exit_price = close
                result.trades.append(active_trade)
                active_trade = None
                continue

        try:
            signal = generate_signal(
                company, date,
                buy_threshold=buy_threshold,
                sell_threshold=sell_threshold,
                require_trend_confirmation=False,
            )
            signal = apply_filters(signal)
        except Exception:
            logger.debug("Signal generation failed for %s on %s", company.ticker, date, exc_info=True)
            continue

        if signal.direction == SignalDirection.BUY and active_trade is None:
            active_trade = BacktestTrade(
                ticker=company.ticker,
                entry_date=date,
                entry_price=close,
            )
        elif signal.direction == SignalDirection.SELL and active_trade is not None:
            active_trade.exit_date = date
            active_trade.exit_price = close
            result.trades.append(active_trade)
            active_trade = None

    if active_trade is not None:
        last_date = df.index[-1]
        last_close = Decimal(str(round(df["Close"].iloc[-1], 2)))
        active_trade.exit_date = last_date.date() if hasattr(last_date, "date") else last_date
        active_trade.exit_price = last_close
        result.trades.append(active_trade)

    return result


def format_backtest_report(result: BacktestResult) -> str:
    lines = [
        f"=== Backtest: {result.ticker} ===",
        f"Period: {result.start_date} to {result.end_date}",
        f"Total trades: {result.total_trades}",
        f"Win rate: {result.win_rate:.1%}" if result.win_rate is not None else "Win rate: N/A",
        f"Total return: {result.total_return_pct:.2f}%",
        f"Max drawdown: {result.max_drawdown_pct:.2f}%",
        "",
        "--- Trades ---",
    ]
    for t in result.closed_trades:
        pnl = f"{t.pnl_pct:+.2f}%" if t.pnl_pct is not None else "open"
        lines.append(f"  {t.entry_date} -> {t.exit_date}  entry={t.entry_price} exit={t.exit_price} pnl={pnl}")
    return "\n".join(lines)
