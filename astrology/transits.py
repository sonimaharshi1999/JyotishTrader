from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.aspects import Drishti, DrishtiType, find_drishti
from src.astrology.natal_chart import NatalChart
from src.data.ephemeris import Graha, GrahaPosition, get_all_positions

# Backward-compatible aliases
Aspect = Drishti
AspectType = DrishtiType


@dataclass(frozen=True)
class TransitReport:
    date: datetime.date
    ticker: str
    transit_positions: dict[Graha, GrahaPosition]
    aspects: list[TransitAspect]


@dataclass(frozen=True)
class TransitAspect:
    transit_planet: Graha
    natal_planet: Graha
    aspect: Drishti


def compute_transits(
    natal_chart: NatalChart,
    date: datetime.date,
    orbs: dict[DrishtiType, float] | None = None,
    weights: dict[DrishtiType, int] | None = None,
) -> TransitReport:
    dt = datetime.datetime.combine(
        date,
        datetime.time(12, 0),
        tzinfo=datetime.timezone.utc,
    )
    transit_positions = get_all_positions(dt)
    aspects: list[TransitAspect] = []

    for transit_graha, transit_pos in transit_positions.items():
        for natal_graha, natal_pos in natal_chart.positions.items():
            drishti = find_drishti(
                natal_pos.longitude,
                transit_pos.longitude,
                transit_graha,
            )
            if drishti is not None:
                aspects.append(TransitAspect(
                    transit_planet=transit_graha,
                    natal_planet=natal_graha,
                    aspect=drishti,
                ))

    return TransitReport(
        date=date,
        ticker=natal_chart.ticker,
        transit_positions=transit_positions,
        aspects=aspects,
    )
