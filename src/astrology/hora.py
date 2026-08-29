"""Vedic Hora (Planetary Hour) system for intraday trading.

Each day is divided into 24 planetary hours following the Chaldean order,
starting from the day's ruler at sunrise. During market hours (~9:15 AM to
3:30 PM IST for NSE, 9:30 AM to 4:00 PM ET for NYSE), each hora lasts
approximately 1 hour.

Bullish horas: Guru, Shukra, Budha, Surya
Bearish horas: Shani, Mangal, Rahu
Neutral horas: Chandra, Ketu
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.data.ephemeris import Graha

CHALDEAN_ORDER = [
    Graha.SHANI, Graha.GURU, Graha.MANGAL, Graha.SURYA,
    Graha.SHUKRA, Graha.BUDHA, Graha.CHANDRA,
]

DAY_RULERS: dict[int, Graha] = {
    0: Graha.CHANDRA,  # Monday
    1: Graha.MANGAL,   # Tuesday
    2: Graha.BUDHA,    # Wednesday
    3: Graha.GURU,     # Thursday
    4: Graha.SHUKRA,   # Friday
    5: Graha.SHANI,    # Saturday
    6: Graha.SURYA,    # Sunday
}

HORA_MARKET_ACTION: dict[Graha, str] = {
    Graha.GURU: "BUY",       # expansion, wealth
    Graha.SHUKRA: "BUY",     # value, luxury
    Graha.BUDHA: "BUY",      # commerce, trade
    Graha.SURYA: "HOLD",     # authority, neutral
    Graha.CHANDRA: "HOLD",   # emotion, volatile
    Graha.MANGAL: "SELL",    # aggression, conflict
    Graha.SHANI: "SELL",     # restriction, loss
    Graha.RAHU: "SELL",      # disruption
    Graha.KETU: "HOLD",      # detachment
}

HORA_SCORE: dict[Graha, float] = {
    Graha.GURU: 2.0,
    Graha.SHUKRA: 1.5,
    Graha.BUDHA: 1.0,
    Graha.SURYA: 0.3,
    Graha.CHANDRA: 0.0,
    Graha.MANGAL: -1.0,
    Graha.SHANI: -2.0,
    Graha.RAHU: -1.5,
    Graha.KETU: -0.5,
}


@dataclass(frozen=True)
class HoraWindow:
    hora_number: int          # 1-24 from sunrise
    ruler: Graha
    start_time: datetime.datetime
    end_time: datetime.datetime
    market_action: str        # BUY, SELL, HOLD
    score: float

    @property
    def is_bullish(self) -> bool:
        return self.market_action == "BUY"

    @property
    def is_bearish(self) -> bool:
        return self.market_action == "SELL"


@dataclass(frozen=True)
class IntradayHoraSchedule:
    date: datetime.date
    day_ruler: Graha
    horas: list[HoraWindow]
    market_horas: list[HoraWindow]  # only during market hours
    buy_windows: list[HoraWindow]
    sell_windows: list[HoraWindow]


def _get_sunrise_hour(date: datetime.date, timezone_offset: float = 5.5) -> float:
    """Approximate sunrise hour (local time). Default IST (+5.5)."""
    day_of_year = date.timetuple().tm_yday
    # Simple sinusoidal approximation for tropical/subtropical latitudes
    sunrise = 6.0 + 0.5 * _sin_approx((day_of_year - 172) / 365.25)
    return sunrise


def _sin_approx(x: float) -> float:
    import math
    return math.sin(x * 2 * math.pi)


def compute_hora_ruler(date: datetime.date, hora_number: int) -> Graha:
    """Compute which graha rules the nth hora (0-indexed from sunrise)."""
    day_ruler = DAY_RULERS[date.weekday()]
    start_idx = CHALDEAN_ORDER.index(day_ruler)
    idx = (start_idx + hora_number) % len(CHALDEAN_ORDER)
    return CHALDEAN_ORDER[idx]


def get_current_hora(dt: datetime.datetime, sunrise_hour: float = 6.0) -> HoraWindow:
    """Get the hora active at a specific datetime."""
    local_hour = dt.hour + dt.minute / 60.0
    hora_number = int(local_hour - sunrise_hour)
    if hora_number < 0:
        hora_number += 24

    ruler = compute_hora_ruler(dt.date(), hora_number)
    start = dt.replace(hour=int(sunrise_hour + hora_number), minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(hours=1)

    return HoraWindow(
        hora_number=hora_number + 1,
        ruler=ruler,
        start_time=start,
        end_time=end,
        market_action=HORA_MARKET_ACTION.get(ruler, "HOLD"),
        score=HORA_SCORE.get(ruler, 0.0),
    )


def compute_trading_day_horas(
    date: datetime.date,
    market_open_hour: float = 9.25,   # 9:15 AM
    market_close_hour: float = 15.5,  # 3:30 PM
    sunrise_hour: float = 6.0,
) -> IntradayHoraSchedule:
    """Compute all hora windows for a trading day."""
    day_ruler = DAY_RULERS[date.weekday()]
    all_horas: list[HoraWindow] = []

    for i in range(24):
        actual_hour = sunrise_hour + i
        if actual_hour >= 24:
            actual_hour -= 24

        ruler = compute_hora_ruler(date, i)
        h = int(actual_hour)
        m = int((actual_hour - h) * 60)
        start = datetime.datetime(date.year, date.month, date.day, h, m)
        end = start + datetime.timedelta(hours=1)

        all_horas.append(HoraWindow(
            hora_number=i + 1,
            ruler=ruler,
            start_time=start,
            end_time=end,
            market_action=HORA_MARKET_ACTION.get(ruler, "HOLD"),
            score=HORA_SCORE.get(ruler, 0.0),
        ))

    market_horas = [
        h for h in all_horas
        if market_open_hour <= (h.start_time.hour + h.start_time.minute / 60.0) < market_close_hour
    ]

    return IntradayHoraSchedule(
        date=date,
        day_ruler=day_ruler,
        horas=all_horas,
        market_horas=market_horas,
        buy_windows=[h for h in market_horas if h.is_bullish],
        sell_windows=[h for h in market_horas if h.is_bearish],
    )


def get_hora_recommendation(
    dt: datetime.datetime,
    natal_astro_score: float,
    sunrise_hour: float = 6.0,
) -> dict:
    """Combined recommendation: hora + natal score for this moment."""
    hora = get_current_hora(dt, sunrise_hour)

    combined_score = natal_astro_score * 0.7 + hora.score * 0.3

    if combined_score >= 1.5 and hora.is_bullish:
        action = "BUY"
    elif combined_score <= -1.5 and hora.is_bearish:
        action = "SELL"
    elif hora.is_bearish and natal_astro_score > 0:
        action = "HOLD"
    else:
        action = hora.market_action

    return {
        "hora_ruler": hora.ruler.name,
        "hora_action": hora.market_action,
        "hora_score": hora.score,
        "natal_score": natal_astro_score,
        "combined_score": combined_score,
        "final_action": action,
        "window_start": hora.start_time.strftime("%H:%M"),
        "window_end": hora.end_time.strftime("%H:%M"),
    }
