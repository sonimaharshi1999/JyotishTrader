from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Position:
    ticker: str
    shares: int
    entry_price: Decimal
    entry_date: datetime.date

    @property
    def cost_basis(self) -> Decimal:
        return self.entry_price * self.shares


@dataclass
class Portfolio:
    cash: Decimal
    positions: dict[str, Position] = field(default_factory=dict)

    @property
    def total_exposure(self) -> Decimal:
        return sum((p.cost_basis for p in self.positions.values()), Decimal("0"))

    @property
    def total_value(self) -> Decimal:
        return self.cash + self.total_exposure

    @property
    def exposure_pct(self) -> float:
        tv = self.total_value
        if tv == 0:
            return 0.0
        return float(self.total_exposure / tv)

    def has_position(self, ticker: str) -> bool:
        return ticker in self.positions

    def get_position(self, ticker: str) -> Position | None:
        return self.positions.get(ticker)


def calculate_position_size(
    portfolio: Portfolio,
    price: Decimal,
    max_position_pct: float = 0.05,
) -> int:
    max_value = portfolio.total_value * Decimal(str(max_position_pct))
    if price <= 0:
        return 0
    shares = int(max_value / price)
    return max(0, shares)


def open_position(
    portfolio: Portfolio,
    ticker: str,
    shares: int,
    price: Decimal,
    date: datetime.date,
) -> Portfolio:
    cost = price * shares
    if cost > portfolio.cash:
        affordable = int(portfolio.cash / price)
        if affordable <= 0:
            return portfolio
        shares = affordable
        cost = price * shares

    new_cash = portfolio.cash - cost
    new_positions = dict(portfolio.positions)
    new_positions[ticker] = Position(
        ticker=ticker,
        shares=shares,
        entry_price=price,
        entry_date=date,
    )
    return Portfolio(cash=new_cash, positions=new_positions)


def close_position(
    portfolio: Portfolio,
    ticker: str,
    price: Decimal,
) -> Portfolio:
    pos = portfolio.positions.get(ticker)
    if pos is None:
        return portfolio

    proceeds = price * pos.shares
    new_cash = portfolio.cash + proceeds
    new_positions = {k: v for k, v in portfolio.positions.items() if k != ticker}
    return Portfolio(cash=new_cash, positions=new_positions)
