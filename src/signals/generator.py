from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.astrology.dashas import compute_dashas
from src.astrology.natal_chart import NatalChart, build_natal_chart
from src.astrology.scoring import AstroScore, score_transit_report
from src.astrology.transits import compute_transits
from src.data.company_registry import CompanyInfo
from src.data.ephemeris import Graha
from src.market.data_feed import fetch_history, get_trend_signal
from src.signals.confidence import compute_confidence
from src.signals.correlation import CorrelationTracker
from src.signals.multi_timeframe import compute_multi_timeframe

logger = logging.getLogger(__name__)


class SignalDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class TradingSignal:
    ticker: str
    date: datetime.date
    direction: SignalDirection
    astro_score: float
    trend_signal: int
    composite_score: float
    dominant_aspect: str | None
    confidence: int | None = None
    active_yogas: list[str] | None = None
    current_dasha: str | None = None
    moon_nakshatra: str | None = None
    multi_timeframe_alignment: str | None = None

    @property
    def strength(self) -> str:
        v = abs(self.composite_score)
        if v >= 6:
            return "Strong"
        if v >= 3:
            return "Moderate"
        return "Weak"


def generate_signal(
    company: CompanyInfo,
    date: datetime.date,
    buy_threshold: float = 3.0,
    sell_threshold: float = -3.0,
    require_trend_confirmation: bool = True,
    lookback_days: int = 60,
    min_confidence: int = 0,
    use_multi_timeframe: bool = False,
    correlation_tracker: CorrelationTracker | None = None,
) -> TradingSignal:
    natal = build_natal_chart(company.ticker, company.incorporation_date)
    report = compute_transits(natal, date)

    moon_pos = natal.positions[Graha.CHANDRA]
    dasha_info = compute_dashas(company.incorporation_date, moon_pos.longitude, date)

    astro = score_transit_report(
        report,
        dasha_info=dasha_info,
        natal_positions=natal.positions,
    )

    trend = 0
    if require_trend_confirmation:
        try:
            start = date - datetime.timedelta(days=lookback_days)
            df = fetch_history(company.ticker, start, date)
            if not df.empty:
                trend = get_trend_signal(df)
        except Exception:
            logger.warning("Market data failed for %s, proceeding without trend", company.ticker)

    composite = astro.clamped_score * (1.0 + 0.3 * trend)

    # Confidence scoring
    natal_longs = {g.name: pos.longitude for g, pos in natal.positions.items()}
    conf = compute_confidence(astro, report, trend, natal_longs)
    confidence_score = conf.score

    # Multi-timeframe alignment
    mtf_alignment = None
    if use_multi_timeframe:
        try:
            mtf = compute_multi_timeframe(company, date)
            mtf_alignment = mtf.alignment
            if not mtf.all_agree:
                composite *= 0.7
                confidence_score = int(confidence_score * 0.7)
        except Exception:
            logger.debug("Multi-timeframe failed for %s", company.ticker, exc_info=True)

    # Correlation-based weight adjustment
    if correlation_tracker and astro.dominant_aspect:
        adj = correlation_tracker.get_aspect_weight_adjustment(astro.dominant_aspect)
        composite *= adj

    # Gate by confidence
    if confidence_score < min_confidence:
        direction = SignalDirection.HOLD
    elif composite >= buy_threshold:
        direction = SignalDirection.BUY
    elif composite <= sell_threshold:
        direction = SignalDirection.SELL
    else:
        direction = SignalDirection.HOLD

    return TradingSignal(
        ticker=company.ticker,
        date=date,
        direction=direction,
        astro_score=astro.clamped_score,
        trend_signal=trend,
        composite_score=composite,
        dominant_aspect=astro.dominant_aspect,
        confidence=confidence_score,
        active_yogas=astro.active_yogas,
        current_dasha=astro.current_dasha,
        moon_nakshatra=astro.moon_nakshatra,
        multi_timeframe_alignment=mtf_alignment,
    )
