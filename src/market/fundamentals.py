from __future__ import annotations

import logging
from dataclasses import dataclass

import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FundamentalSnapshot:
    ticker: str
    market_cap: float | None
    sector: str | None
    pe_ratio: float | None
    dividend_yield: float | None


def get_fundamentals(ticker: str) -> FundamentalSnapshot:
    tk = yf.Ticker(ticker)
    info = tk.info or {}
    return FundamentalSnapshot(
        ticker=ticker,
        market_cap=info.get("marketCap"),
        sector=info.get("sector"),
        pe_ratio=info.get("trailingPE"),
        dividend_yield=info.get("dividendYield"),
    )


def passes_fundamental_filter(
    snapshot: FundamentalSnapshot,
    min_market_cap: float = 1_000_000_000,
) -> bool:
    if snapshot.market_cap is None:
        logger.warning("No market cap data for %s, skipping", snapshot.ticker)
        return False
    return snapshot.market_cap >= min_market_cap
