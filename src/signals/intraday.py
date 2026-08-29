"""Intraday signal generator using Hora + Muhurta + Panchang.

Each tick (every ~48 minutes, aligned to Muhurta boundaries) checks:
1. Panchang score for the day — is today auspicious for trading at all?
2. Hora ruler for this hour — Guru/Shukra = BUY window, Shani/Mangal = SELL window
3. Muhurta for this 48-min slot — Abhijit = best, Vishti karana = avoid
4. Natal astro score for the stock — daily direction from drishti/dasha/yogas
5. Market price trend — short SMA confirmation

Decision: all five layers must agree for a trade. Any single "AVOID" blocks it.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

from src.astrology.dashas import compute_dashas
from src.astrology.hora import (
    HoraWindow,
    compute_trading_day_horas,
    get_current_hora,
    HORA_SCORE,
)
from src.astrology.muhurta import (
    MuhurtaWindow,
    get_current_muhurta,
    is_in_rahu_kaal,
)
from src.astrology.natal_chart import build_natal_chart
from src.astrology.panchang import Panchang, compute_panchang
from src.astrology.scoring import AstroScore, score_transit_report
from src.astrology.transits import compute_transits
from src.data.company_registry import CompanyInfo
from src.data.ephemeris import Graha
from src.signals.generator import SignalDirection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntradaySignal:
    ticker: str
    timestamp: datetime.datetime
    direction: SignalDirection
    hora_ruler: Graha
    hora_score: float
    muhurta_name: str
    muhurta_score: float
    panchang_score: float
    natal_score: float
    combined_score: float
    trend_signal: int
    confidence: int
    reason: str
    warnings: list[str]

    @property
    def strength(self) -> str:
        v = abs(self.combined_score)
        if v >= 3:
            return "Strong"
        if v >= 1.5:
            return "Moderate"
        return "Weak"


@dataclass
class IntradayState:
    ticker: str
    has_position: bool = False
    entry_price: float = 0.0
    entry_time: datetime.datetime | None = None
    trades_today: int = 0
    pnl_today: float = 0.0


def compute_natal_score_for_day(company: CompanyInfo, date: datetime.date) -> AstroScore:
    natal = build_natal_chart(company.ticker, company.incorporation_date)
    report = compute_transits(natal, date)
    moon_pos = natal.positions[Graha.CHANDRA]
    dasha_info = compute_dashas(company.incorporation_date, moon_pos.longitude, date)
    return score_transit_report(report, dasha_info=dasha_info, natal_positions=natal.positions)


def generate_intraday_signal(
    company: CompanyInfo,
    dt: datetime.datetime,
    natal_score: AstroScore,
    panchang: Panchang | None = None,
    trend_signal: int = 0,
    has_position: bool = False,
    sunrise_hour: float = 6.0,
    min_confidence: int = 30,
    max_trades_per_day: int = 8,
    trades_today: int = 0,
) -> IntradaySignal:
    hora = get_current_hora(dt, sunrise_hour)
    muhurta = get_current_muhurta(dt, sunrise_hour)
    in_rahu_kaal = is_in_rahu_kaal(dt, sunrise_hour)

    if panchang is None:
        panchang = compute_panchang(dt.date())

    natal_val = natal_score.clamped_score
    hora_val = hora.score
    muhurta_val = muhurta.score
    panchang_val = panchang.composite_score

    warnings = list(panchang.warnings)
    if in_rahu_kaal:
        warnings.append("Rahu Kaal active - avoid new positions")
    if muhurta.is_inauspicious:
        warnings.append(f"{muhurta.name} muhurta - inauspicious window")

    # Weighted combination
    combined = (
        natal_val * 0.35          # stock's daily vedic direction
        + hora_val * 1.5          # which planet rules this hour
        + muhurta_val * 1.0       # is this 48-min window auspicious
        + panchang_val * 0.8      # is today a good day overall
        + trend_signal * 0.3      # price chart confirmation
    )

    # Confidence scoring
    confidence = 20
    natal_hora_agree = (natal_val > 0 and hora_val > 0) or (natal_val < 0 and hora_val < 0)
    if natal_hora_agree:
        confidence += 20
    if muhurta.is_auspicious:
        confidence += 15
    if panchang.is_auspicious:
        confidence += 15
    if not warnings:
        confidence += 10
    if (combined > 0 and trend_signal > 0) or (combined < 0 and trend_signal < 0):
        confidence += 15
    if muhurta.is_abhijit:
        confidence += 5
    confidence = min(100, confidence)

    # Hard blocks
    if trades_today >= max_trades_per_day:
        return _make_signal(
            company, dt, SignalDirection.HOLD, hora, muhurta, panchang_val,
            natal_val, combined, trend_signal, confidence,
            "Max trades reached for today", warnings,
        )

    if confidence < min_confidence:
        return _make_signal(
            company, dt, SignalDirection.HOLD, hora, muhurta, panchang_val,
            natal_val, combined, trend_signal, confidence,
            f"Low confidence ({confidence})", warnings,
        )

    if in_rahu_kaal and not has_position:
        return _make_signal(
            company, dt, SignalDirection.HOLD, hora, muhurta, panchang_val,
            natal_val, combined, trend_signal, confidence,
            "Rahu Kaal - no new positions", warnings,
        )

    if muhurta.is_inauspicious and not has_position:
        return _make_signal(
            company, dt, SignalDirection.HOLD, hora, muhurta, panchang_val,
            natal_val, combined, trend_signal, confidence,
            f"Inauspicious muhurta ({muhurta.name})", warnings,
        )

    # Decision
    direction = SignalDirection.HOLD
    reason = "Neutral"

    if hora.is_bullish and muhurta.is_auspicious and combined >= 1.5 and not has_position:
        direction = SignalDirection.BUY
        reason = f"{hora.ruler.name} hora + {muhurta.name} muhurta (auspicious)"
    elif hora.is_bullish and combined >= 2.0 and not has_position:
        direction = SignalDirection.BUY
        reason = f"{hora.ruler.name} hora + strong score ({combined:+.1f})"
    elif hora.is_bearish and has_position:
        direction = SignalDirection.SELL
        reason = f"{hora.ruler.name} hora - exit on bearish hour"
    elif combined <= -1.5 and has_position:
        direction = SignalDirection.SELL
        reason = f"Combined score bearish ({combined:+.1f})"
    elif in_rahu_kaal and has_position and combined < 0:
        direction = SignalDirection.SELL
        reason = "Rahu Kaal + negative score - defensive exit"

    return _make_signal(
        company, dt, direction, hora, muhurta, panchang_val,
        natal_val, combined, trend_signal, confidence, reason, warnings,
    )


def _make_signal(
    company, dt, direction, hora, muhurta, panchang_val,
    natal_val, combined, trend_signal, confidence, reason, warnings,
) -> IntradaySignal:
    return IntradaySignal(
        ticker=company.ticker,
        timestamp=dt,
        direction=direction,
        hora_ruler=hora.ruler,
        hora_score=hora.score,
        muhurta_name=muhurta.name,
        muhurta_score=muhurta.score,
        panchang_score=panchang_val,
        natal_score=natal_val,
        combined_score=combined,
        trend_signal=trend_signal,
        confidence=confidence,
        reason=reason,
        warnings=warnings,
    )


def plan_trading_day(
    company: CompanyInfo,
    date: datetime.date,
    market_open: float = 9.25,
    market_close: float = 15.5,
    sunrise: float = 6.0,
) -> list[dict]:
    """Preview the entire day's hora + muhurta schedule with recommendations."""
    natal = compute_natal_score_for_day(company, date)
    panchang = compute_panchang(date)
    schedule = compute_trading_day_horas(date, market_open, market_close, sunrise)

    plan = []
    for hora in schedule.market_horas:
        combined = (
            natal.clamped_score * 0.35
            + hora.score * 1.5
            + panchang.composite_score * 0.8
        )
        if hora.is_bullish and combined >= 1.5:
            action = "BUY"
        elif hora.is_bearish:
            action = "SELL/EXIT"
        else:
            action = "HOLD"

        plan.append({
            "time": f"{hora.start_time.strftime('%H:%M')}-{hora.end_time.strftime('%H:%M')}",
            "hora_ruler": hora.ruler.name,
            "hora_action": hora.market_action,
            "natal_score": f"{natal.clamped_score:+.1f}",
            "combined": f"{combined:+.1f}",
            "recommendation": action,
        })

    return plan, panchang
