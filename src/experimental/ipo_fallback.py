from __future__ import annotations

import datetime
import logging

import yfinance as yf

from src.data.company_registry import CompanyInfo

logger = logging.getLogger(__name__)


def get_ipo_date(ticker: str) -> datetime.date | None:
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="max")
        if hist.empty:
            return None
        first_date = hist.index[0]
        return first_date.date() if hasattr(first_date, "date") else first_date
    except Exception:
        logger.debug("Could not determine IPO date for %s", ticker, exc_info=True)
        return None


def get_best_birth_date(company: CompanyInfo) -> datetime.date:
    if company.incorporation_date != datetime.date(1900, 1, 1):
        return company.incorporation_date

    ipo = get_ipo_date(company.ticker)
    if ipo is not None:
        logger.info(
            "%s: no incorporation date, using IPO date %s",
            company.ticker, ipo,
        )
        return ipo

    logger.warning("%s: no incorporation or IPO date found, using epoch", company.ticker)
    return datetime.date(2000, 1, 1)


def enrich_company_with_ipo(company: CompanyInfo) -> CompanyInfo:
    if company.incorporation_date != datetime.date(1900, 1, 1):
        return company

    ipo = get_ipo_date(company.ticker)
    if ipo:
        return CompanyInfo(
            ticker=company.ticker,
            incorporation_date=ipo,
            incorporation_location=company.incorporation_location,
            sector=company.sector,
        )
    return company
