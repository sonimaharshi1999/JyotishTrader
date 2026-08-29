from __future__ import annotations

import datetime
import logging

from src.astrology.retrogrades import check_retrograde_shadow
from src.data.ephemeris import Planet
from src.market.calendar import is_market_open, is_near_earnings
from src.signals.generator import SignalDirection, TradingSignal

logger = logging.getLogger(__name__)


def apply_filters(
    signal: TradingSignal,
    skip_mercury_retrograde: bool = True,
    retrograde_shadow_days: int = 3,
    earnings_buffer_days: int = 3,
) -> TradingSignal:
    if signal.direction == SignalDirection.HOLD:
        return signal

    if not is_market_open(signal.date):
        logger.info("%s: market closed on %s, forcing HOLD", signal.ticker, signal.date)
        return _force_hold(signal)

    if skip_mercury_retrograde:
        in_shadow = check_retrograde_shadow(
            Planet.BUDHA, signal.date, retrograde_shadow_days,
        )
        if in_shadow and signal.direction == SignalDirection.BUY:
            logger.info(
                "%s: Mercury retrograde shadow on %s, suppressing BUY",
                signal.ticker, signal.date,
            )
            return _force_hold(signal)

    if is_near_earnings(signal.ticker, signal.date, earnings_buffer_days):
        if signal.direction == SignalDirection.BUY:
            logger.info(
                "%s: near earnings on %s, suppressing new BUY",
                signal.ticker, signal.date,
            )
            return _force_hold(signal)

    return signal


def _force_hold(signal: TradingSignal) -> TradingSignal:
    return TradingSignal(
        ticker=signal.ticker,
        date=signal.date,
        direction=SignalDirection.HOLD,
        astro_score=signal.astro_score,
        trend_signal=signal.trend_signal,
        composite_score=signal.composite_score,
        dominant_aspect=signal.dominant_aspect,
    )
