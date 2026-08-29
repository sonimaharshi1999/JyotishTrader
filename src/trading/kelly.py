from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.trading.portfolio import Portfolio


@dataclass(frozen=True)
class KellyResult:
    win_rate: float
    avg_win: float
    avg_loss: float
    kelly_fraction: float
    half_kelly: float
    recommended_pct: float


def compute_kelly(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
) -> KellyResult:
    if avg_loss_pct == 0 or win_rate <= 0 or win_rate >= 1:
        return KellyResult(
            win_rate=win_rate,
            avg_win=avg_win_pct,
            avg_loss=avg_loss_pct,
            kelly_fraction=0.0,
            half_kelly=0.0,
            recommended_pct=0.0,
        )

    b = avg_win_pct / abs(avg_loss_pct)
    p = win_rate
    q = 1 - p

    kelly = (b * p - q) / b

    kelly = max(0.0, min(1.0, kelly))
    half = kelly / 2

    return KellyResult(
        win_rate=win_rate,
        avg_win=avg_win_pct,
        avg_loss=avg_loss_pct,
        kelly_fraction=kelly,
        half_kelly=half,
        recommended_pct=half,
    )


def kelly_position_size(
    portfolio: Portfolio,
    price: Decimal,
    kelly_result: KellyResult,
    max_position_pct: float = 0.05,
) -> int:
    if price <= 0 or kelly_result.recommended_pct <= 0:
        return 0

    kelly_cap = min(kelly_result.recommended_pct, max_position_pct)
    max_value = portfolio.total_value * Decimal(str(kelly_cap))
    shares = int(max_value / price)
    return max(0, shares)


def compute_kelly_from_trades(
    pnl_pcts: list[float],
) -> KellyResult:
    if not pnl_pcts:
        return KellyResult(0, 0, 0, 0, 0, 0)

    wins = [p for p in pnl_pcts if p > 0]
    losses = [p for p in pnl_pcts if p <= 0]

    win_rate = len(wins) / len(pnl_pcts) if pnl_pcts else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0

    return compute_kelly(win_rate, avg_win, avg_loss)
