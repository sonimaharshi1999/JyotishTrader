"""Vimshottari Dasha system — the primary Vedic predictive timing tool.

The 120-year cycle is divided among 9 grahas based on the Moon's nakshatra
at birth. Each maha dasha is further divided into antardashas (sub-periods).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.astrology.nakshatras import NAKSHATRA_DATA, NAKSHATRA_SPAN, get_nakshatra
from src.data.ephemeris import Graha

# Vimshottari dasha periods in years
DASHA_YEARS: dict[Graha, float] = {
    Graha.KETU: 7,
    Graha.SHUKRA: 20,
    Graha.SURYA: 6,
    Graha.CHANDRA: 10,
    Graha.MANGAL: 7,
    Graha.RAHU: 18,
    Graha.GURU: 16,
    Graha.SHANI: 19,
    Graha.BUDHA: 17,
}

TOTAL_DASHA_YEARS = 120.0

DASHA_ORDER: list[Graha] = [
    Graha.KETU, Graha.SHUKRA, Graha.SURYA, Graha.CHANDRA,
    Graha.MANGAL, Graha.RAHU, Graha.GURU, Graha.SHANI, Graha.BUDHA,
]

# Market favorability of each dasha lord for financial purposes
DASHA_MARKET_SCORES: dict[Graha, float] = {
    Graha.SURYA: 0.5,       # authority, leadership — mild positive
    Graha.CHANDRA: 0.3,     # public, emotions — volatile
    Graha.MANGAL: -0.5,     # aggression, conflict — negative
    Graha.BUDHA: 1.0,       # commerce, trade — very positive
    Graha.GURU: 2.0,        # expansion, wealth — most positive
    Graha.SHUKRA: 1.5,      # luxury, value — positive
    Graha.SHANI: -1.5,      # restriction, loss — negative
    Graha.RAHU: -1.0,       # disruption, illusion — negative
    Graha.KETU: -0.5,       # detachment, loss — mild negative
}


@dataclass(frozen=True)
class DashaPeriod:
    lord: Graha
    start_date: datetime.date
    end_date: datetime.date
    years: float

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days

    @property
    def market_score(self) -> float:
        return DASHA_MARKET_SCORES.get(self.lord, 0.0)


@dataclass(frozen=True)
class AntarDasha:
    maha_lord: Graha
    antar_lord: Graha
    start_date: datetime.date
    end_date: datetime.date

    @property
    def market_score(self) -> float:
        maha = DASHA_MARKET_SCORES.get(self.maha_lord, 0.0)
        antar = DASHA_MARKET_SCORES.get(self.antar_lord, 0.0)
        return maha * 0.6 + antar * 0.4


@dataclass(frozen=True)
class DashaInfo:
    birth_date: datetime.date
    moon_longitude: float
    maha_dashas: list[DashaPeriod]
    current_maha: DashaPeriod | None
    current_antar: AntarDasha | None


def compute_dashas(
    birth_date: datetime.date,
    moon_longitude: float,
    target_date: datetime.date | None = None,
) -> DashaInfo:
    if target_date is None:
        target_date = datetime.date.today()

    nak = get_nakshatra(moon_longitude)
    start_lord = nak.lord
    start_idx = DASHA_ORDER.index(start_lord)

    # Fraction of first dasha already elapsed at birth
    pos_in_nak = moon_longitude % NAKSHATRA_SPAN
    fraction_elapsed = pos_in_nak / NAKSHATRA_SPAN
    first_dasha_years = DASHA_YEARS[start_lord]
    remaining_years = first_dasha_years * (1 - fraction_elapsed)

    maha_dashas: list[DashaPeriod] = []
    current_date = birth_date

    # First (partial) dasha
    end = _add_years(current_date, remaining_years)
    maha_dashas.append(DashaPeriod(
        lord=start_lord, start_date=current_date,
        end_date=end, years=remaining_years,
    ))
    current_date = end

    # Subsequent full dashas (cycle through the order)
    for cycle in range(2):  # 2 full cycles = 240 years, more than enough
        for i in range(9):
            idx = (start_idx + 1 + i) % 9
            lord = DASHA_ORDER[idx]
            years = DASHA_YEARS[lord]
            end = _add_years(current_date, years)
            maha_dashas.append(DashaPeriod(
                lord=lord, start_date=current_date,
                end_date=end, years=years,
            ))
            current_date = end

    # Find current maha dasha
    current_maha = None
    for md in maha_dashas:
        if md.start_date <= target_date < md.end_date:
            current_maha = md
            break

    # Find current antar dasha
    current_antar = None
    if current_maha is not None:
        antars = compute_antardashas(current_maha)
        for ad in antars:
            if ad.start_date <= target_date < ad.end_date:
                current_antar = ad
                break

    return DashaInfo(
        birth_date=birth_date,
        moon_longitude=moon_longitude,
        maha_dashas=maha_dashas,
        current_maha=current_maha,
        current_antar=current_antar,
    )


def compute_antardashas(maha: DashaPeriod) -> list[AntarDasha]:
    maha_idx = DASHA_ORDER.index(maha.lord)
    total_days = maha.duration_days
    antars: list[AntarDasha] = []
    current = maha.start_date

    for i in range(9):
        idx = (maha_idx + i) % 9
        antar_lord = DASHA_ORDER[idx]
        antar_years = DASHA_YEARS[antar_lord]
        fraction = antar_years / TOTAL_DASHA_YEARS
        antar_days = int(total_days * fraction)
        end = current + datetime.timedelta(days=antar_days)

        antars.append(AntarDasha(
            maha_lord=maha.lord,
            antar_lord=antar_lord,
            start_date=current,
            end_date=end,
        ))
        current = end

    return antars


def score_dasha_period(dasha_info: DashaInfo) -> float:
    score = 0.0
    if dasha_info.current_maha:
        score += dasha_info.current_maha.market_score * 0.6
    if dasha_info.current_antar:
        score += dasha_info.current_antar.market_score * 0.4
    return max(-3.0, min(3.0, score))


def _add_years(date: datetime.date, years: float) -> datetime.date:
    days = int(years * 365.25)
    return date + datetime.timedelta(days=days)
