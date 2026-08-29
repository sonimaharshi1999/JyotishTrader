from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.aspects import AspectType, find_aspect
from src.astrology.natal_chart import NatalChart, build_natal_chart
from src.astrology.scoring import AstroScore, score_transit_report
from src.astrology.transits import TransitAspect, TransitReport, compute_transits
from src.data.ephemeris import Planet


@dataclass(frozen=True)
class CEOInfo:
    name: str
    birth_date: datetime.date
    ticker: str


@dataclass(frozen=True)
class CompositeChartScore:
    ticker: str
    date: datetime.date
    company_score: float
    ceo_score: float
    synastry_score: float
    blended_score: float

    @property
    def label(self) -> str:
        if self.blended_score >= 5:
            return "Strongly Bullish"
        if self.blended_score >= 2:
            return "Bullish"
        if self.blended_score <= -5:
            return "Strongly Bearish"
        if self.blended_score <= -2:
            return "Bearish"
        return "Neutral"


CEO_DATABASE: dict[str, CEOInfo] = {
    "AAPL": CEOInfo("Tim Cook", datetime.date(1960, 11, 1), "AAPL"),
    "MSFT": CEOInfo("Satya Nadella", datetime.date(1967, 8, 19), "MSFT"),
    "AMZN": CEOInfo("Andy Jassy", datetime.date(1968, 1, 13), "AMZN"),
    "TSLA": CEOInfo("Elon Musk", datetime.date(1971, 6, 28), "TSLA"),
    "GOOGL": CEOInfo("Sundar Pichai", datetime.date(1972, 7, 12), "GOOGL"),
    "META": CEOInfo("Mark Zuckerberg", datetime.date(1984, 5, 14), "META"),
    "NVDA": CEOInfo("Jensen Huang", datetime.date(1963, 2, 17), "NVDA"),
    "JPM": CEOInfo("Jamie Dimon", datetime.date(1956, 3, 13), "JPM"),
}


def compute_synastry_score(
    chart_a: NatalChart,
    chart_b: NatalChart,
) -> float:
    score = 0.0
    for planet_a, pos_a in chart_a.positions.items():
        for planet_b, pos_b in chart_b.positions.items():
            aspect = find_aspect(pos_a.longitude, pos_b.longitude)
            if aspect is not None:
                score += aspect.weight * aspect.strength * 0.3
    return max(-5.0, min(5.0, score))


def compute_composite_score(
    ticker: str,
    company_birth: datetime.date,
    date: datetime.date,
    company_weight: float = 0.5,
    ceo_weight: float = 0.3,
    synastry_weight: float = 0.2,
) -> CompositeChartScore | None:
    ceo = CEO_DATABASE.get(ticker)
    if ceo is None:
        return None

    company_natal = build_natal_chart(ticker, company_birth)
    company_transit = compute_transits(company_natal, date)
    company_astro = score_transit_report(company_transit)

    ceo_natal = build_natal_chart(f"{ticker}_CEO", ceo.birth_date)
    ceo_transit = compute_transits(ceo_natal, date)
    ceo_astro = score_transit_report(ceo_transit)

    synastry = compute_synastry_score(company_natal, ceo_natal)

    blended = (
        company_astro.clamped_score * company_weight
        + ceo_astro.clamped_score * ceo_weight
        + synastry * synastry_weight
    )

    return CompositeChartScore(
        ticker=ticker,
        date=date,
        company_score=company_astro.clamped_score,
        ceo_score=ceo_astro.clamped_score,
        synastry_score=synastry,
        blended_score=blended,
    )
