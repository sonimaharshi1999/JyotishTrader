from __future__ import annotations

import datetime
from dataclasses import dataclass

from src.data.ephemeris import Graha, GrahaPosition, get_all_positions

# Backward-compatible alias
Planet = Graha


@dataclass(frozen=True)
class NatalChart:
    ticker: str
    birth_date: datetime.date
    positions: dict[Graha, GrahaPosition]

    def get_planet(self, graha: Graha) -> GrahaPosition:
        return self.positions[graha]

    @property
    def lagna_rashi(self) -> int:
        """Use Sun's rashi as proxy lagna when birth time is unknown."""
        return self.positions[Graha.SURYA].rashi_index

    @property
    def moon_nakshatra_index(self) -> int:
        return self.positions[Graha.CHANDRA].nakshatra_index


def build_natal_chart(ticker: str, incorporation_date: datetime.date) -> NatalChart:
    dt = datetime.datetime.combine(
        incorporation_date,
        datetime.time(12, 0),  # noon default when exact time unknown
        tzinfo=datetime.timezone.utc,
    )
    positions = get_all_positions(dt)
    return NatalChart(ticker=ticker, birth_date=incorporation_date, positions=positions)
