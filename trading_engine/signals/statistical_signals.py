"""signals/statistical_signals.py — Reusable True/False conditions from Family B.

Quant / research-paper signals:
  • zscore_below_minus_2 / zscore_above_plus_2 (mean-reversion extremes)
  • hurst_trending_regime / hurst_mean_reverting_regime
  • volatility_expanding / volatility_contracting (volatility percentile)
  • linear_regression_slope positive / negative (trend slope)
  • relative_strength leader / laggard filter
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _f(row: Any, name: str) -> float:
    if isinstance(row, pd.Series):
        return float(row[name])
    return float(row[name])  # type: ignore[index]


# --------------------------------------------------------------------------- #
# Z-Score (mean-reversion) signals
# --------------------------------------------------------------------------- #
def zscore_below_minus_2(row: Any, zscore_col: str = "zscore") -> bool:
    """True when z-score <= -2 (oversold statistical extreme)."""
    return _f(row, zscore_col) <= -2.0


def zscore_above_plus_2(row: Any, zscore_col: str = "zscore") -> bool:
    """True when z-score >= +2 (overbought statistical extreme)."""
    return _f(row, zscore_col) >= 2.0


def zscore_below_threshold(row: Any, zscore_col: str = "zscore",
                           threshold: float = -2.0) -> bool:
    return _f(row, zscore_col) <= threshold


def zscore_above_threshold(row: Any, zscore_col: str = "zscore",
                           threshold: float = 2.0) -> bool:
    return _f(row, zscore_col) >= threshold


def zscore_mean_revert_long(row: Any, zscore_col: str = "zscore") -> bool:
    """True when z-score crossed back above -2 from below (long mean-reversion entry)."""
    return _f(row, zscore_col) >= -2.0


def zscore_mean_revert_short(row: Any, zscore_col: str = "zscore") -> bool:
    """True when z-score crossed back below +2 from above (short mean-reversion entry)."""
    return _f(row, zscore_col) <= 2.0


# --------------------------------------------------------------------------- #
# Hurst Exponent (regime) signals
# --------------------------------------------------------------------------- #
def hurst_trending_regime(row: Any, hurst_col: str = "hurst",
                          trending_threshold: float = 0.55) -> bool:
    """True when H > trending_threshold (market is trending)."""
    return _f(row, hurst_col) > trending_threshold


def hurst_mean_reverting_regime(row: Any, hurst_col: str = "hurst",
                                mr_threshold: float = 0.45) -> bool:
    """True when H < mr_threshold (market is mean-reverting)."""
    return _f(row, hurst_col) < mr_threshold


def hurst_random_walk(row: Any, hurst_col: str = "hurst") -> bool:
    """True when H is approximately 0.5 (random walk / no clear regime)."""
    h = _f(row, hurst_col)
    return 0.45 <= h <= 0.55


# --------------------------------------------------------------------------- #
# Volatility Percentile (regime) signals
# --------------------------------------------------------------------------- #
def volatility_expanding(row: Any, vol_pct_col: str = "volatility_percentile",
                         high_threshold: float = 75.0) -> bool:
    """True when volatility percentile is in the high tier (>=75th pct)."""
    return _f(row, vol_pct_col) >= high_threshold


def volatility_contracting(row: Any, vol_pct_col: str = "volatility_percentile",
                           low_threshold: float = 25.0) -> bool:
    """True when volatility percentile is in the low tier (<=25th pct)."""
    return _f(row, vol_pct_col) <= low_threshold


def volatility_normal(row: Any, vol_pct_col: str = "volatility_percentile") -> bool:
    """True when volatility is in the normal band (25th–75th percentile)."""
    v = _f(row, vol_pct_col)
    return 25.0 < v < 75.0


# --------------------------------------------------------------------------- #
# Linear Regression Slope (trend) signals
# --------------------------------------------------------------------------- #
def slope_positive(row: Any, slope_col: str = "linreg_slope") -> bool:
    """True when the regression slope over the window is positive."""
    return _f(row, slope_col) > 0.0


def slope_negative(row: Any, slope_col: str = "linreg_slope") -> bool:
    """True when the regression slope over the window is negative."""
    return _f(row, slope_col) < 0.0


def slope_strongly_positive(row: Any, slope_col: str = "linreg_slope",
                            threshold: float = 0.0) -> bool:
    return _f(row, slope_col) > threshold


# --------------------------------------------------------------------------- #
# Relative Strength (cross-asset) signals
# --------------------------------------------------------------------------- #
def rs_leader(row: Any, rs_col: str = "relative_strength",
              benchmark_col: str = "relative_strength_benchmark") -> bool:
    """True when the asset's RS is above its benchmark (relative leader)."""
    return _f(row, rs_col) > _f(row, benchmark_col)


def rs_laggard(row: Any, rs_col: str = "relative_strength",
               benchmark_col: str = "relative_strength_benchmark") -> bool:
    """True when the asset's RS is below its benchmark (relative laggard)."""
    return _f(row, rs_col) < _f(row, benchmark_col)


__all__ = [
    "zscore_below_minus_2",
    "zscore_above_plus_2",
    "zscore_below_threshold",
    "zscore_above_threshold",
    "zscore_mean_revert_long",
    "zscore_mean_revert_short",
    "hurst_trending_regime",
    "hurst_mean_reverting_regime",
    "hurst_random_walk",
    "volatility_expanding",
    "volatility_contracting",
    "volatility_normal",
    "slope_positive",
    "slope_negative",
    "slope_strongly_positive",
    "rs_leader",
    "rs_laggard",
]
