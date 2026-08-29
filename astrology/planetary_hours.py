from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from src.data.ephemeris import Planet


class DayRuler(Enum):
    SUNDAY = Planet.SURYA
    MONDAY = Planet.CHANDRA
    TUESDAY = Planet.MANGAL
    WEDNESDAY = Planet.BUDHA
    THURSDAY = Planet.GURU
    FRIDAY = Planet.SHUKRA
    SATURDAY = Planet.SHANI


DAY_RULERS: dict[int, Planet] = {
    0: Planet.CHANDRA,    # Monday
    1: Planet.MANGAL,     # Tuesday
    2: Planet.BUDHA,      # Wednesday
    3: Planet.GURU,       # Thursday
    4: Planet.SHUKRA,     # Friday
    5: Planet.SHANI,      # Saturday
    6: Planet.SURYA,      # Sunday
}

CHALDEAN_ORDER = [
    Planet.SHANI, Planet.GURU, Planet.MANGAL, Planet.SURYA,
    Planet.SHUKRA, Planet.BUDHA, Planet.CHANDRA,
]

PLANET_MARKET_AFFINITY: dict[Planet, float] = {
    Planet.SURYA: 0.5,
    Planet.CHANDRA: -0.3,
    Planet.BUDHA: 0.3,
    Planet.SHUKRA: 0.8,
    Planet.MANGAL: -0.5,
    Planet.GURU: 1.0,
    Planet.SHANI: -0.8,
}


@dataclass(frozen=True)
class PlanetaryDayInfo:
    date: datetime.date
    day_ruler: Planet
    market_affinity: float


def get_day_ruler(date: datetime.date) -> Planet:
    return DAY_RULERS[date.weekday()]


def get_planetary_day_info(date: datetime.date) -> PlanetaryDayInfo:
    ruler = get_day_ruler(date)
    return PlanetaryDayInfo(
        date=date,
        day_ruler=ruler,
        market_affinity=PLANET_MARKET_AFFINITY.get(ruler, 0.0),
    )


def get_planetary_hour_ruler(date: datetime.date, hour: int) -> Planet:
    day_ruler = get_day_ruler(date)
    start_idx = CHALDEAN_ORDER.index(day_ruler)
    hour_idx = (start_idx + hour) % len(CHALDEAN_ORDER)
    return CHALDEAN_ORDER[hour_idx]


SECTOR_RULING_PLANETS: dict[str, list[Planet]] = {
    "Technology": [Planet.BUDHA, Planet.RAHU],
    "Communication Services": [Planet.BUDHA],
    "Financial": [Planet.GURU, Planet.RAHU],
    "Healthcare": [Planet.KETU, Planet.CHANDRA],
    "Consumer Cyclical": [Planet.SHUKRA, Planet.GURU],
    "Consumer Defensive": [Planet.CHANDRA, Planet.SHUKRA],
    "Industrials": [Planet.MANGAL, Planet.SHANI],
    "Automotive": [Planet.MANGAL, Planet.RAHU],
    "Energy": [Planet.MANGAL, Planet.RAHU],
    "Utilities": [Planet.SHANI, Planet.CHANDRA],
    "Real Estate": [Planet.SHANI, Planet.CHANDRA],
    "Materials": [Planet.SHANI, Planet.MANGAL],
}


def is_sector_day(sector: str, date: datetime.date) -> bool:
    ruler = get_day_ruler(date)
    sector_planets = SECTOR_RULING_PLANETS.get(sector, [])
    return ruler in sector_planets
