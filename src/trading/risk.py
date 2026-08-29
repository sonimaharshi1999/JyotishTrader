from __future__ import annotations

import logging
from decimal import Decimal

from src.trading.portfolio import Portfolio

logger = logging.getLogger(__name__)


def check_max_exposure(portfolio: Portfolio, max_exposure_pct: float = 0.30) -> bool:
    if portfolio.exposure_pct >= max_exposure_pct:
        logger.info(
            "Exposure %.1f%% exceeds max %.1f%%, blocking new positions",
            portfolio.exposure_pct * 100, max_exposure_pct * 100,
        )
        return False
    return True


def check_stop_loss(
    entry_price: Decimal,
    current_price: Decimal,
    stop_loss_pct: float = 0.07,
) -> bool:
    if entry_price <= 0:
        return False
    drop = float((entry_price - current_price) / entry_price)
    return drop >= stop_loss_pct


def check_position_size_limit(
    portfolio: Portfolio,
    proposed_cost: Decimal,
    max_position_pct: float = 0.05,
) -> bool:
    max_allowed = portfolio.total_value * Decimal(str(max_position_pct))
    if proposed_cost > max_allowed:
        logger.info(
            "Proposed cost $%.2f exceeds max position $%.2f",
            float(proposed_cost), float(max_allowed),
        )
        return False
    return True
