import datetime
from decimal import Decimal

from src.signals.backtest import BacktestResult, BacktestTrade


class TestBacktestTrade:
    def test_pnl_positive(self):
        trade = BacktestTrade(
            ticker="TEST",
            entry_date=datetime.date(2024, 1, 1),
            entry_price=Decimal("100.00"),
            exit_date=datetime.date(2024, 2, 1),
            exit_price=Decimal("110.00"),
        )
        assert trade.pnl_pct == 10.0

    def test_pnl_negative(self):
        trade = BacktestTrade(
            ticker="TEST",
            entry_date=datetime.date(2024, 1, 1),
            entry_price=Decimal("100.00"),
            exit_date=datetime.date(2024, 2, 1),
            exit_price=Decimal("90.00"),
        )
        assert trade.pnl_pct == -10.0

    def test_pnl_none_when_open(self):
        trade = BacktestTrade(
            ticker="TEST",
            entry_date=datetime.date(2024, 1, 1),
            entry_price=Decimal("100.00"),
        )
        assert trade.pnl_pct is None


class TestBacktestResult:
    def _make_result(self, pnl_pcts: list[float]) -> BacktestResult:
        trades = []
        for pnl in pnl_pcts:
            entry = Decimal("100.00")
            exit_p = entry * (1 + Decimal(str(pnl / 100)))
            trades.append(BacktestTrade(
                ticker="TEST",
                entry_date=datetime.date(2024, 1, 1),
                entry_price=entry,
                exit_date=datetime.date(2024, 2, 1),
                exit_price=exit_p,
            ))
        return BacktestResult(
            ticker="TEST",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
            trades=trades,
        )

    def test_win_rate(self):
        result = self._make_result([10.0, -5.0, 8.0, -3.0])
        assert result.win_rate == 0.5

    def test_total_return(self):
        result = self._make_result([10.0, 10.0])
        assert result.total_return_pct > 20.0  # compounding

    def test_empty_result(self):
        result = BacktestResult(
            ticker="TEST",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        assert result.total_trades == 0
        assert result.win_rate is None
        assert result.total_return_pct == 0.0
        assert result.max_drawdown_pct == 0.0
