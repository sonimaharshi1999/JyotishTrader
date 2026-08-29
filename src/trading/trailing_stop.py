from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class TrailingStop:
    ticker: str
    entry_price: Decimal
    trail_pct: Decimal
    highest_price: Decimal
    stop_price: Decimal

    @classmethod
    def create(cls, ticker: str, entry_price: Decimal, trail_pct: float) -> TrailingStop:
        pct = Decimal(str(trail_pct))
        stop = entry_price * (1 - pct)
        return cls(
            ticker=ticker,
            entry_price=entry_price,
            trail_pct=pct,
            highest_price=entry_price,
            stop_price=stop,
        )

    def update(self, current_price: Decimal) -> TrailingStop:
        if current_price > self.highest_price:
            new_high = current_price
            new_stop = new_high * (1 - self.trail_pct)
            return TrailingStop(
                ticker=self.ticker,
                entry_price=self.entry_price,
                trail_pct=self.trail_pct,
                highest_price=new_high,
                stop_price=new_stop,
            )
        return self

    def is_triggered(self, current_price: Decimal) -> bool:
        return current_price <= self.stop_price

    @property
    def current_gain_pct(self) -> float:
        return float((self.highest_price - self.entry_price) / self.entry_price * 100)

    @property
    def locked_gain_pct(self) -> float:
        return float((self.stop_price - self.entry_price) / self.entry_price * 100)
