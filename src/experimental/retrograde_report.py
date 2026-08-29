from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.retrogrades import TRADE_SENSITIVE_PLANETS, check_retrograde
from src.data.company_registry import CompanyInfo
from src.data.ephemeris import Planet
from src.market.data_feed import fetch_history
from src.signals.backtest import BacktestResult, run_backtest


@dataclass(frozen=True)
class RetrogradeWindow:
    planet: Planet
    start_date: datetime.date
    end_date: datetime.date
    duration_days: int


@dataclass(frozen=True)
class RetrogradeAnalysis:
    ticker: str
    period_start: datetime.date
    period_end: datetime.date
    windows: list[RetrogradeWindow]
    return_during_retrogrades_pct: float
    return_outside_retrogrades_pct: float
    days_in_retrograde: int
    days_outside_retrograde: int


def find_retrograde_windows(
    planet: Planet,
    start: datetime.date,
    end: datetime.date,
) -> list[RetrogradeWindow]:
    windows: list[RetrogradeWindow] = []
    current_start: datetime.date | None = None
    date = start

    while date <= end:
        status = check_retrograde(planet, date)
        if status.is_retrograde and current_start is None:
            current_start = date
        elif not status.is_retrograde and current_start is not None:
            windows.append(RetrogradeWindow(
                planet=planet,
                start_date=current_start,
                end_date=date - datetime.timedelta(days=1),
                duration_days=(date - current_start).days,
            ))
            current_start = None
        date += datetime.timedelta(days=1)

    if current_start is not None:
        windows.append(RetrogradeWindow(
            planet=planet,
            start_date=current_start,
            end_date=end,
            duration_days=(end - current_start).days + 1,
        ))

    return windows


def analyze_retrograde_performance(
    ticker: str,
    start: datetime.date,
    end: datetime.date,
    planet: Planet = Planet.BUDHA,
) -> RetrogradeAnalysis:
    windows = find_retrograde_windows(planet, start, end)

    retrograde_dates: set[datetime.date] = set()
    for w in windows:
        d = w.start_date
        while d <= w.end_date:
            retrograde_dates.add(d)
            d += datetime.timedelta(days=1)

    df = fetch_history(ticker, start, end)
    if df.empty:
        return RetrogradeAnalysis(
            ticker=ticker, period_start=start, period_end=end,
            windows=windows,
            return_during_retrogrades_pct=0.0,
            return_outside_retrogrades_pct=0.0,
            days_in_retrograde=len(retrograde_dates),
            days_outside_retrograde=(end - start).days - len(retrograde_dates),
        )

    retro_returns = []
    normal_returns = []

    for i in range(1, len(df)):
        row_date = df.index[i]
        d = row_date.date() if hasattr(row_date, "date") else row_date
        daily_return = (df["Close"].iloc[i] / df["Close"].iloc[i - 1] - 1) * 100

        if d in retrograde_dates:
            retro_returns.append(daily_return)
        else:
            normal_returns.append(daily_return)

    retro_total = sum(retro_returns) if retro_returns else 0.0
    normal_total = sum(normal_returns) if normal_returns else 0.0

    return RetrogradeAnalysis(
        ticker=ticker,
        period_start=start,
        period_end=end,
        windows=windows,
        return_during_retrogrades_pct=retro_total,
        return_outside_retrogrades_pct=normal_total,
        days_in_retrograde=len(retro_returns),
        days_outside_retrograde=len(normal_returns),
    )


def generate_retrograde_report(
    company: CompanyInfo,
    start: datetime.date,
    end: datetime.date,
) -> str:
    lines = [f"=== Retrograde Analysis: {company.ticker} ===", f"Period: {start} to {end}", ""]

    for planet in TRADE_SENSITIVE_PLANETS:
        analysis = analyze_retrograde_performance(company.ticker, start, end, planet)
        lines.append(f"--- {planet.name} ---")
        lines.append(f"  Retrograde windows: {len(analysis.windows)}")
        lines.append(f"  Days in retrograde:    {analysis.days_in_retrograde}")
        lines.append(f"  Days outside:          {analysis.days_outside_retrograde}")
        lines.append(f"  Return during retro:   {analysis.return_during_retrogrades_pct:+.2f}%")
        lines.append(f"  Return outside retro:  {analysis.return_outside_retrogrades_pct:+.2f}%")

        for w in analysis.windows:
            lines.append(f"    {w.start_date} to {w.end_date} ({w.duration_days} days)")
        lines.append("")

    return "\n".join(lines)
