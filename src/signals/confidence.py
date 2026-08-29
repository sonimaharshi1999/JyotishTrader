from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.eclipses import compute_eclipse_impact
from src.astrology.lunar import get_lunar_phase
from src.astrology.planetary_hours import get_planetary_day_info
from src.astrology.scoring import AstroScore
from src.astrology.transits import TransitReport


@dataclass(frozen=True)
class ConfidenceScore:
    ticker: str
    date: datetime.date
    score: int  # 0-100
    aspect_tightness: float
    aspect_agreement: float
    trend_alignment: float
    lunar_modifier: float
    day_ruler_modifier: float
    eclipse_modifier: float
    breakdown: str

    @property
    def label(self) -> str:
        if self.score >= 80:
            return "Very High"
        if self.score >= 60:
            return "High"
        if self.score >= 40:
            return "Moderate"
        if self.score >= 20:
            return "Low"
        return "Very Low"


def compute_confidence(
    astro_score: AstroScore,
    transit_report: TransitReport,
    trend_signal: int,
    natal_longitudes: dict[str, float] | None = None,
) -> ConfidenceScore:
    date = transit_report.date

    # 1) Aspect tightness: tighter orbs = more confidence (0-25 points)
    if transit_report.aspects:
        avg_strength = sum(
            ta.aspect.strength for ta in transit_report.aspects
        ) / len(transit_report.aspects)
        tightness_pts = avg_strength * 25
    else:
        avg_strength = 0.0
        tightness_pts = 0.0

    # 2) Aspect agreement: are most aspects pointing the same direction? (0-25 points)
    if transit_report.aspects:
        bullish = sum(1 for ta in transit_report.aspects if ta.aspect.weight > 0)
        bearish = sum(1 for ta in transit_report.aspects if ta.aspect.weight < 0)
        total = bullish + bearish
        agreement = max(bullish, bearish) / total if total > 0 else 0.0
        agreement_pts = agreement * 25
    else:
        agreement = 0.0
        agreement_pts = 0.0

    # 3) Trend alignment: astro direction matches price trend (0-20 points)
    if astro_score.clamped_score > 0 and trend_signal > 0:
        trend_pts = 20.0
    elif astro_score.clamped_score < 0 and trend_signal < 0:
        trend_pts = 20.0
    elif trend_signal == 0:
        trend_pts = 10.0
    else:
        trend_pts = 0.0

    # 4) Lunar modifier (0-10 points)
    lunar = get_lunar_phase(date)
    if astro_score.clamped_score > 0 and lunar.score > 0:
        lunar_pts = 10.0
    elif astro_score.clamped_score < 0 and lunar.score < 0:
        lunar_pts = 10.0
    else:
        lunar_pts = 5.0

    # 5) Day ruler modifier (0-10 points)
    day_info = get_planetary_day_info(date)
    if day_info.market_affinity > 0 and astro_score.clamped_score > 0:
        day_pts = 10.0
    elif day_info.market_affinity < 0 and astro_score.clamped_score < 0:
        day_pts = 10.0
    else:
        day_pts = 5.0

    # 6) Eclipse amplifier (0-10 points)
    eclipse_pts = 0.0
    if natal_longitudes:
        impacts = compute_eclipse_impact(date, natal_longitudes)
        if impacts:
            max_amp = max(i.amplifier for i in impacts)
            eclipse_pts = min(10.0, max_amp * 5)

    raw = tightness_pts + agreement_pts + trend_pts + lunar_pts + day_pts + eclipse_pts
    final = int(max(0, min(100, raw)))

    breakdown = (
        f"tightness={tightness_pts:.0f} agreement={agreement_pts:.0f} "
        f"trend={trend_pts:.0f} lunar={lunar_pts:.0f} "
        f"day={day_pts:.0f} eclipse={eclipse_pts:.0f}"
    )

    return ConfidenceScore(
        ticker=astro_score.ticker,
        date=date,
        score=final,
        aspect_tightness=avg_strength,
        aspect_agreement=agreement,
        trend_alignment=trend_pts,
        lunar_modifier=lunar_pts,
        day_ruler_modifier=day_pts,
        eclipse_modifier=eclipse_pts,
        breakdown=breakdown,
    )
