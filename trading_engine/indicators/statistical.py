"""indicators/statistical.py — Family B: Quantitative & Research-Paper Indicators.

Pure statistical / math features used by quant and research-paper strategies.
Each function takes a pandas Series/DataFrame and parameters and returns a
numeric ``pd.Series``.

Zero look-ahead: every computation uses only rows ``iloc[:t]`` — current and
past bars only. Rolling windows are anchored at ``t``.

Declared dependencies: ``numpy``, ``pandas``, ``scipy.stats``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "rolling_zscore",
    "hurst_exponent",
    "volatility_percentile",
    "linear_regression_slope",
    "relative_strength",
]


# --------------------------------------------------------------------------- #
# Family B — Statistical / Quant
# --------------------------------------------------------------------------- #
def rolling_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """Rolling Z-Score: (value - rolling_mean) / rolling_std over past bars.

    The first ``window - 1`` values are NaN (insufficient history). Uses
    ``min_periods=window`` so no partial-window look-ahead occurs.
    """
    if window < 2:
        raise ValueError("rolling_zscore window must be >= 2")
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std(ddof=0)
    return (series - rolling_mean) / rolling_std.replace(0, np.nan)


def hurst_exponent(series: pd.Series, window: int = 100) -> pd.Series:
    """Hurst Exponent over a rolling window.

    H < 0.5: mean-reverting; H > 0.5: trending; H ≈ 0.5: random walk.
    Computed via the rescaled-range (R/S) method on each past window.
    Returns NaN for the first ``window`` bars.
    """
    if window < 10:
        raise ValueError("hurst_exponent window must be >= 10")

    def _hurst(arr: np.ndarray) -> float:
        n = len(arr)
        if n < 2:
            return np.nan
        # Mean-adjusted cumulative deviations
        mean_adj = arr - arr.mean()
        cum_dev = np.cumsum(mean_adj)
        r = cum_dev.max() - cum_dev.min()
        s = arr.std(ddof=1)
        if s == 0 or r == 0:
            return 0.5
        # R/S across increasing lags
        lags = np.arange(2, n + 1)
        rs_vals = []
        for lag in lags:
            # Split into non-overlapping chunks of size `lag`
            n_chunks = n // lag
            if n_chunks < 2:
                break
            chunks = cum_dev[: n_chunks * lag].reshape(n_chunks, lag)
            arr_chunks = arr[: n_chunks * lag].reshape(n_chunks, lag)
            R = chunks.max(axis=1) - chunks.min(axis=1)
            S = arr_chunks.std(axis=1, ddof=1)
            S = np.where(S == 0, np.nan, S)
            rs_vals.append(np.nanmean(R / S))
        if len(rs_vals) < 2:
            return 0.5
        lags_used = np.arange(2, 2 + len(rs_vals))
        # Linear regression of log(R/S) vs log(lag) -> slope = H
        log_lags = np.log(lags_used)
        log_rs = np.log(rs_vals)
        if np.all(np.isfinite(log_rs)) and np.std(log_lags) > 0:
            slope = np.polyfit(log_lags, log_rs, 1)[0]
            return float(np.clip(slope, 0.0, 1.0))
        return 0.5

    return series.rolling(window=window, min_periods=window).apply(_hurst, raw=True)


def volatility_percentile(series: pd.Series, window: int = 100, lookback: int = 252) -> pd.Series:
    """Rolling Volatility Percentile.

    Computes the rolling standard deviation of returns over ``window`` bars,
    then expresses the current value as a percentile (0–100) of its own
    history over ``lookback`` bars. Used to classify Low/Normal/High vol
    regimes. Only past bars are used.
    """
    if window < 2 or lookback < 2:
        raise ValueError("volatility_percentile window/lookback must be >= 2")
    returns = series.pct_change().fillna(0.0)
    rolling_vol = returns.rolling(window=window, min_periods=window).std(ddof=0)
    # Percentile rank of current rolling_vol within past `lookback` values.
    pct = rolling_vol.rolling(window=lookback, min_periods=lookback).apply(
        lambda x: float(np.nanpercentile(x[:-1], 100 * (np.sum(x[:-1] <= x[-1]) / max(len(x[:-1]), 1)))) if len(x) > 1 else np.nan,
        raw=True,
    )
    return pct


def linear_regression_slope(series: pd.Series, window: int = 20) -> pd.Series:
    """Slope of an OLS linear regression over the past ``window`` bars.

    Positive slope = upward trend over the window; negative = downward.
    Uses only past data (window anchored at current bar, no future rows).
    """
    if window < 2:
        raise ValueError("linear_regression_slope window must be >= 2")
    x = np.arange(window, dtype=float)

    def _slope(arr: np.ndarray) -> float:
        if np.any(~np.isfinite(arr)):
            return np.nan
        y = arr
        x_mean = x.mean()
        y_mean = y.mean()
        denom = np.sum((x - x_mean) ** 2)
        if denom == 0:
            return 0.0
        return float(np.sum((x - x_mean) * (y - y_mean)) / denom)

    return series.rolling(window=window, min_periods=window).apply(_slope, raw=True)


def relative_strength(series_a: pd.Series, series_b: pd.Series, window: int = 20) -> pd.Series:
    """Cross-Asset Relative Strength (RS) = ratio of series_a to series_b.

    Smoothed over ``window`` past bars. series_a / series_b at each bar using
    only current and past values of both series.
    """
    if window < 1:
        raise ValueError("relative_strength window must be >= 1")
    ratio = series_a / series_b.replace(0, np.nan)
    return ratio.rolling(window=window, min_periods=window).mean()
