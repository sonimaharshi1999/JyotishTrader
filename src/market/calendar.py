from __future__ import annotations

import datetime
import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

try:
    import exchange_calendars as xcals
    _nyse = xcals.get_calendar("XNYS")
    _HAS_EXCHANGE_CALENDARS = True
except ImportError:
    _nyse = None
    _HAS_EXCHANGE_CALENDARS = False
    logger.warning("exchange_calendars not installed, using fallback holiday check")


def get_next_earnings_date(ticker: str) -> datetime.date | None:
    tk = yf.Ticker(ticker)
    try:
        cal = tk.calendar
        if cal is None or cal.empty:
            return None
        if "Earnings Date" in cal.index:
            raw = cal.loc["Earnings Date"].iloc[0]
            if hasattr(raw, "date"):
                return raw.date()
            return datetime.date.fromisoformat(str(raw)[:10])
    except Exception:
        logger.debug("Could not fetch earnings calendar for %s", ticker, exc_info=True)
    return None


def is_near_earnings(
    ticker: str,
    reference_date: datetime.date,
    buffer_days: int = 3,
) -> bool:
    earnings_date = get_next_earnings_date(ticker)
    if earnings_date is None:
        return False
    delta = abs((earnings_date - reference_date).days)
    return delta <= buffer_days


def is_market_open(date: datetime.date) -> bool:
    if _HAS_EXCHANGE_CALENDARS:
        try:
            ts = pd.Timestamp(date)
            return _nyse.is_session(ts)
        except Exception:
            pass
    # Fallback: weekdays only
    return date.weekday() < 5


def next_trading_day(date: datetime.date) -> datetime.date:
    if _HAS_EXCHANGE_CALENDARS:
        try:
            ts = pd.Timestamp(date) + pd.Timedelta(days=1)
            return _nyse.date_to_session(ts, direction="next").date()
        except Exception:
            pass
    d = date + datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d += datetime.timedelta(days=1)
    return d
