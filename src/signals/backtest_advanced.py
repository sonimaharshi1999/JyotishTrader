from __future__ import annotations

import datetime
import math
import random
from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np
import pandas as pd

from src.market.data_feed import fetch_history
from src.signals.backtest import BacktestResult, BacktestTrade


@dataclass(frozen=True)
class RiskMetrics:
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    avg_trade_return_pct: float
    avg_holding_days: float
    total_trades: int


@dataclass(frozen=True)
class BenchmarkComparison:
    strategy_return_pct: float
    benchmark_return_pct: float
    alpha_pct: float
    benchmark_ticker: str
    period_start: datetime.date
    period_end: datetime.date


@dataclass(frozen=True)
class MonteCarloResult:
    median_return_pct: float
    mean_return_pct: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    prob_profitable: float
    num_simulations: int


@dataclass(frozen=True)
class WalkForwardResult:
    windows: list[WalkForwardWindow]
    avg_oos_return: float
    avg_is_return: float
    degradation_pct: float


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: datetime.date
    train_end: datetime.date
    test_start: datetime.date
    test_end: datetime.date
    in_sample_return: float
    out_of_sample_return: float
    optimal_buy_threshold: float
    optimal_sell_threshold: float


def compute_risk_metrics(
    result: BacktestResult,
    risk_free_rate: float = 0.04,
) -> RiskMetrics:
    closed = result.closed_trades
    if not closed:
        return RiskMetrics(
            total_return_pct=0, annualized_return_pct=0,
            sharpe_ratio=0, sortino_ratio=0, max_drawdown_pct=0,
            calmar_ratio=0, win_rate=0, profit_factor=0,
            avg_trade_return_pct=0, avg_holding_days=0, total_trades=0,
        )

    returns = [t.pnl_pct / 100 for t in closed if t.pnl_pct is not None]
    if not returns:
        return RiskMetrics(
            total_return_pct=0, annualized_return_pct=0,
            sharpe_ratio=0, sortino_ratio=0, max_drawdown_pct=0,
            calmar_ratio=0, win_rate=0, profit_factor=0,
            avg_trade_return_pct=0, avg_holding_days=0, total_trades=0,
        )

    total_days = (result.end_date - result.start_date).days
    years = total_days / 365.25 if total_days > 0 else 1

    cumulative = 1.0
    for r in returns:
        cumulative *= (1 + r)
    total_return = (cumulative - 1) * 100
    annualized = ((cumulative ** (1 / years)) - 1) * 100

    arr = np.array(returns)
    mean_ret = arr.mean()
    std_ret = arr.std()
    trades_per_year = len(returns) / years

    sharpe = 0.0
    if std_ret > 0:
        excess = mean_ret - risk_free_rate / trades_per_year
        sharpe = excess / std_ret * math.sqrt(trades_per_year)

    downside = arr[arr < 0]
    downside_std = downside.std() if len(downside) > 0 else 0.0
    sortino = 0.0
    if downside_std > 0:
        excess = mean_ret - risk_free_rate / trades_per_year
        sortino = excess / downside_std * math.sqrt(trades_per_year)

    max_dd = result.max_drawdown_pct
    calmar = annualized / max_dd if max_dd > 0 else 0.0

    wins = [r for r in returns if r > 0]
    losses = [abs(r) for r in returns if r <= 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    holding_days = []
    for t in closed:
        if t.entry_date and t.exit_date:
            hd = (t.exit_date - t.entry_date).days
            holding_days.append(hd)
    avg_hold = sum(holding_days) / len(holding_days) if holding_days else 0

    return RiskMetrics(
        total_return_pct=total_return,
        annualized_return_pct=annualized,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown_pct=max_dd,
        calmar_ratio=calmar,
        win_rate=result.win_rate or 0,
        profit_factor=profit_factor,
        avg_trade_return_pct=float(mean_ret * 100),
        avg_holding_days=avg_hold,
        total_trades=len(closed),
    )


def compare_to_benchmark(
    result: BacktestResult,
    benchmark_ticker: str = "SPY",
) -> BenchmarkComparison:
    df = fetch_history(benchmark_ticker, result.start_date, result.end_date)
    bench_return = 0.0
    if not df.empty:
        bench_return = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100

    strategy_return = result.total_return_pct
    alpha = strategy_return - bench_return

    return BenchmarkComparison(
        strategy_return_pct=strategy_return,
        benchmark_return_pct=bench_return,
        alpha_pct=alpha,
        benchmark_ticker=benchmark_ticker,
        period_start=result.start_date,
        period_end=result.end_date,
    )


def run_monte_carlo(
    result: BacktestResult,
    num_simulations: int = 1000,
    seed: int | None = 42,
) -> MonteCarloResult:
    closed = result.closed_trades
    returns = [t.pnl_pct for t in closed if t.pnl_pct is not None]
    if not returns:
        return MonteCarloResult(
            median_return_pct=0, mean_return_pct=0,
            percentile_5=0, percentile_25=0,
            percentile_75=0, percentile_95=0,
            prob_profitable=0, num_simulations=num_simulations,
        )

    rng = random.Random(seed)
    simulation_returns = []

    for _ in range(num_simulations):
        shuffled = [rng.choice(returns) for _ in range(len(returns))]
        cumulative = 1.0
        for r in shuffled:
            cumulative *= (1 + r / 100)
        simulation_returns.append((cumulative - 1) * 100)

    arr = np.array(simulation_returns)
    profitable = sum(1 for r in simulation_returns if r > 0) / num_simulations

    return MonteCarloResult(
        median_return_pct=float(np.median(arr)),
        mean_return_pct=float(np.mean(arr)),
        percentile_5=float(np.percentile(arr, 5)),
        percentile_25=float(np.percentile(arr, 25)),
        percentile_75=float(np.percentile(arr, 75)),
        percentile_95=float(np.percentile(arr, 95)),
        prob_profitable=profitable,
        num_simulations=num_simulations,
    )


def run_walk_forward(
    run_backtest_fn,
    company,
    full_start: datetime.date,
    full_end: datetime.date,
    num_windows: int = 4,
    train_ratio: float = 0.7,
    threshold_range: tuple[float, float] = (1.0, 5.0),
    threshold_step: float = 0.5,
) -> WalkForwardResult:
    total_days = (full_end - full_start).days
    window_days = total_days // num_windows
    windows: list[WalkForwardWindow] = []

    for i in range(num_windows):
        window_start = full_start + datetime.timedelta(days=i * window_days)
        window_end = window_start + datetime.timedelta(days=window_days)
        split = window_start + datetime.timedelta(days=int(window_days * train_ratio))

        best_threshold = 3.0
        best_return = -999.0

        t = threshold_range[0]
        while t <= threshold_range[1]:
            try:
                r = run_backtest_fn(company, window_start, split, buy_threshold=t, sell_threshold=-t)
                ret = r.total_return_pct
                if ret > best_return:
                    best_return = ret
                    best_threshold = t
            except Exception:
                pass
            t += threshold_step

        try:
            oos_result = run_backtest_fn(
                company, split, window_end,
                buy_threshold=best_threshold, sell_threshold=-best_threshold,
            )
            oos_return = oos_result.total_return_pct
        except Exception:
            oos_return = 0.0

        windows.append(WalkForwardWindow(
            train_start=window_start,
            train_end=split,
            test_start=split,
            test_end=window_end,
            in_sample_return=best_return,
            out_of_sample_return=oos_return,
            optimal_buy_threshold=best_threshold,
            optimal_sell_threshold=-best_threshold,
        ))

    avg_is = sum(w.in_sample_return for w in windows) / len(windows) if windows else 0
    avg_oos = sum(w.out_of_sample_return for w in windows) / len(windows) if windows else 0
    degradation = ((avg_is - avg_oos) / abs(avg_is) * 100) if avg_is != 0 else 0

    return WalkForwardResult(
        windows=windows,
        avg_oos_return=avg_oos,
        avg_is_return=avg_is,
        degradation_pct=degradation,
    )


def format_risk_report(metrics: RiskMetrics, benchmark: BenchmarkComparison | None = None) -> str:
    lines = [
        "=== Risk Metrics ===",
        f"Total Return:      {metrics.total_return_pct:+.2f}%",
        f"Annualized Return: {metrics.annualized_return_pct:+.2f}%",
        f"Sharpe Ratio:      {metrics.sharpe_ratio:.2f}",
        f"Sortino Ratio:     {metrics.sortino_ratio:.2f}",
        f"Max Drawdown:      {metrics.max_drawdown_pct:.2f}%",
        f"Calmar Ratio:      {metrics.calmar_ratio:.2f}",
        f"Win Rate:          {metrics.win_rate:.1%}",
        f"Profit Factor:     {metrics.profit_factor:.2f}",
        f"Avg Trade Return:  {metrics.avg_trade_return_pct:+.2f}%",
        f"Avg Holding Days:  {metrics.avg_holding_days:.0f}",
        f"Total Trades:      {metrics.total_trades}",
    ]
    if benchmark:
        lines.extend([
            "",
            "=== vs Benchmark ===",
            f"Strategy:  {benchmark.strategy_return_pct:+.2f}%",
            f"Benchmark: {benchmark.benchmark_return_pct:+.2f}% ({benchmark.benchmark_ticker})",
            f"Alpha:     {benchmark.alpha_pct:+.2f}%",
        ])
    return "\n".join(lines)


def format_monte_carlo_report(mc: MonteCarloResult) -> str:
    return "\n".join([
        "=== Monte Carlo Simulation ===",
        f"Simulations:     {mc.num_simulations}",
        f"Median Return:   {mc.median_return_pct:+.2f}%",
        f"Mean Return:     {mc.mean_return_pct:+.2f}%",
        f"5th Percentile:  {mc.percentile_5:+.2f}%",
        f"25th Percentile: {mc.percentile_25:+.2f}%",
        f"75th Percentile: {mc.percentile_75:+.2f}%",
        f"95th Percentile: {mc.percentile_95:+.2f}%",
        f"P(Profitable):   {mc.prob_profitable:.1%}",
    ])
