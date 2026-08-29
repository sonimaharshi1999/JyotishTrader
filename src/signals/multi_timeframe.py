from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.natal_chart import build_natal_chart
from src.astrology.scoring import AstroScore, score_transit_report
from src.astrology.transits import compute_transits
from src.data.company_registry import CompanyInfo


@dataclass(frozen=True)
class TimeframeScore:
    label: str
    score: float
    aspect_count: int


@dataclass(frozen=True)
class MultiTimeframeSignal:
    ticker: str
    date: datetime.date
    daily: TimeframeScore
    weekly_avg: TimeframeScore
    monthly_avg: TimeframeScore
    alignment: str
    composite: float

    @property
    def all_agree(self) -> bool:
        signs = [
            self.daily.score > 0,
            self.weekly_avg.score > 0,
            self.monthly_avg.score > 0,
        ]
        return all(signs) or not any(signs)


def _average_scores(scores: list[AstroScore]) -> TimeframeScore:
    if not scores:
        return TimeframeScore(label="empty", score=0.0, aspect_count=0)
    avg_score = sum(s.clamped_score for s in scores) / len(scores)
    total_aspects = sum(s.aspect_count for s in scores)
    return TimeframeScore(label="avg", score=avg_score, aspect_count=total_aspects)


def compute_multi_timeframe(
    company: CompanyInfo,
    date: datetime.date,
    weekly_lookback: int = 7,
    monthly_lookback: int = 30,
) -> MultiTimeframeSignal:
    natal = build_natal_chart(company.ticker, company.incorporation_date)

    daily_report = compute_transits(natal, date)
    daily_score = score_transit_report(daily_report)
    daily_tf = TimeframeScore(
        label="daily", score=daily_score.clamped_score,
        aspect_count=daily_score.aspect_count,
    )

    weekly_scores = []
    for i in range(weekly_lookback):
        d = date - datetime.timedelta(days=i)
        report = compute_transits(natal, d)
        weekly_scores.append(score_transit_report(report))
    weekly_tf = _average_scores(weekly_scores)
    weekly_tf = TimeframeScore(label="weekly", score=weekly_tf.score, aspect_count=weekly_tf.aspect_count)

    monthly_scores = []
    for i in range(0, monthly_lookback, 3):
        d = date - datetime.timedelta(days=i)
        report = compute_transits(natal, d)
        monthly_scores.append(score_transit_report(report))
    monthly_tf = _average_scores(monthly_scores)
    monthly_tf = TimeframeScore(label="monthly", score=monthly_tf.score, aspect_count=monthly_tf.aspect_count)

    signs = [daily_tf.score > 0, weekly_tf.score > 0, monthly_tf.score > 0]
    if all(signs):
        alignment = "Bullish Alignment"
    elif not any(signs):
        alignment = "Bearish Alignment"
    else:
        alignment = "Mixed"

    composite = daily_tf.score * 0.5 + weekly_tf.score * 0.3 + monthly_tf.score * 0.2

    return MultiTimeframeSignal(
        ticker=company.ticker,
        date=date,
        daily=daily_tf,
        weekly_avg=weekly_tf,
        monthly_avg=monthly_tf,
        alignment=alignment,
        composite=composite,
    )
