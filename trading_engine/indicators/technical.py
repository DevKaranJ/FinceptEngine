"""indicators/technical.py — Family A: Classical Technical Indicators.

Pure-math indicator blocks. Each function takes a pandas DataFrame (columns:
``open``, ``high``, ``low``, ``close``, ``volume``) plus parameters and returns
a numeric ``pd.Series`` (or dict of Series for multi-output indicators such as
Bollinger Bands / MACD / Pivots).

Zero look-ahead: every computation uses only rows ``iloc[:t]`` — current and
past bars only. No ``shift(-1)`` or whole-series unanchored look-ahead is used.

Declared dependencies: ``pandas``, ``numpy``, ``pandas-ta``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# pandas-ta is available in the environment but we implement core indicators
# with pure pandas/numpy so behaviour is deterministic and version-independent.
import pandas_ta as pta  # noqa: F401  (used optionally for cross-checks)

__all__ = [
    "ema",
    "sma",
    "rsi",
    "atr",
    "bollinger_bands",
    "macd",
    "supertrend",
    "pivots",
    "donchian_channels",
    "hma",
]


# --------------------------------------------------------------------------- #
# Family A — Trend / Momentum / Volatility
# --------------------------------------------------------------------------- #
def ema(close: pd.Series, length: int = 20) -> pd.Series:
    """Exponential Moving Average.

    Pure recursive EMA using only past bars. Adjust=False matches the classic
    recursive definition (no look-ahead, no future rows involved).
    """
    if length < 1:
        raise ValueError("ema length must be >= 1")
    return close.ewm(span=length, adjust=False, min_periods=length).mean()


def sma(close: pd.Series, length: int = 20) -> pd.Series:
    """Simple Moving Average over ``length`` past bars (incl. current)."""
    if length < 1:
        raise ValueError("sma length must be >= 1")
    return close.rolling(window=length, min_periods=length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing).

    Uses only past price changes; the first ``length`` values are NaN
    (insufficient history) — never future data.
    """
    if length < 1:
        raise ValueError("rsi length must be >= 1")
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_values = 100.0 - (100.0 / (1.0 + rs))
    return rsi_values


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average True Range (Wilder's smoothing).

    TrueRange = max(high-low, |high-prev_close|, |low-prev_close|).
    Only past bars are used (shift(1) of close is a past bar).
    """
    if length < 1:
        raise ValueError("atr length must be >= 1")
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()


def bollinger_bands(
    close: pd.Series, length: int = 20, std_dev: float = 2.0
) -> dict[str, pd.Series]:
    """Bollinger Bands.

    Returns ``{"upper": ..., "middle": ..., "lower": ...}`` using the rolling
    mean and rolling std of past ``length`` bars.
    """
    if length < 1:
        raise ValueError("bollinger_bands length must be >= 1")
    middle = sma(close, length)
    std = close.rolling(window=length, min_periods=length).std(ddof=0)
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    return {"upper": upper, "middle": middle, "lower": lower}


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, pd.Series]:
    """MACD (Moving Average Convergence Divergence).

    Returns ``{"macd": ..., "signal": ..., "histogram": ...}``. EMAs are purely
    recursive over past bars.
    """
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def supertrend(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, multiplier: float = 3.0
) -> dict[str, pd.Series]:
    """Supertrend indicator.

    Returns ``{"supertrend": ..., "direction": ...}`` where direction is +1
    (uptrend) or -1 (downtrend). Built only from past ATR and close values.
    """
    if period < 1:
        raise ValueError("supertrend period must be >= 1")
    atr_values = atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper_band = hl2 + (multiplier * atr_values)
    lower_band = hl2 - (multiplier * atr_values)

    n = len(close)
    supertrend = np.full(n, np.nan, dtype=float)
    direction = np.full(n, 1, dtype=int)

    for i in range(1, n):
        prev_st = supertrend[i - 1]
        prev_dir = direction[i - 1]
        curr_close = close.iloc[i]
        curr_upper = upper_band.iloc[i]
        curr_lower = lower_band.iloc[i]
        prev_close = close.iloc[i - 1]

        if prev_dir == 1:
            # In uptrend: ST is the lower band unless price closes below it.
            if curr_lower > prev_st or prev_close > curr_lower:
                supertrend[i] = curr_lower
                direction[i] = -1 if curr_close < curr_lower else 1
            else:
                supertrend[i] = prev_st
                direction[i] = 1
        else:
            # In downtrend: ST is the upper band unless price closes above it.
            if curr_upper < prev_st or prev_close < curr_upper:
                supertrend[i] = curr_upper
                direction[i] = 1 if curr_close > curr_upper else -1
            else:
                supertrend[i] = prev_st
                direction[i] = -1

    return {
        "supertrend": pd.Series(supertrend, index=close.index),
        "direction": pd.Series(direction, index=close.index),
    }


def donchian_channels(
    high: pd.Series, low: pd.Series, length: int = 20
) -> dict[str, pd.Series]:
    """Donchian Channels: highest high / lowest low over past ``length`` bars.

    Returns ``{"upper": ..., "lower": ..., "middle": ...}``. Uses rolling
    window over past bars only (current bar included, no future).
    """
    if length < 1:
        raise ValueError("donchian_channels length must be >= 1")
    upper = high.rolling(window=length, min_periods=length).max()
    lower = low.rolling(window=length, min_periods=length).min()
    middle = (upper + lower) / 2.0
    return {"upper": upper, "lower": lower, "middle": middle}


# --------------------------------------------------------------------------- #
# Family A — Pivots (Daily Fibonacci & Classic Pivots)
# --------------------------------------------------------------------------- #
def pivots(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> dict[str, pd.Series]:
    """Classic Floor-Trader Pivots from the previous bar's H/L/C.

    Pivot Point PP = (H + L + C) / 3
    R1 = 2*PP - L,  S1 = 2*PP - H
    R2 = PP + (H - L), S2 = PP - (H - L)
    R3 = PP + 2*(H - L), S3 = PP - 2*(H - L)

    Uses shift(1) on H/L/C so only the previous bar (past) is used — zero
    look-ahead for the current bar's decision.
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    pp = (prev_high + prev_low + prev_close) / 3.0
    r1 = 2 * pp - prev_low
    s1 = 2 * pp - prev_high
    r2 = pp + (prev_high - prev_low)
    s2 = pp - (prev_high - prev_low)
    r3 = pp + 2 * (prev_high - prev_low)
    s3 = pp - 2 * (prev_high - prev_low)

    return {
        "pp": pp,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "s1": s1,
        "s2": s2,
        "s3": s3,
    }


def hma(close: pd.Series, length: int = 20) -> pd.Series:
    """Hull Moving Average (HMA).

    A faster, smoother moving average that reduces lag vs SMA/EMA.
    Formula: HMA = WMA(2 * WMA(n/2) - WMA(n)), then WMA(sqrt(n)) of that result.

    Pure pandas/numpy — deterministic and version-independent.
    Zero look-ahead: uses only past bars (rolling windows incl. current bar).

    Args:
        close: Close price series.
        length: HMA period (must be >= 1).

    Returns:
        pd.Series of HMA values aligned to ``close.index``.
    """
    if length < 1:
        raise ValueError("hma length must be >= 1")

    half = max(1, length // 2)
    sqrt_len = max(1, int(round(length ** 0.5)))

    wma_half = close.rolling(window=half, min_periods=half).mean()
    wma_full = close.rolling(window=length, min_periods=length).mean()

    raw = 2.0 * wma_half - wma_full
    return raw.rolling(window=sqrt_len, min_periods=sqrt_len).mean()
