from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from src.data.company_registry import CompanyInfo
from src.trading.portfolio import Portfolio

logger = logging.getLogger(__name__)


def get_sector_exposure(
    portfolio: Portfolio,
    company_registry: dict[str, CompanyInfo],
) -> dict[str, Decimal]:
    exposure: dict[str, Decimal] = defaultdict(Decimal)
    for ticker, position in portfolio.positions.items():
        company = company_registry.get(ticker)
        sector = company.sector if company else "Unknown"
        exposure[sector] += position.cost_basis
    return dict(exposure)


def check_sector_concentration(
    portfolio: Portfolio,
    company_registry: dict[str, CompanyInfo],
    ticker_to_add: str,
    proposed_cost: Decimal,
    max_sector_pct: float = 0.15,
) -> bool:
    company = company_registry.get(ticker_to_add)
    if company is None:
        return True

    sector = company.sector
    current_exposure = get_sector_exposure(portfolio, company_registry)
    sector_total = current_exposure.get(sector, Decimal("0")) + proposed_cost
    total_value = portfolio.total_value

    if total_value <= 0:
        return False

    sector_pct = float(sector_total / total_value)
    if sector_pct > max_sector_pct:
        logger.info(
            "%s: sector '%s' would be %.1f%% of portfolio (max %.1f%%), blocking",
            ticker_to_add, sector, sector_pct * 100, max_sector_pct * 100,
        )
        return False
    return True


def format_sector_report(
    portfolio: Portfolio,
    company_registry: dict[str, CompanyInfo],
) -> str:
    exposure = get_sector_exposure(portfolio, company_registry)
    total = portfolio.total_value
    lines = ["Sector Exposure:"]
    for sector, amount in sorted(exposure.items(), key=lambda x: x[1], reverse=True):
        pct = float(amount / total * 100) if total > 0 else 0.0
        lines.append(f"  {sector:25s}  ${amount:>10,.2f}  ({pct:.1f}%)")
    return "\n".join(lines)
