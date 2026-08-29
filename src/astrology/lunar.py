from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum

from src.data.ephemeris import Planet, get_planet_position


class LunarPhase(Enum):
    NEW_MOON = "New Moon"
    WAXING_CRESCENT = "Waxing Crescent"
    FIRST_QUARTER = "First Quarter"
    WAXING_GIBBOUS = "Waxing Gibbous"
    FULL_MOON = "Full Moon"
    WANING_GIBBOUS = "Waning Gibbous"
    LAST_QUARTER = "Last Quarter"
    WANING_CRESCENT = "Waning Crescent"


PHASE_SCORES: dict[LunarPhase, float] = {
    LunarPhase.NEW_MOON: 1.5,
    LunarPhase.WAXING_CRESCENT: 1.0,
    LunarPhase.FIRST_QUARTER: 0.5,
    LunarPhase.WAXING_GIBBOUS: 0.0,
    LunarPhase.FULL_MOON: -1.5,
    LunarPhase.WANING_GIBBOUS: -0.5,
    LunarPhase.LAST_QUARTER: 0.0,
    LunarPhase.WANING_CRESCENT: 0.5,
}


@dataclass(frozen=True)
class LunarInfo:
    date: datetime.date
    phase: LunarPhase
    moon_longitude: float
    sun_longitude: float
    elongation: float
    score: float


def _normalize_angle(angle: float) -> float:
    return angle % 360


def get_lunar_phase(date: datetime.date) -> LunarInfo:
    dt = datetime.datetime.combine(date, datetime.time(12, 0), tzinfo=datetime.timezone.utc)
    moon = get_planet_position(Planet.CHANDRA, dt)
    sun = get_planet_position(Planet.SURYA, dt)

    elongation = _normalize_angle(moon.longitude - sun.longitude)

    if elongation < 22.5:
        phase = LunarPhase.NEW_MOON
    elif elongation < 67.5:
        phase = LunarPhase.WAXING_CRESCENT
    elif elongation < 112.5:
        phase = LunarPhase.FIRST_QUARTER
    elif elongation < 157.5:
        phase = LunarPhase.WAXING_GIBBOUS
    elif elongation < 202.5:
        phase = LunarPhase.FULL_MOON
    elif elongation < 247.5:
        phase = LunarPhase.WANING_GIBBOUS
    elif elongation < 292.5:
        phase = LunarPhase.LAST_QUARTER
    elif elongation < 337.5:
        phase = LunarPhase.WANING_CRESCENT
    else:
        phase = LunarPhase.NEW_MOON

    return LunarInfo(
        date=date,
        phase=phase,
        moon_longitude=moon.longitude,
        sun_longitude=sun.longitude,
        elongation=elongation,
        score=PHASE_SCORES[phase],
    )


def is_near_new_moon(date: datetime.date, orb_days: int = 2) -> bool:
    for offset in range(-orb_days, orb_days + 1):
        check = date + datetime.timedelta(days=offset)
        info = get_lunar_phase(check)
        if info.phase == LunarPhase.NEW_MOON:
            return True
    return False


def is_near_full_moon(date: datetime.date, orb_days: int = 2) -> bool:
    for offset in range(-orb_days, orb_days + 1):
        check = date + datetime.timedelta(days=offset)
        info = get_lunar_phase(check)
        if info.phase == LunarPhase.FULL_MOON:
            return True
    return False
