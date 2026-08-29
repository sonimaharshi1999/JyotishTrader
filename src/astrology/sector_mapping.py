from __future__ import annotations

from dataclasses import dataclass

from src.astrology.transits import TransitAspect
from src.data.ephemeris import Planet


SECTOR_PLANETS: dict[str, dict[Planet, float]] = {
    "Technology": {
        Planet.BUDHA: 2.0, Planet.RAHU: 1.8,
        Planet.SURYA: 0.5, Planet.GURU: 0.8,
    },
    "Communication Services": {
        Planet.BUDHA: 2.0, Planet.KETU: 1.0,
        Planet.SHUKRA: 0.5, Planet.RAHU: 1.2,
    },
    "Financial": {
        Planet.GURU: 2.0, Planet.RAHU: 1.5,
        Planet.SHANI: 1.0, Planet.SURYA: 0.5,
    },
    "Healthcare": {
        Planet.KETU: 2.0, Planet.CHANDRA: 1.5,
        Planet.SHUKRA: 0.8, Planet.GURU: 0.5,
    },
    "Consumer Cyclical": {
        Planet.SHUKRA: 2.0, Planet.GURU: 1.5,
        Planet.CHANDRA: 1.0, Planet.BUDHA: 0.5,
    },
    "Consumer Defensive": {
        Planet.CHANDRA: 2.0, Planet.SHUKRA: 1.5,
        Planet.SHANI: 1.0, Planet.SURYA: 0.5,
    },
    "Industrials": {
        Planet.MANGAL: 2.0, Planet.SHANI: 1.5,
        Planet.SURYA: 0.8, Planet.GURU: 0.5,
    },
    "Automotive": {
        Planet.MANGAL: 2.0, Planet.RAHU: 1.5,
        Planet.BUDHA: 0.8, Planet.SURYA: 0.5,
    },
    "Energy": {
        Planet.MANGAL: 2.0, Planet.RAHU: 1.8,
        Planet.SURYA: 1.0, Planet.SHANI: 0.5,
    },
    "Utilities": {
        Planet.SHANI: 2.0, Planet.CHANDRA: 1.5,
        Planet.KETU: 0.8, Planet.SURYA: 0.5,
    },
    "Real Estate": {
        Planet.SHANI: 2.0, Planet.CHANDRA: 1.8,
        Planet.SHUKRA: 1.0, Planet.GURU: 0.5,
    },
    "Materials": {
        Planet.SHANI: 2.0, Planet.MANGAL: 1.5,
        Planet.RAHU: 1.0, Planet.SURYA: 0.5,
    },
}

DEFAULT_PLANET_WEIGHT = 0.3


@dataclass(frozen=True)
class SectorWeightedScore:
    sector: str
    base_score: float
    sector_adjusted_score: float
    sector_multiplier: float


def get_sector_multiplier(sector: str, planet: Planet) -> float:
    mapping = SECTOR_PLANETS.get(sector, {})
    return mapping.get(planet, DEFAULT_PLANET_WEIGHT)


def apply_sector_weighting(
    transit_aspects: list[TransitAspect],
    sector: str,
) -> SectorWeightedScore:
    if not transit_aspects:
        return SectorWeightedScore(
            sector=sector, base_score=0.0,
            sector_adjusted_score=0.0, sector_multiplier=1.0,
        )

    base_score = sum(
        ta.aspect.weight * ta.aspect.strength
        for ta in transit_aspects
    )

    weighted_score = sum(
        ta.aspect.weight * ta.aspect.strength * get_sector_multiplier(sector, ta.transit_planet)
        for ta in transit_aspects
    )

    multiplier = weighted_score / base_score if base_score != 0 else 1.0

    return SectorWeightedScore(
        sector=sector,
        base_score=base_score,
        sector_adjusted_score=weighted_score,
        sector_multiplier=multiplier,
    )
