"""Vakri (retrograde) detection for Vedic astrology.

In Jyotish, retrograde planets (vakri grahas) are considered strong but
unpredictable. Budha (Mercury) vakri disrupts trade and communication.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.data.ephemeris import Graha, get_graha_position

# Backward-compatible alias
Planet = Graha


@dataclass(frozen=True)
class RetrogradeStatus:
    planet: Graha
    is_retrograde: bool
    speed: float
    date: datetime.date

    @property
    def is_vakri(self) -> bool:
        return self.is_retrograde


TRADE_SENSITIVE_PLANETS = [Graha.BUDHA, Graha.SHUKRA, Graha.MANGAL]


def check_retrograde(planet: Graha, date: datetime.date) -> RetrogradeStatus:
    dt = datetime.datetime.combine(
        date, datetime.time(12, 0), tzinfo=datetime.timezone.utc,
    )
    pos = get_graha_position(planet, dt)
    return RetrogradeStatus(
        planet=planet,
        is_retrograde=pos.is_retrograde,
        speed=pos.speed,
        date=date,
    )


def is_mercury_retrograde(date: datetime.date) -> bool:
    return check_retrograde(Graha.BUDHA, date).is_retrograde


def check_retrograde_shadow(
    planet: Graha,
    date: datetime.date,
    shadow_days: int = 3,
) -> bool:
    for offset in range(-shadow_days, shadow_days + 1):
        check_date = date + datetime.timedelta(days=offset)
        status = check_retrograde(planet, check_date)
        if status.is_retrograde:
            return True
    return False


def get_all_retrograde_statuses(date: datetime.date) -> list[RetrogradeStatus]:
    return [check_retrograde(p, date) for p in TRADE_SENSITIVE_PLANETS]
