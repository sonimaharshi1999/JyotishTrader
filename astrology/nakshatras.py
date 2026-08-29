from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import IntEnum

from src.data.ephemeris import Graha, GrahaPosition


class NakshatraLord(IntEnum):
    """Vimshottari dasha lords for each nakshatra."""
    KETU = 0
    SHUKRA = 1
    SURYA = 2
    CHANDRA = 3
    MANGAL = 4
    RAHU = 5
    GURU = 6
    SHANI = 7
    BUDHA = 8


NAKSHATRA_DATA: list[dict] = [
    {"name": "Ashwini",        "lord": Graha.KETU,    "deity": "Ashwini Kumaras", "nature": "dharma",  "market": 1.0},
    {"name": "Bharani",        "lord": Graha.SHUKRA,  "deity": "Yama",            "nature": "artha",   "market": -0.5},
    {"name": "Krittika",       "lord": Graha.SURYA,   "deity": "Agni",            "nature": "kama",    "market": 0.5},
    {"name": "Rohini",         "lord": Graha.CHANDRA, "deity": "Brahma",          "nature": "moksha",  "market": 1.5},
    {"name": "Mrigashira",     "lord": Graha.MANGAL,  "deity": "Soma",            "nature": "moksha",  "market": 0.3},
    {"name": "Ardra",          "lord": Graha.RAHU,    "deity": "Rudra",           "nature": "kama",    "market": -1.5},
    {"name": "Punarvasu",      "lord": Graha.GURU,    "deity": "Aditi",           "nature": "artha",   "market": 1.2},
    {"name": "Pushya",         "lord": Graha.SHANI,   "deity": "Brihaspati",      "nature": "dharma",  "market": 2.0},
    {"name": "Ashlesha",       "lord": Graha.BUDHA,   "deity": "Naga",            "nature": "dharma",  "market": -1.0},
    {"name": "Magha",          "lord": Graha.KETU,    "deity": "Pitrs",           "nature": "artha",   "market": 0.5},
    {"name": "Purva Phalguni", "lord": Graha.SHUKRA,  "deity": "Bhaga",           "nature": "kama",    "market": 1.0},
    {"name": "Uttara Phalguni","lord": Graha.SURYA,   "deity": "Aryaman",         "nature": "moksha",  "market": 0.8},
    {"name": "Hasta",          "lord": Graha.CHANDRA, "deity": "Savitar",         "nature": "moksha",  "market": 1.2},
    {"name": "Chitra",         "lord": Graha.MANGAL,  "deity": "Vishwakarma",     "nature": "kama",    "market": 0.0},
    {"name": "Swati",          "lord": Graha.RAHU,    "deity": "Vayu",            "nature": "artha",   "market": 0.5},
    {"name": "Vishakha",       "lord": Graha.GURU,    "deity": "Indra-Agni",      "nature": "dharma",  "market": 0.8},
    {"name": "Anuradha",       "lord": Graha.SHANI,   "deity": "Mitra",           "nature": "dharma",  "market": 1.0},
    {"name": "Jyeshtha",       "lord": Graha.BUDHA,   "deity": "Indra",           "nature": "artha",   "market": -0.5},
    {"name": "Mula",           "lord": Graha.KETU,    "deity": "Nirriti",         "nature": "kama",    "market": -2.0},
    {"name": "Purva Ashadha",  "lord": Graha.SHUKRA,  "deity": "Apas",            "nature": "moksha",  "market": 0.5},
    {"name": "Uttara Ashadha", "lord": Graha.SURYA,   "deity": "Vishvadevas",     "nature": "moksha",  "market": 1.0},
    {"name": "Shravana",       "lord": Graha.CHANDRA, "deity": "Vishnu",          "nature": "artha",   "market": 1.5},
    {"name": "Dhanishtha",     "lord": Graha.MANGAL,  "deity": "Vasus",           "nature": "dharma",  "market": 1.2},
    {"name": "Shatabhisha",    "lord": Graha.RAHU,    "deity": "Varuna",          "nature": "dharma",  "market": -0.8},
    {"name": "Purva Bhadrapada","lord": Graha.GURU,   "deity": "Aja Ekapada",     "nature": "artha",   "market": -0.5},
    {"name": "Uttara Bhadrapada","lord": Graha.SHANI, "deity": "Ahir Budhnya",    "nature": "kama",    "market": 0.5},
    {"name": "Revati",         "lord": Graha.BUDHA,   "deity": "Pushan",          "nature": "moksha",  "market": 1.0},
]

NAKSHATRA_SPAN = 360.0 / 27  # 13°20' = 13.3333...°


@dataclass(frozen=True)
class NakshatraInfo:
    index: int            # 0-26
    name: str
    lord: Graha
    deity: str
    nature: str           # dharma, artha, kama, moksha
    pada: int             # 1-4
    degree_in_nakshatra: float
    market_score: float   # inherent market favorability


def get_nakshatra(longitude: float) -> NakshatraInfo:
    idx = int(longitude / NAKSHATRA_SPAN) % 27
    data = NAKSHATRA_DATA[idx]
    pos_in_nak = longitude % NAKSHATRA_SPAN
    pada = int(pos_in_nak / (NAKSHATRA_SPAN / 4)) + 1

    return NakshatraInfo(
        index=idx,
        name=data["name"],
        lord=data["lord"],
        deity=data["deity"],
        nature=data["nature"],
        pada=min(pada, 4),
        degree_in_nakshatra=pos_in_nak,
        market_score=data["market"],
    )


def get_moon_nakshatra(dt: datetime.datetime) -> NakshatraInfo:
    from src.data.ephemeris import get_graha_position
    moon = get_graha_position(Graha.CHANDRA, dt)
    return get_nakshatra(moon.longitude)


@dataclass(frozen=True)
class NakshatraTransit:
    transit_graha: Graha
    nakshatra: NakshatraInfo
    is_lord_match: bool  # transit graha is the nakshatra lord


def get_graha_nakshatras(
    positions: dict[Graha, GrahaPosition],
) -> dict[Graha, NakshatraInfo]:
    return {g: get_nakshatra(pos.longitude) for g, pos in positions.items()}


def score_nakshatra_transits(
    natal_moon_nakshatra: NakshatraInfo,
    transit_positions: dict[Graha, GrahaPosition],
) -> float:
    """Score based on which nakshatras the transiting grahas occupy."""
    score = 0.0
    natal_lord = natal_moon_nakshatra.lord

    for graha, pos in transit_positions.items():
        nak = get_nakshatra(pos.longitude)

        # Graha transiting a nakshatra ruled by the natal Moon's nakshatra lord
        if nak.lord == natal_lord:
            score += 1.0 if graha in (Graha.GURU, Graha.SHUKRA) else -0.5

        # Pushya nakshatra is universally auspicious for wealth
        if nak.name == "Pushya" and graha == Graha.GURU:
            score += 2.0

        # Mula nakshatra indicates destruction/transformation
        if nak.name == "Mula":
            score -= 0.5

        score += nak.market_score * 0.1

    return max(-5.0, min(5.0, score))
