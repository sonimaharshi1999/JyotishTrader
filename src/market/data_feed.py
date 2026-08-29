from __future__ import annotations

import datetime
import logging
import time
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BACKOFF = 2


@dataclass(frozen=True)
class PriceBar:
    date: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: int


def fetch_history(
    ticker: str,
    start: datetime.date,
    end: datetime.date,
) -> pd.DataFrame:
    for attempt in range(_MAX_RETRIES):
        try:
            tk = yf.Ticker(ticker)
            df = tk.history(start=str(start), end=str(end), auto_adjust=True)
            if df.empty:
                logger.warning("No price data returned for %s (%s to %s)", ticker, start, end)
            return df
        except Exception:
            if attempt == _MAX_RETRIES - 1:
                logger.error("Failed to fetch data for %s after %d retries", ticker, _MAX_RETRIES, exc_info=True)
                return pd.DataFrame()
            wait = _RETRY_BACKOFF ** attempt
            logger.warning("Fetch failed for %s (attempt %d), retrying in %ds", ticker, attempt + 1, wait)
            time.sleep(wait)
    return pd.DataFrame()


def get_sma(df: pd.DataFrame, window: int = 20) -> pd.Series:
    return df["Close"].rolling(window=window).mean()


def get_trend_signal(df: pd.DataFrame, short_window: int = 10, long_window: int = 30) -> int:
    if len(df) < long_window:
        return 0
    short_sma = df["Close"].rolling(window=short_window).mean()
    long_sma = df["Close"].rolling(window=long_window).mean()
    latest_short = short_sma.iloc[-1]
    latest_long = long_sma.iloc[-1]
    if pd.isna(latest_short) or pd.isna(latest_long):
        return 0
    if latest_short > latest_long:
        return 1
    if latest_short < latest_long:
        return -1
    return 0
