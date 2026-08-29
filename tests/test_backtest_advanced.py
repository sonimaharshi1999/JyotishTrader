import datetime
from decimal import Decimal
from unittest.mock import patch

from src.signals.backtest import BacktestResult, BacktestTrade
from src.signals.backtest_advanced import (
    compute_risk_metrics, run_monte_carlo,
    compare_to_benchmark, format_risk_report, format_monte_carlo_report,
)


def _make_result(pnl_pcts: list[float]) -> BacktestResult:
    trades = []
    for i, pnl in enumerate(pnl_pcts):
        entry = Decimal("100.00")
        exit_p = entry * (1 + Decimal(str(pnl / 100)))
        trades.append(BacktestTrade(
            ticker="TEST",
            entry_date=datetime.date(2024, 1, 1) + datetime.timedelta(days=i * 30),
            entry_price=entry,
            exit_date=datetime.date(2024, 1, 15) + datetime.timedelta(days=i * 30),
            exit_price=exit_p,
        ))
    return BacktestResult(
        ticker="TEST",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
        trades=trades,
    )


class TestRiskMetrics:
    def test_basic_metrics(self):
        result = _make_result([10.0, -5.0, 8.0, -3.0, 12.0])
        metrics = compute_risk_metrics(result)
        assert metrics.total_trades == 5
        assert metrics.win_rate > 0
        assert metrics.total_return_pct != 0

    def test_empty(self):
        result = BacktestResult(
            ticker="TEST",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        metrics = compute_risk_metrics(result)
        assert metrics.total_trades == 0
        assert metrics.sharpe_ratio == 0


class TestMonteCarlo:
    def test_runs(self):
        result = _make_result([10.0, -5.0, 8.0, -3.0, 12.0])
        mc = run_monte_carlo(result, num_simulations=100)
        assert mc.num_simulations == 100
        assert mc.percentile_5 <= mc.median_return_pct <= mc.percentile_95

    def test_empty(self):
        result = BacktestResult(
            ticker="TEST",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        mc = run_monte_carlo(result)
        assert mc.median_return_pct == 0


class TestBenchmark:
    @patch("src.signals.backtest_advanced.fetch_history")
    def test_comparison(self, mock_fetch):
        import pandas as pd
        import numpy as np
        dates = pd.date_range("2024-01-01", periods=252)
        df = pd.DataFrame({"Close": np.linspace(100, 110, 252)}, index=dates)
        mock_fetch.return_value = df

        result = _make_result([10.0, 5.0])
        comp = compare_to_benchmark(result)
        assert comp.benchmark_ticker == "SPY"
        assert comp.benchmark_return_pct > 0


class TestFormatting:
    def test_risk_report(self):
        result = _make_result([10.0, -5.0])
        metrics = compute_risk_metrics(result)
        report = format_risk_report(metrics)
        assert "Sharpe" in report

    def test_mc_report(self):
        result = _make_result([10.0, -5.0])
        mc = run_monte_carlo(result, num_simulations=50)
        report = format_monte_carlo_report(mc)
        assert "Monte Carlo" in report
