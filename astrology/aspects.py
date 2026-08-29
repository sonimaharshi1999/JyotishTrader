"""Vedic aspects (Graha Drishti).

In Jyotish, all grahas aspect the 7th house from their position (180°).
Special aspects:
- Mars (Mangal): also aspects 4th and 8th houses (90° and 210°)
- Jupiter (Guru): also aspects 5th and 9th houses (120° and 240°)
- Saturn (Shani): also aspects 3rd and 10th houses (60° and 270°)
- Rahu/Ketu: also aspect 5th and 9th (like Jupiter in some traditions)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.data.ephemeris import Graha


class DrishtiType(Enum):
    FULL = "Full"           # 7th house (all grahas)
    THREE_QUARTER = "3/4"   # special aspects with 75% strength
    HALF = "Half"           # special aspects with 50% strength
    QUARTER = "Quarter"     # special aspects with 25% strength


# Backward compatibility
AspectType = DrishtiType


@dataclass(frozen=True)
class Drishti:
    drishti_type: DrishtiType
    natal_longitude: float
    transit_longitude: float
    orb_actual: float
    weight: int
    graha: Graha | None = None

    @property
    def strength(self) -> float:
        type_strength = {
            DrishtiType.FULL: 1.0,
            DrishtiType.THREE_QUARTER: 0.75,
            DrishtiType.HALF: 0.50,
            DrishtiType.QUARTER: 0.25,
        }
        base = type_strength.get(self.drishti_type, 1.0)
        if self.orb_actual <= 5:
            return base
        return base * max(0.0, 1.0 - (self.orb_actual - 5) / 10)

    # Backward-compatible aliases
    @property
    def aspect_type(self) -> DrishtiType:
        return self.drishti_type


# Backward compatibility
Aspect = Drishti

VEDIC_ORB = 10.0

# Benefic/malefic weights for Vedic grahas
GRAHA_WEIGHTS: dict[Graha, int] = {
    Graha.SURYA: 1,       # mild malefic
    Graha.CHANDRA: 2,     # benefic (when waxing)
    Graha.MANGAL: -2,     # malefic
    Graha.BUDHA: 1,       # benefic (when unafflicted)
    Graha.GURU: 3,        # great benefic
    Graha.SHUKRA: 2,      # benefic
    Graha.SHANI: -3,      # great malefic
    Graha.RAHU: -2,       # malefic
    Graha.KETU: -1,       # malefic (but spiritual)
}

# Default weights for backward compatibility
DEFAULT_WEIGHTS: dict[DrishtiType, int] = {
    DrishtiType.FULL: 3,
    DrishtiType.THREE_QUARTER: 2,
    DrishtiType.HALF: 1,
    DrishtiType.QUARTER: 1,
}

DEFAULT_ORBS = {
    DrishtiType.FULL: 10.0,
    DrishtiType.THREE_QUARTER: 10.0,
    DrishtiType.HALF: 10.0,
    DrishtiType.QUARTER: 10.0,
}


def _house_distance(lon1: float, lon2: float) -> int:
    """Compute house distance (1-12) from lon1 to lon2."""
    sign1 = int(lon1 // 30)
    sign2 = int(lon2 // 30)
    return ((sign2 - sign1) % 12) + 1


def _angular_distance(lon1: float, lon2: float) -> float:
    diff = abs(lon1 - lon2) % 360
    return min(diff, 360 - diff)


SPECIAL_ASPECTS: dict[Graha, list[int]] = {
    Graha.MANGAL: [4, 7, 8],
    Graha.GURU: [5, 7, 9],
    Graha.SHANI: [3, 7, 10],
    Graha.RAHU: [5, 7, 9],
    Graha.KETU: [5, 7, 9],
}

DEFAULT_ASPECTS = [7]  # all grahas aspect the 7th


def get_aspected_houses(graha: Graha) -> list[int]:
    return SPECIAL_ASPECTS.get(graha, DEFAULT_ASPECTS)


def find_drishti(
    natal_longitude: float,
    transit_longitude: float,
    transit_graha: Graha,
) -> Drishti | None:
    house_dist = _house_distance(natal_longitude, transit_longitude)
    aspected = get_aspected_houses(transit_graha)

    # Check if any aspect applies (reverse: natal is aspected BY transit)
    reverse_dist = _house_distance(transit_longitude, natal_longitude)

    # Transit graha at transit_longitude — does it aspect natal_longitude?
    aspected_by_transit = get_aspected_houses(transit_graha)
    graha_to_natal_dist = _house_distance(transit_longitude, natal_longitude)

    if graha_to_natal_dist not in aspected_by_transit:
        return None

    # Compute orb: how far is the natal point from the exact house cusp?
    exact_aspect_lon = (transit_longitude + (graha_to_natal_dist - 1) * 30) % 360
    orb = _angular_distance(natal_longitude, exact_aspect_lon)

    if orb > VEDIC_ORB:
        return None

    if graha_to_natal_dist == 7:
        dtype = DrishtiType.FULL
    elif graha_to_natal_dist in (5, 9):
        dtype = DrishtiType.THREE_QUARTER
    elif graha_to_natal_dist in (3, 10):
        dtype = DrishtiType.HALF
    else:
        dtype = DrishtiType.QUARTER

    weight = GRAHA_WEIGHTS.get(transit_graha, 0)

    return Drishti(
        drishti_type=dtype,
        natal_longitude=natal_longitude,
        transit_longitude=transit_longitude,
        orb_actual=orb,
        weight=weight,
        graha=transit_graha,
    )


# Backward-compatible aliases
find_aspect = find_drishti


def find_all_drishtis(
    natal_longitudes: dict[str, float],
    transit_longitudes: dict[str, float],
    transit_grahas: dict[str, Graha] | None = None,
) -> list[Drishti]:
    results: list[Drishti] = []
    for natal_name, natal_lon in natal_longitudes.items():
        for transit_name, transit_lon in transit_longitudes.items():
            graha = (transit_grahas or {}).get(transit_name, Graha.SURYA)
            drishti = find_drishti(natal_lon, transit_lon, graha)
            if drishti is not None:
                results.append(drishti)
    return results


find_all_aspects = find_all_drishtis
