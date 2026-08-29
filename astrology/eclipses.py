from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from src.data.ephemeris import Planet, get_planet_position


class EclipseType(Enum):
    SOLAR = "Solar"
    LUNAR = "Lunar"


@dataclass(frozen=True)
class EclipseEvent:
    date: datetime.date
    eclipse_type: EclipseType
    longitude: float


KNOWN_ECLIPSES: list[EclipseEvent] = [
    EclipseEvent(datetime.date(2024, 3, 25), EclipseType.LUNAR, 5.1),
    EclipseEvent(datetime.date(2024, 4, 8), EclipseType.SOLAR, 19.2),
    EclipseEvent(datetime.date(2024, 9, 18), EclipseType.LUNAR, 355.5),
    EclipseEvent(datetime.date(2024, 10, 2), EclipseType.SOLAR, 10.1),
    EclipseEvent(datetime.date(2025, 3, 14), EclipseType.LUNAR, 173.9),
    EclipseEvent(datetime.date(2025, 3, 29), EclipseType.SOLAR, 8.8),
    EclipseEvent(datetime.date(2025, 9, 7), EclipseType.LUNAR, 344.6),
    EclipseEvent(datetime.date(2025, 9, 21), EclipseType.SOLAR, 178.7),
    EclipseEvent(datetime.date(2026, 2, 17), EclipseType.LUNAR, 149.0),
    EclipseEvent(datetime.date(2026, 3, 3), EclipseType.SOLAR, 342.5),
    EclipseEvent(datetime.date(2026, 8, 12), EclipseType.LUNAR, 319.8),
    EclipseEvent(datetime.date(2026, 8, 28), EclipseType.SOLAR, 155.1),
]


@dataclass(frozen=True)
class EclipseImpact:
    eclipse: EclipseEvent
    days_until: int
    natal_planet_hit: str | None
    amplifier: float


def find_nearby_eclipses(
    date: datetime.date,
    window_days: int = 14,
) -> list[EclipseEvent]:
    results = []
    for e in KNOWN_ECLIPSES:
        delta = abs((e.date - date).days)
        if delta <= window_days:
            results.append(e)
    return results


def _angular_distance(lon1: float, lon2: float) -> float:
    diff = abs(lon1 - lon2) % 360
    return min(diff, 360 - diff)


def compute_eclipse_impact(
    date: datetime.date,
    natal_longitudes: dict[str, float],
    window_days: int = 14,
    hit_orb: float = 10.0,
) -> list[EclipseImpact]:
    eclipses = find_nearby_eclipses(date, window_days)
    impacts = []

    for eclipse in eclipses:
        days_until = (eclipse.date - date).days
        proximity = max(0.0, 1.0 - abs(days_until) / window_days)

        hit_planet = None
        tightest_orb = hit_orb
        for planet_name, natal_lon in natal_longitudes.items():
            dist = _angular_distance(eclipse.longitude, natal_lon)
            if dist < tightest_orb:
                tightest_orb = dist
                hit_planet = planet_name

        if hit_planet:
            amplifier = 2.0 * proximity * (1.0 - tightest_orb / hit_orb)
        else:
            amplifier = 0.5 * proximity

        if eclipse.eclipse_type == EclipseType.SOLAR:
            amplifier *= 1.5

        impacts.append(EclipseImpact(
            eclipse=eclipse,
            days_until=days_until,
            natal_planet_hit=hit_planet,
            amplifier=amplifier,
        ))

    return impacts
