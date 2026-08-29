"""Vedic Bhava (House) system using whole-sign houses.

In Jyotish, the Lagna (ascendant) sign becomes the 1st house, and each
subsequent sign is the next house. When birth time is unknown (as with
company incorporation dates), we use Sun-sign as the proxy Lagna.

Key financial houses:
- 2nd house (Dhana bhava): accumulated wealth, income
- 5th house: speculation, investments, intelligence
- 7th house: partnerships, business deals
- 10th house: career, public standing, business success
- 11th house (Labha bhava): gains, profits, fulfillment of desires
- 8th house: sudden gains/losses, inheritance, transformation
- 12th house (Vyaya bhava): losses, expenditure
"""
from __future__ import annotations

from dataclasses import dataclass

from src.data.ephemeris import Graha, GrahaPosition


BHAVA_NAMES = {
    1: "Tanu (Self)",
    2: "Dhana (Wealth)",
    3: "Sahaja (Courage)",
    4: "Sukha (Happiness)",
    5: "Putra (Speculation)",
    6: "Ripu (Enemies)",
    7: "Kalatra (Partnerships)",
    8: "Mrityu (Transformation)",
    9: "Dharma (Fortune)",
    10: "Karma (Career)",
    11: "Labha (Gains)",
    12: "Vyaya (Losses)",
}

FINANCIAL_HOUSES = {2, 5, 7, 10, 11}
NEGATIVE_HOUSES = {6, 8, 12}

# Graha strength by house placement (simplified dig bala / house joy)
GRAHA_HOUSE_STRENGTH: dict[Graha, dict[int, float]] = {
    Graha.SURYA: {1: 1.5, 10: 2.0, 9: 1.0},
    Graha.CHANDRA: {4: 2.0, 2: 1.0, 7: 1.0},
    Graha.MANGAL: {10: 2.0, 3: 1.5, 6: 1.0},
    Graha.BUDHA: {1: 1.5, 10: 1.5, 7: 1.0},
    Graha.GURU: {1: 2.0, 5: 2.0, 9: 2.0, 11: 1.5},
    Graha.SHUKRA: {4: 2.0, 7: 1.5, 2: 1.5, 11: 1.0},
    Graha.SHANI: {7: 1.5, 10: 1.5, 11: 1.0, 3: 1.0},
    Graha.RAHU: {3: 1.0, 6: 1.5, 10: 1.0, 11: 1.5},
    Graha.KETU: {9: 1.5, 12: 1.0, 3: 1.0},
}


@dataclass(frozen=True)
class BhavaChart:
    lagna_rashi: int  # 0-11, rashi index of the ascendant/Sun
    graha_houses: dict[Graha, int]  # graha → house number (1-12)
    house_occupants: dict[int, list[Graha]]  # house → list of grahas


@dataclass(frozen=True)
class BhavaAnalysis:
    chart: BhavaChart
    wealth_house_score: float
    gains_house_score: float
    loss_house_score: float
    total_financial_score: float
    yogas_from_houses: list[str]


def build_bhava_chart(
    positions: dict[Graha, GrahaPosition],
    lagna_graha: Graha = Graha.SURYA,
) -> BhavaChart:
    lagna_pos = positions.get(lagna_graha)
    if lagna_pos is None:
        lagna_rashi = 0
    else:
        lagna_rashi = lagna_pos.rashi_index

    graha_houses: dict[Graha, int] = {}
    house_occupants: dict[int, list[Graha]] = {h: [] for h in range(1, 13)}

    for graha, pos in positions.items():
        house = ((pos.rashi_index - lagna_rashi) % 12) + 1
        graha_houses[graha] = house
        house_occupants[house].append(graha)

    return BhavaChart(
        lagna_rashi=lagna_rashi,
        graha_houses=graha_houses,
        house_occupants=house_occupants,
    )


def analyze_bhavas(
    chart: BhavaChart,
    positions: dict[Graha, GrahaPosition],
) -> BhavaAnalysis:
    wealth_score = 0.0
    gains_score = 0.0
    loss_score = 0.0
    yoga_notes: list[str] = []

    for graha, house in chart.graha_houses.items():
        house_mult = GRAHA_HOUSE_STRENGTH.get(graha, {}).get(house, 0.5)
        base = 1.0 if graha in (Graha.GURU, Graha.SHUKRA, Graha.BUDHA) else -0.5

        if house == 2:
            wealth_score += base * house_mult
        elif house == 11:
            gains_score += base * house_mult
        elif house == 5:
            wealth_score += base * house_mult * 0.8
        elif house == 10:
            gains_score += base * house_mult * 0.7
        elif house == 12:
            loss_score += abs(base) * house_mult
        elif house == 8:
            loss_score += abs(base) * house_mult * 0.5

    # Jupiter in 2nd or 11th = strong wealth indicator
    guru_house = chart.graha_houses.get(Graha.GURU)
    if guru_house in (2, 11):
        yoga_notes.append(f"Guru in {BHAVA_NAMES.get(guru_house, str(guru_house))} — wealth blessing")
        wealth_score += 2.0

    # Malefics in 11th gain through struggle
    for g in chart.house_occupants.get(11, []):
        if g in (Graha.SHANI, Graha.MANGAL, Graha.RAHU):
            yoga_notes.append(f"{g.name} in Labha — gains through effort/disruption")

    # Malefics in 12th = financial drain
    for g in chart.house_occupants.get(12, []):
        if g in (Graha.SHANI, Graha.RAHU, Graha.KETU):
            yoga_notes.append(f"{g.name} in Vyaya — financial drain")
            loss_score += 1.0

    total = wealth_score + gains_score - loss_score
    total = max(-5.0, min(5.0, total))

    return BhavaAnalysis(
        chart=chart,
        wealth_house_score=wealth_score,
        gains_house_score=gains_score,
        loss_house_score=loss_score,
        total_financial_score=total,
        yogas_from_houses=yoga_notes,
    )
