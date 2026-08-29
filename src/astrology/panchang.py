"""Panchang — the five limbs of the Vedic daily calendar.

The five elements:
1. Tithi — lunar day (30 per month, based on Moon-Sun elongation)
2. Vara — weekday ruler (already in planetary_hours.py)
3. Nakshatra — Moon's mansion (already in nakshatras.py)
4. Yoga — Sun+Moon longitude combination (27 yogas, NOT planetary yogas)
5. Karana — half-tithi (60 per month)

Each element has financial implications from classical Jyotish texts.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.data.ephemeris import Graha, get_graha_position


# === TITHI (Lunar Day) ===

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima",
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya",
]

TITHI_PAKSHA = ["Shukla"] * 15 + ["Krishna"] * 15  # Bright / Dark half

# Financial scores for each tithi
# Shukla Panchami, Dashami, Ekadashi, Trayodashi = wealth tithis
# Ashtami, Navami, Chaturdashi, Amavasya = inauspicious
TITHI_SCORES: dict[int, float] = {
    0: 0.5,     # Shukla Pratipada — new beginning
    1: 0.5,     # Dwitiya
    2: 1.0,     # Tritiya — good for purchases
    3: -0.5,    # Chaturthi — Vinayaka, obstacles
    4: 1.5,     # Panchami — wealth tithi (Lakshmi)
    5: 1.0,     # Shashthi
    6: 1.0,     # Saptami
    7: -1.5,    # Ashtami — Rikta (empty), avoid buying
    8: -1.0,    # Navami — inauspicious
    9: 1.5,     # Dashami — victory tithi
    10: 1.5,    # Ekadashi — auspicious for wealth
    11: 1.0,    # Dwadashi
    12: 1.5,    # Trayodashi — Dhana Trayodashi (wealth)
    13: -2.0,   # Chaturdashi — very inauspicious
    14: 0.5,    # Purnima — full moon, volatile
    15: 0.0,    # Krishna Pratipada
    16: 0.0,    # Dwitiya
    17: 0.5,    # Tritiya
    18: -0.5,   # Chaturthi
    19: 1.0,    # Panchami
    20: 0.5,    # Shashthi
    21: 0.5,    # Saptami
    22: -1.5,   # Ashtami — Rikta
    23: -1.0,   # Navami
    24: 1.0,    # Dashami
    25: 1.0,    # Ekadashi
    26: 0.5,    # Dwadashi
    27: 1.0,    # Trayodashi
    28: -2.0,   # Chaturdashi
    29: -1.5,   # Amavasya — no moon, worst for new ventures
}


# === YOGA (Sun+Moon combination, NOT planetary yoga) ===

YOGA_NAMES = [
    "Vishkambha", "Preeti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarma", "Dhriti", "Shoola", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti",
]

# Financial scores for Panchang yogas
YOGA_SCORES: dict[int, float] = {
    0: -1.0,    # Vishkambha — obstacles
    1: 1.5,     # Preeti — love, good deals
    2: 1.0,     # Ayushman — long life, stability
    3: 2.0,     # Saubhagya — good fortune (BEST)
    4: 1.5,     # Shobhana — beauty, value
    5: -1.5,    # Atiganda — extreme knots, danger
    6: 1.5,     # Sukarma — good deeds, profitable
    7: 1.0,     # Dhriti — firmness, hold
    8: -2.0,    # Shoola — thorn/pain (WORST)
    9: -1.5,    # Ganda — knots, obstacles
    10: 2.0,    # Vriddhi — growth (BEST for wealth)
    11: 1.0,    # Dhruva — fixed, stable investment
    12: -1.0,   # Vyaghata — beating
    13: 1.5,    # Harshana — happiness
    14: -0.5,   # Vajra — thunderbolt, sudden
    15: 2.0,    # Siddhi — accomplishment (BEST)
    16: -2.0,   # Vyatipata — calamity (WORST)
    17: 1.0,    # Variyana — comfort
    18: -1.5,   # Parigha — obstruction
    19: 1.5,    # Shiva — auspicious
    20: 2.0,    # Siddha — accomplished (BEST)
    21: 1.0,    # Sadhya — achievable
    22: 1.5,    # Shubha — auspicious
    23: 1.0,    # Shukla — bright
    24: 1.5,    # Brahma — creative
    25: 1.5,    # Indra — powerful
    26: -2.0,   # Vaidhriti — inauspicious (WORST)
}


# === KARANA (half-tithi) ===

KARANA_NAMES = [
    "Bava", "Balava", "Kaulava", "Taitila", "Garija",
    "Vanija", "Vishti", "Shakuni", "Chatushpada", "Naga", "Kimstughna",
]

# Vishti (Bhadra) karana is universally inauspicious
KARANA_SCORES: dict[str, float] = {
    "Bava": 1.0,        # lion — powerful, good for bold moves
    "Balava": 0.5,      # leopard — moderate
    "Kaulava": 1.0,     # pig — good for accumulation
    "Taitila": 1.5,     # donkey — good for wealth, trade
    "Garija": 0.5,      # elephant — stable
    "Vanija": 2.0,      # cow — BEST for commerce/trading
    "Vishti": -2.0,     # dog — WORST (Bhadra), avoid all transactions
    "Shakuni": -1.0,    # bird — unstable
    "Chatushpada": -0.5, # quadruped — slow
    "Naga": -1.0,       # serpent — hidden danger
    "Kimstughna": 0.0,  # neutral
}


@dataclass(frozen=True)
class TithiInfo:
    index: int              # 0-29
    name: str
    paksha: str             # Shukla (bright) or Krishna (dark)
    score: float


@dataclass(frozen=True)
class PanchangYogaInfo:
    index: int              # 0-26
    name: str
    score: float


@dataclass(frozen=True)
class KaranaInfo:
    name: str
    score: float


@dataclass(frozen=True)
class Panchang:
    date: datetime.date
    tithi: TithiInfo
    yoga: PanchangYogaInfo
    karana: KaranaInfo
    vara_ruler: Graha       # day ruler (from planetary_hours)
    moon_nakshatra: str     # from nakshatras module
    composite_score: float  # combined financial score
    is_auspicious: bool
    warnings: list[str]


def compute_tithi(moon_lon: float, sun_lon: float) -> TithiInfo:
    elongation = (moon_lon - sun_lon) % 360
    idx = int(elongation / 12) % 30
    return TithiInfo(
        index=idx,
        name=TITHI_NAMES[idx],
        paksha=TITHI_PAKSHA[idx],
        score=TITHI_SCORES.get(idx, 0.0),
    )


def compute_panchang_yoga(moon_lon: float, sun_lon: float) -> PanchangYogaInfo:
    combined = (moon_lon + sun_lon) % 360
    idx = int(combined / (360 / 27)) % 27
    return PanchangYogaInfo(
        index=idx,
        name=YOGA_NAMES[idx],
        score=YOGA_SCORES.get(idx, 0.0),
    )


def compute_karana(moon_lon: float, sun_lon: float) -> KaranaInfo:
    elongation = (moon_lon - sun_lon) % 360
    tithi_idx = int(elongation / 12) % 30
    karana_idx = (tithi_idx * 2) % 11
    # First half or second half of tithi
    half = int((elongation % 12) / 6)
    karana_idx = ((tithi_idx * 2) + half) % 11

    name = KARANA_NAMES[karana_idx]
    return KaranaInfo(name=name, score=KARANA_SCORES.get(name, 0.0))


def compute_panchang(date: datetime.date) -> Panchang:
    from src.astrology.nakshatras import get_nakshatra
    from src.astrology.planetary_hours import get_day_ruler

    dt = datetime.datetime.combine(date, datetime.time(12, 0), tzinfo=datetime.timezone.utc)
    moon = get_graha_position(Graha.CHANDRA, dt)
    sun = get_graha_position(Graha.SURYA, dt)

    tithi = compute_tithi(moon.longitude, sun.longitude)
    yoga = compute_panchang_yoga(moon.longitude, sun.longitude)
    karana = compute_karana(moon.longitude, sun.longitude)
    vara = get_day_ruler(date)
    nak = get_nakshatra(moon.longitude)

    warnings: list[str] = []
    if karana.name == "Vishti":
        warnings.append("Bhadra (Vishti Karana) - avoid all new transactions")
    if tithi.index in (7, 22):  # Ashtami
        warnings.append("Rikta Tithi (Ashtami) - empty, avoid buying")
    if tithi.index in (13, 28):  # Chaturdashi
        warnings.append("Chaturdashi - highly inauspicious for finance")
    if tithi.index == 29:  # Amavasya
        warnings.append("Amavasya (New Moon) - avoid new ventures")
    if yoga.name in ("Shoola", "Vyatipata", "Vaidhriti"):
        warnings.append(f"{yoga.name} Yoga - inauspicious, high risk day")

    composite = (
        tithi.score * 0.30
        + yoga.score * 0.25
        + karana.score * 0.25
        + nak.market_score * 0.20
    )

    is_auspicious = composite >= 0.5 and not warnings

    return Panchang(
        date=date,
        tithi=tithi,
        yoga=yoga,
        karana=karana,
        vara_ruler=vara,
        moon_nakshatra=nak.name,
        composite_score=composite,
        is_auspicious=is_auspicious,
        warnings=warnings,
    )
