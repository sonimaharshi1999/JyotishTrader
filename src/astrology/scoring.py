"""Vedic scoring engine — combines drishti, dasha, nakshatra, yoga, and bhava scores."""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.bhavas import BhavaAnalysis, analyze_bhavas, build_bhava_chart
from src.astrology.dashas import DashaInfo, score_dasha_period
from src.astrology.nakshatras import NakshatraInfo, score_nakshatra_transits, get_nakshatra
from src.astrology.transits import TransitReport
from src.astrology.yogas import Yoga, detect_yogas, score_yogas
from src.data.ephemeris import Graha, GrahaPosition


SCORE_FLOOR = -10.0
SCORE_CEILING = 10.0


@dataclass(frozen=True)
class AstroScore:
    ticker: str
    raw_score: float
    clamped_score: float
    aspect_count: int
    dominant_aspect: str | None
    # Vedic components
    drishti_score: float
    dasha_score: float
    nakshatra_score: float
    yoga_score: float
    bhava_score: float
    active_yogas: list[str]
    current_dasha: str | None
    moon_nakshatra: str | None

    @property
    def label(self) -> str:
        if self.clamped_score >= 5:
            return "Strongly Bullish"
        if self.clamped_score >= 2:
            return "Bullish"
        if self.clamped_score <= -5:
            return "Strongly Bearish"
        if self.clamped_score <= -2:
            return "Bearish"
        return "Neutral"


def score_transit_report(
    report: TransitReport,
    dasha_info: DashaInfo | None = None,
    natal_positions: dict[Graha, GrahaPosition] | None = None,
) -> AstroScore:
    # 1) Drishti (aspect) score
    if report.aspects:
        drishti_raw = sum(
            ta.aspect.weight * ta.aspect.strength
            for ta in report.aspects
        )
        strongest = max(report.aspects, key=lambda ta: abs(ta.aspect.weight * ta.aspect.strength))
        dominant = (
            f"{strongest.transit_planet.name} "
            f"{strongest.aspect.drishti_type.name} "
            f"{strongest.natal_planet.name}"
        )
    else:
        drishti_raw = 0.0
        dominant = None

    # 2) Dasha score
    dasha_score = 0.0
    current_dasha_str = None
    if dasha_info:
        dasha_score = score_dasha_period(dasha_info)
        if dasha_info.current_maha:
            current_dasha_str = f"{dasha_info.current_maha.lord.name}"
            if dasha_info.current_antar:
                current_dasha_str += f"/{dasha_info.current_antar.antar_lord.name}"

    # 3) Nakshatra score
    nakshatra_score = 0.0
    moon_nak_str = None
    if natal_positions and Graha.CHANDRA in natal_positions:
        natal_moon = natal_positions[Graha.CHANDRA]
        natal_moon_nak = get_nakshatra(natal_moon.longitude)
        moon_nak_str = natal_moon_nak.name
        nakshatra_score = score_nakshatra_transits(natal_moon_nak, report.transit_positions)

    # 4) Yoga score (from transit positions)
    transit_yogas = detect_yogas(report.transit_positions)
    yoga_score = score_yogas(transit_yogas)
    yoga_names = [y.name for y in transit_yogas]

    # 5) Bhava score (from natal positions)
    bhava_score = 0.0
    if natal_positions:
        chart = build_bhava_chart(natal_positions)
        analysis = analyze_bhavas(chart, natal_positions)
        bhava_score = analysis.total_financial_score

    # Weighted combination
    raw = (
        drishti_raw * 0.30
        + dasha_score * 0.25
        + nakshatra_score * 0.15
        + yoga_score * 0.20
        + bhava_score * 0.10
    )

    clamped = max(SCORE_FLOOR, min(SCORE_CEILING, raw))

    return AstroScore(
        ticker=report.ticker,
        raw_score=raw,
        clamped_score=clamped,
        aspect_count=len(report.aspects),
        dominant_aspect=dominant,
        drishti_score=drishti_raw,
        dasha_score=dasha_score,
        nakshatra_score=nakshatra_score,
        yoga_score=yoga_score,
        bhava_score=bhava_score,
        active_yogas=yoga_names,
        current_dasha=current_dasha_str,
        moon_nakshatra=moon_nak_str,
    )
