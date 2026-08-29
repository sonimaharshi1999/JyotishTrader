from __future__ import annotations

import logging
from decimal import Decimal

import numpy as np
import pandas as pd

from src.trading.portfolio import Portfolio

logger = logging.getLogger(__name__)


def compute_atr(df: pd.DataFrame, window: int = 14) -> float:
    if len(df) < window + 1:
        return 0.0
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.rolling(window=window).mean().iloc[-1]
    return float(atr) if not pd.isna(atr) else 0.0


def volatility_adjusted_shares(
    portfolio: Portfolio,
    current_price: Decimal,
    atr: float,
    max_position_pct: float = 0.05,
    risk_per_trade_pct: float = 0.01,
) -> int:
    if atr <= 0 or float(current_price) <= 0:
        return 0

    risk_amount = float(portfolio.total_value) * risk_per_trade_pct
    shares_by_risk = int(risk_amount / atr)

    max_value = float(portfolio.total_value) * max_position_pct
    shares_by_cap = int(max_value / float(current_price))

    shares = min(shares_by_risk, shares_by_cap)
    return max(0, shares)


def compute_historical_volatility(df: pd.DataFrame, window: int = 20) -> float:
    if len(df) < window + 1:
        return 0.0
    log_returns = np.log(df["Close"] / df["Close"].shift(1)).dropna()
    if len(log_returns) < window:
        return 0.0
    vol = log_returns.rolling(window=window).std().iloc[-1]
    annualized = vol * np.sqrt(252)
    return float(annualized) if not np.isnan(annualized) else 0.0
