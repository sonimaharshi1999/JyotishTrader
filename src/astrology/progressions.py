from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.aspects import Aspect, AspectType, find_aspect
from src.data.ephemeris import Planet, PlanetPosition, get_all_positions


@dataclass(frozen=True)
class ProgressedChart:
    ticker: str
    birth_date: datetime.date
    progressed_date: datetime.date
    years_elapsed: float
    positions: dict[Planet, PlanetPosition]


@dataclass(frozen=True)
class ProgressedAspect:
    progressed_planet: Planet
    natal_planet: Planet
    aspect: Aspect


def build_progressed_chart(
    ticker: str,
    birth_date: datetime.date,
    target_date: datetime.date,
) -> ProgressedChart:
    """Secondary progressions: 1 day after birth = 1 year of life."""
    years = (target_date - birth_date).days / 365.25
    progressed_offset = datetime.timedelta(days=years)
    progressed_date = birth_date + progressed_offset

    dt = datetime.datetime.combine(
        progressed_date,
        datetime.time(12, 0),
        tzinfo=datetime.timezone.utc,
    )
    positions = get_all_positions(dt)

    return ProgressedChart(
        ticker=ticker,
        birth_date=birth_date,
        progressed_date=progressed_date,
        years_elapsed=years,
        positions=positions,
    )


def compute_progressed_aspects(
    progressed: ProgressedChart,
    natal_positions: dict[Planet, PlanetPosition],
    orbs: dict[AspectType, float] | None = None,
    weights: dict[AspectType, int] | None = None,
) -> list[ProgressedAspect]:
    tighter_orbs = orbs
    if tighter_orbs is None:
        tighter_orbs = {
            AspectType.CONJUNCTION: 2.0,
            AspectType.SEXTILE: 1.5,
            AspectType.SQUARE: 2.0,
            AspectType.TRINE: 2.0,
            AspectType.OPPOSITION: 2.0,
        }

    aspects: list[ProgressedAspect] = []
    for prog_planet, prog_pos in progressed.positions.items():
        for natal_planet, natal_pos in natal_positions.items():
            aspect = find_aspect(
                natal_pos.longitude,
                prog_pos.longitude,
                tighter_orbs,
                weights,
            )
            if aspect is not None:
                aspects.append(ProgressedAspect(
                    progressed_planet=prog_planet,
                    natal_planet=natal_planet,
                    aspect=aspect,
                ))
    return aspects


def score_progressions(aspects: list[ProgressedAspect]) -> float:
    if not aspects:
        return 0.0
    raw = sum(a.aspect.weight * a.aspect.strength for a in aspects)
    return max(-5.0, min(5.0, raw * 0.5))
