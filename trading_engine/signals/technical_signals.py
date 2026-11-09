"""signals/technical_signals.py — Reusable True/False conditions from Family A.

Each function takes the latest bar row (a pandas Series / dict-like object
produced by the indicator layer) and returns a boolean. These are the atomic
building blocks that strategies combine into triggers + filters.

Zero look-ahead: each condition reads only the current row's already-computed
indicator values — never future rows.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _f(row: Any, name: str) -> float:
    """Fetch a numeric feature from a row (Series or dict)."""
    if isinstance(row, pd.Series):
        return float(row[name])
    return float(row[name])  # type: ignore[index]


# --------------------------------------------------------------------------- #
# Trend signals
# --------------------------------------------------------------------------- #
def ema_fast_cross_above(row: Any, ema_fast_col: str, ema_slow_col: str,
                         prev_row: Any | None = None) -> bool:
    """True when fast EMA crossed above slow EMA on the current bar.

    Requires the previous bar's values to detect the cross (prev fast <= prev
    slow AND curr fast > curr slow). If prev_row is None, falls back to
    fast > slow on the current bar only.
    """
    fast_now = _f(row, ema_fast_col)
    slow_now = _f(row, ema_slow_col)
    if prev_row is None:
        return fast_now > slow_now
    fast_prev = _f(prev_row, ema_fast_col)
    slow_prev = _f(prev_row, ema_slow_col)
    return fast_prev <= slow_prev and fast_now > slow_now


def ema_fast_cross_below(row: Any, ema_fast_col: str, ema_slow_col: str,
                         prev_row: Any | None = None) -> bool:
    """True when fast EMA crossed below slow EMA on the current bar."""
    fast_now = _f(row, ema_fast_col)
    slow_now = _f(row, ema_slow_col)
    if prev_row is None:
        return fast_now < slow_now
    fast_prev = _f(prev_row, ema_fast_col)
    slow_prev = _f(prev_row, ema_slow_col)
    return fast_prev >= slow_prev and fast_now < slow_now


def is_ema_bull_trend(row: Any, close_col: str = "close",
                      ema_fast_col: str = "ema_fast",
                      ema_slow_col: str = "ema_slow") -> bool:
    """True when close > fast EMA > slow EMA (bullish alignment)."""
    return _f(row, close_col) > _f(row, ema_fast_col) > _f(row, ema_slow_col)


def is_ema_bear_trend(row: Any, close_col: str = "close",
                      ema_fast_col: str = "ema_fast",
                      ema_slow_col: str = "ema_slow") -> bool:
    """True when close < fast EMA < slow EMA (bearish alignment)."""
    return _f(row, close_col) < _f(row, ema_fast_col) < _f(row, ema_slow_col)


# --------------------------------------------------------------------------- #
# Momentum signals
# --------------------------------------------------------------------------- #
def rsi_oversold(row: Any, rsi_col: str = "rsi", threshold: float = 30.0) -> bool:
    """True when RSI is at/below the oversold threshold."""
    return _f(row, rsi_col) <= threshold


def rsi_overbought(row: Any, rsi_col: str = "rsi", threshold: float = 70.0) -> bool:
    """True when RSI is at/above the overbought threshold."""
    return _f(row, rsi_col) >= threshold


def rsi_below(row: Any, rsi_col: str = "rsi", threshold: float = 50.0) -> bool:
    return _f(row, rsi_col) < threshold


def rsi_above(row: Any, rsi_col: str = "rsi", threshold: float = 50.0) -> bool:
    return _f(row, rsi_col) > threshold


# --------------------------------------------------------------------------- #
# Volatility signals
# --------------------------------------------------------------------------- #
def atr_above_threshold(row: Any, atr_col: str, atr_sma_col: str,
                        multiplier: float = 1.15) -> bool:
    """True when ATR is expanding vs its own SMA (volatility filter)."""
    return _f(row, atr_col) > _f(row, atr_sma_col) * multiplier


def atr_below_threshold(row: Any, atr_col: str, atr_sma_col: str,
                        multiplier: float = 0.85) -> bool:
    """True when ATR is contracted vs its own SMA (low-volatility gate)."""
    return _f(row, atr_col) < _f(row, atr_sma_col) * multiplier


def price_touches_bollinger_lower(row: Any, close_col: str = "close",
                                  bb_lower_col: str = "bb_lower") -> bool:
    """True when price is at/below the lower Bollinger Band (mean-reversion long setup)."""
    return _f(row, close_col) <= _f(row, bb_lower_col)


def price_touches_bollinger_upper(row: Any, close_col: str = "close",
                                  bb_upper_col: str = "bb_upper") -> bool:
    """True when price is at/above the upper Bollinger Band (mean-reversion short setup)."""
    return _f(row, close_col) >= _f(row, bb_upper_col)


def close_above_upper_band(row: Any, close_col: str = "close",
                           bb_upper_col: str = "bb_upper") -> bool:
    return _f(row, close_col) > _f(row, bb_upper_col)


def close_below_lower_band(row: Any, close_col: str = "close",
                           bb_lower_col: str = "bb_lower") -> bool:
    return _f(row, close_col) < _f(row, bb_lower_col)


# --------------------------------------------------------------------------- #
# Supertrend / Donchian
# --------------------------------------------------------------------------- #
def supertrend_uptrend(row: Any, direction_col: str = "supertrend_direction") -> bool:
    """True when Supertrend direction is +1 (uptrend)."""
    return _f(row, direction_col) == 1


def supertrend_downtrend(row: Any, direction_col: str = "supertrend_direction") -> bool:
    """True when Supertrend direction is -1 (downtrend)."""
    return _f(row, direction_col) == -1


def price_above_supertrend(row: Any, close_col: str = "close",
                           st_col: str = "supertrend") -> bool:
    return _f(row, close_col) > _f(row, st_col)


def price_below_supertrend(row: Any, close_col: str = "close",
                           st_col: str = "supertrend") -> bool:
    return _f(row, close_col) < _f(row, st_col)


def donchian_breakout_up(row: Any, high_col: str = "high",
                         donchian_upper_col: str = "donchian_upper",
                         prev_row: Any | None = None) -> bool:
    """True when price breaks above the Donchian upper channel."""
    now = _f(row, high_col)
    upper = _f(row, donchian_upper_col)
    if prev_row is None:
        return now > upper
    prev_high = _f(prev_row, high_col)
    prev_upper = _f(prev_row, donchian_upper_col)
    return prev_high <= prev_upper and now > upper


def donchian_breakout_down(row: Any, low_col: str = "low",
                           donchian_lower_col: str = "donchian_lower",
                           prev_row: Any | None = None) -> bool:
    """True when price breaks below the Donchian lower channel."""
    now = _f(row, low_col)
    lower = _f(row, donchian_lower_col)
    if prev_row is None:
        return now < lower
    prev_low = _f(prev_row, low_col)
    prev_lower = _f(prev_row, donchian_lower_col)
    return prev_low >= prev_lower and now < lower


def price_above_hma(row: Any, hma_col: str = "hma", close_col: str = "close") -> bool:
    """True when price is above the Hull Moving Average (bullish bias)."""
    return _f(row, close_col) > _f(row, hma_col)


def price_below_hma(row: Any, hma_col: str = "hma", close_col: str = "close") -> bool:
    """True when price is below the Hull Moving Average (bearish bias)."""
    return _f(row, close_col) < _f(row, hma_col)


__all__ = [
    "ema_fast_cross_above",
    "ema_fast_cross_below",
    "is_ema_bull_trend",
    "is_ema_bear_trend",
    "rsi_oversold",
    "rsi_overbought",
    "rsi_below",
    "rsi_above",
    "atr_above_threshold",
    "atr_below_threshold",
    "price_touches_bollinger_lower",
    "price_touches_bollinger_upper",
    "close_above_upper_band",
    "close_below_lower_band",
    "supertrend_uptrend",
    "supertrend_downtrend",
    "price_above_supertrend",
    "price_below_supertrend",
    "donchian_breakout_up",
    "donchian_breakout_down",
    "price_above_hma",
    "price_below_hma",
]
