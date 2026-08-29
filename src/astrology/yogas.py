"""Vedic Yogas — specific planetary combinations that indicate wealth, power, or loss.

Each yoga has market implications: wealth yogas are bullish, poverty/destruction yogas bearish.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.data.ephemeris import Graha, GrahaPosition


@dataclass(frozen=True)
class Yoga:
    name: str
    sanskrit: str
    description: str
    market_score: float  # positive = bullish, negative = bearish
    grahas_involved: list[Graha]


def _rashi_of(pos: GrahaPosition) -> int:
    return pos.rashi_index


def _house_from(pos_a: GrahaPosition, pos_b: GrahaPosition) -> int:
    """House distance from a to b (1-12)."""
    return ((_rashi_of(pos_b) - _rashi_of(pos_a)) % 12) + 1


KENDRA_HOUSES = {1, 4, 7, 10}
TRIKONA_HOUSES = {1, 5, 9}


def detect_yogas(positions: dict[Graha, GrahaPosition]) -> list[Yoga]:
    yogas: list[Yoga] = []

    guru = positions.get(Graha.GURU)
    chandra = positions.get(Graha.CHANDRA)
    surya = positions.get(Graha.SURYA)
    shukra = positions.get(Graha.SHUKRA)
    mangal = positions.get(Graha.MANGAL)
    shani = positions.get(Graha.SHANI)
    budha = positions.get(Graha.BUDHA)
    rahu = positions.get(Graha.RAHU)
    ketu = positions.get(Graha.KETU)

    # Gaja Kesari Yoga: Jupiter in kendra from Moon
    if guru and chandra:
        dist = _house_from(chandra, guru)
        if dist in KENDRA_HOUSES:
            yogas.append(Yoga(
                name="Gaja Kesari", sanskrit="गजकेसरी",
                description="Jupiter in kendra from Moon — fame, wealth, and intelligence",
                market_score=3.0,
                grahas_involved=[Graha.GURU, Graha.CHANDRA],
            ))

    # Dhana Yoga: Lord of 2nd and 11th in kendra/trikona (simplified)
    if guru and shukra:
        dist = _house_from(guru, shukra)
        if dist in KENDRA_HOUSES or dist in TRIKONA_HOUSES:
            yogas.append(Yoga(
                name="Dhana Yoga", sanskrit="धनयोग",
                description="Jupiter-Venus in mutual kendra/trikona — wealth accumulation",
                market_score=2.5,
                grahas_involved=[Graha.GURU, Graha.SHUKRA],
            ))

    # Budhaditya Yoga: Mercury conjunct Sun
    if budha and surya:
        if _rashi_of(budha) == _rashi_of(surya):
            yogas.append(Yoga(
                name="Budhaditya", sanskrit="बुधादित्य",
                description="Mercury conjunct Sun — intelligence in commerce and trade",
                market_score=1.5,
                grahas_involved=[Graha.BUDHA, Graha.SURYA],
            ))

    # Chandra-Mangal Yoga: Moon conjunct Mars
    if chandra and mangal:
        if _rashi_of(chandra) == _rashi_of(mangal):
            yogas.append(Yoga(
                name="Chandra-Mangal", sanskrit="चंद्र-मंगल",
                description="Moon-Mars conjunction — wealth through bold action",
                market_score=1.5,
                grahas_involved=[Graha.CHANDRA, Graha.MANGAL],
            ))

    # Lakshmi Yoga: Venus in own/exalted sign + lord of 9th strong (simplified)
    if shukra:
        venus_strong = _rashi_of(shukra) in (1, 6, 11)  # Taurus, Libra, Pisces (exalted)
        if venus_strong and guru:
            dist = _house_from(shukra, guru)
            if dist in KENDRA_HOUSES:
                yogas.append(Yoga(
                    name="Lakshmi Yoga", sanskrit="लक्ष्मीयोग",
                    description="Strong Venus with Jupiter — goddess of wealth blesses",
                    market_score=3.0,
                    grahas_involved=[Graha.SHUKRA, Graha.GURU],
                ))

    # Kemadruma Yoga: Moon with no planets in 2nd or 12th from it (poverty yoga)
    if chandra:
        moon_rashi = _rashi_of(chandra)
        neighbors = {(moon_rashi + 1) % 12, (moon_rashi - 1) % 12}
        has_neighbor = False
        for g, pos in positions.items():
            if g == Graha.CHANDRA:
                continue
            if _rashi_of(pos) in neighbors:
                has_neighbor = True
                break
        if not has_neighbor:
            yogas.append(Yoga(
                name="Kemadruma", sanskrit="केमद्रुम",
                description="Moon isolated — poverty, financial struggle",
                market_score=-2.5,
                grahas_involved=[Graha.CHANDRA],
            ))

    # Grahan Yoga: Sun/Moon with Rahu or Ketu (eclipse yoga)
    if rahu:
        if surya and _rashi_of(surya) == _rashi_of(rahu):
            yogas.append(Yoga(
                name="Surya Grahan", sanskrit="सूर्यग्रहण",
                description="Sun-Rahu conjunction — authority undermined, deception",
                market_score=-2.0,
                grahas_involved=[Graha.SURYA, Graha.RAHU],
            ))
        if chandra and _rashi_of(chandra) == _rashi_of(rahu):
            yogas.append(Yoga(
                name="Chandra Grahan", sanskrit="चंद्रग्रहण",
                description="Moon-Rahu conjunction — emotional instability, panic",
                market_score=-2.0,
                grahas_involved=[Graha.CHANDRA, Graha.RAHU],
            ))

    # Shani-Mangal Yoga (malefic conjunction)
    if shani and mangal:
        if _rashi_of(shani) == _rashi_of(mangal):
            yogas.append(Yoga(
                name="Shani-Mangal", sanskrit="शनि-मंगल",
                description="Saturn-Mars conjunction — conflict, destruction, volatility",
                market_score=-3.0,
                grahas_involved=[Graha.SHANI, Graha.MANGAL],
            ))

    # Hamsa Yoga: Jupiter in kendra in own/exalted sign
    if guru:
        guru_rashi = _rashi_of(guru)
        if guru_rashi in (8, 11, 3):  # Sagittarius, Pisces, Cancer (own/exalted)
            if surya:
                dist = _house_from(surya, guru)
                if dist in KENDRA_HOUSES:
                    yogas.append(Yoga(
                        name="Hamsa Yoga", sanskrit="हंसयोग",
                        description="Jupiter in kendra in own sign — divine blessings, prosperity",
                        market_score=2.5,
                        grahas_involved=[Graha.GURU],
                    ))

    return yogas


def score_yogas(yogas: list[Yoga]) -> float:
    if not yogas:
        return 0.0
    return max(-5.0, min(5.0, sum(y.market_score for y in yogas)))
