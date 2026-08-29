"""Muhurta — 48-minute Vedic time windows (30 per day).

Each day from sunrise to sunrise is divided into 30 muhurtas (~48 min each).
Certain muhurtas are universally auspicious or inauspicious for financial activity.

Classical texts name specific muhurtas:
- Abhijit Muhurta (midday, ~11:36-12:24) — universally auspicious, best for new ventures
- Brahma Muhurta (pre-dawn, ~4:24-5:12) — spiritual, not for trading
- Rahu Kaal — inauspicious period ruled by Rahu, avoid new transactions

For trading, we score each muhurta on a -2 to +2 scale.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.data.ephemeris import Graha


MUHURTA_DURATION_MINUTES = 48
MUHURTAS_PER_DAY = 30

MUHURTA_NAMES = [
    "Rudra", "Ahi", "Mitra", "Pitru", "Vasu",
    "Vara", "Vishvedeva", "Vidhi", "Satamukhi", "Puruhuta",
    "Vahini", "Naktankara", "Varuna", "Aryaman", "Bhaga",
    "Girisha", "Ajapada", "Ahir-Budhnya", "Pusha", "Ashvini",
    "Yama", "Agni", "Vidhatr", "Kanda", "Aditi",
    "Jiva", "Vishnu", "Dyumadgadyuti", "Brahma", "Samudram",
]

# Market favorability score for each muhurta (-2 to +2)
# Based on classical Jyotish texts on auspicious timings
MUHURTA_SCORES: dict[int, float] = {
    0: -1.5,   # Rudra — destructive
    1: -1.0,   # Ahi — serpent, hidden danger
    2: 1.5,    # Mitra — friendly, good for deals
    3: -0.5,   # Pitru — ancestors, not for new business
    4: 1.0,    # Vasu — wealth gods
    5: 0.5,    # Vara — day lord, neutral-positive
    6: 1.0,    # Vishvedeva — all gods
    7: 1.5,    # Vidhi — creator, good for new ventures
    8: 0.5,    # Satamukhi — hundred-faced
    9: 0.5,    # Puruhuta — Indra, power
    10: -0.5,  # Vahini — fire, burns
    11: -1.5,  # Naktankara — night-maker, inauspicious
    12: 0.5,   # Varuna — ocean, deep value
    13: 1.0,   # Aryaman — nobility, fair dealing
    14: 2.0,   # Bhaga — fortune, wealth (ABHIJIT area)
    15: -1.0,  # Girisha — Shiva, destruction
    16: -0.5,  # Ajapada — one-footed, unstable
    17: 0.0,   # Ahir-Budhnya — neutral
    18: 1.0,   # Pusha — nourishment, growth
    19: 1.5,   # Ashvini — healers, fresh start
    20: -2.0,  # Yama — death god, worst for finance
    21: 0.5,   # Agni — fire, transformation
    22: 1.0,   # Vidhatr — ordainer
    23: 0.5,   # Kanda — section
    24: 1.5,   # Aditi — mother of gods, abundance
    25: 2.0,   # Jiva — life force, best for wealth
    26: 1.5,   # Vishnu — preserver, stability
    27: 0.5,   # Dyumadgadyuti — radiance
    28: 0.0,   # Brahma — creation, spiritual not material
    29: -0.5,  # Samudram — ocean, unpredictable
}

# Rahu Kaal: varies by day of week (approximate hour from sunrise)
# Monday=2nd hr, Sat=1st hr, Fri=3rd, Wed=5th, Thu=4th, Tue=7th, Sun=8th
RAHU_KAAL_HORA: dict[int, int] = {
    0: 2,  # Monday — 2nd hora from sunrise
    1: 7,  # Tuesday
    2: 5,  # Wednesday
    3: 4,  # Thursday
    4: 3,  # Friday
    5: 1,  # Saturday
    6: 8,  # Sunday
}


@dataclass(frozen=True)
class MuhurtaWindow:
    index: int                  # 0-29
    name: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    score: float                # -2 to +2
    is_abhijit: bool
    is_rahu_kaal: bool

    @property
    def is_auspicious(self) -> bool:
        return self.score >= 1.0 and not self.is_rahu_kaal

    @property
    def is_inauspicious(self) -> bool:
        return self.score <= -1.0 or self.is_rahu_kaal

    @property
    def action(self) -> str:
        if self.is_rahu_kaal:
            return "AVOID"
        if self.score >= 1.5:
            return "BUY"
        if self.score >= 0.5:
            return "HOLD"
        if self.score <= -1.0:
            return "SELL"
        return "HOLD"


def compute_rahu_kaal(date: datetime.date, sunrise_hour: float = 6.0) -> tuple[float, float]:
    """Return (start_hour, end_hour) of Rahu Kaal for the given day."""
    hora_offset = RAHU_KAAL_HORA[date.weekday()]
    start = sunrise_hour + (hora_offset - 1) * 1.5
    end = start + 1.5
    return start, end


def is_in_rahu_kaal(dt: datetime.datetime, sunrise_hour: float = 6.0) -> bool:
    start, end = compute_rahu_kaal(dt.date(), sunrise_hour)
    current = dt.hour + dt.minute / 60.0
    return start <= current < end


def compute_muhurta_schedule(
    date: datetime.date,
    sunrise_hour: float = 6.0,
    market_open_hour: float = 9.25,
    market_close_hour: float = 15.5,
) -> list[MuhurtaWindow]:
    """Compute all 30 muhurtas and filter to market hours."""
    rahu_start, rahu_end = compute_rahu_kaal(date, sunrise_hour)
    windows: list[MuhurtaWindow] = []

    for i in range(MUHURTAS_PER_DAY):
        offset_minutes = i * MUHURTA_DURATION_MINUTES
        start_dt = datetime.datetime(
            date.year, date.month, date.day,
            int(sunrise_hour), int((sunrise_hour % 1) * 60),
        ) + datetime.timedelta(minutes=offset_minutes)
        end_dt = start_dt + datetime.timedelta(minutes=MUHURTA_DURATION_MINUTES)

        start_hour = start_dt.hour + start_dt.minute / 60.0
        is_rahu = rahu_start <= start_hour < rahu_end

        # Abhijit is the 8th muhurta (midday, ~11:36-12:24)
        is_abhijit = (i == 14)

        score = MUHURTA_SCORES.get(i, 0.0)
        if is_abhijit:
            score = max(score, 2.0)

        windows.append(MuhurtaWindow(
            index=i,
            name=MUHURTA_NAMES[i] if i < len(MUHURTA_NAMES) else f"Muhurta-{i+1}",
            start_time=start_dt,
            end_time=end_dt,
            score=score,
            is_abhijit=is_abhijit,
            is_rahu_kaal=is_rahu,
        ))

    # Filter to market hours
    market_windows = [
        w for w in windows
        if market_open_hour <= (w.start_time.hour + w.start_time.minute / 60.0) < market_close_hour
    ]
    return market_windows


def get_current_muhurta(
    dt: datetime.datetime,
    sunrise_hour: float = 6.0,
) -> MuhurtaWindow:
    """Get the muhurta active at a specific time."""
    sunrise_dt = datetime.datetime(
        dt.year, dt.month, dt.day,
        int(sunrise_hour), int((sunrise_hour % 1) * 60),
    )
    minutes_since_sunrise = (dt - sunrise_dt).total_seconds() / 60
    idx = int(minutes_since_sunrise / MUHURTA_DURATION_MINUTES) % MUHURTAS_PER_DAY

    rahu_start, rahu_end = compute_rahu_kaal(dt.date(), sunrise_hour)
    current_hour = dt.hour + dt.minute / 60.0
    is_rahu = rahu_start <= current_hour < rahu_end

    start_dt = sunrise_dt + datetime.timedelta(minutes=idx * MUHURTA_DURATION_MINUTES)
    end_dt = start_dt + datetime.timedelta(minutes=MUHURTA_DURATION_MINUTES)

    score = MUHURTA_SCORES.get(idx, 0.0)
    is_abhijit = (idx == 14)
    if is_abhijit:
        score = max(score, 2.0)

    return MuhurtaWindow(
        index=idx,
        name=MUHURTA_NAMES[idx] if idx < len(MUHURTA_NAMES) else f"Muhurta-{idx+1}",
        start_time=start_dt,
        end_time=end_dt,
        score=score,
        is_abhijit=is_abhijit,
        is_rahu_kaal=is_rahu,
    )
