"""signals/orderflow_signals.py — Reusable True/False conditions from Family D.

Volume / Orderflow signals:
  • above_vwap / below_vwap
  • vwap_band_breach_upper / lower
  • at_session_poc / price_in_value_area (POC, VAH, VAL)
  • rvol_above_2x / rvol_below_0x5
  • footprint_imbalance_bull / bear
  • iceberg_present
  • cvd_rising / cvd_falling
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _f(row: Any, name: str) -> float:
    if isinstance(row, pd.Series):
        return float(row[name])
    return float(row[name])  # type: ignore[index]


# --------------------------------------------------------------------------- #
# VWAP signals
# --------------------------------------------------------------------------- #
def above_vwap(row: Any, close_col: str = "close", vwap_col: str = "vwap") -> bool:
    """True when close is at/above VWAP."""
    return _f(row, close_col) >= _f(row, vwap_col)


def below_vwap(row: Any, close_col: str = "close", vwap_col: str = "vwap") -> bool:
    """True when close is at/below VWAP."""
    return _f(row, close_col) <= _f(row, vwap_col)


def vwap_band_breach_upper(row: Any, close_col: str = "close",
                           vwap_upper_col: str = "vwap_upper") -> bool:
    """True when price breaches above the VWAP + std band."""
    return _f(row, close_col) > _f(row, vwap_upper_col)


def vwap_band_breach_lower(row: Any, close_col: str = "close",
                           vwap_lower_col: str = "vwap_lower") -> bool:
    """True when price breaches below the VWAP - std band."""
    return _f(row, close_col) < _f(row, vwap_lower_col)


# --------------------------------------------------------------------------- #
# Session Volume Profile (POC / VAH / VAL) signals
# --------------------------------------------------------------------------- #
def at_session_poc(row: Any, close_col: str = "close", poc_col: str = "poc",
                   tolerance_pct: float = 0.001) -> bool:
    """True when price is at the session Point of Control (within tolerance)."""
    tol = _f(row, poc_col) * tolerance_pct
    return abs(_f(row, close_col) - _f(row, poc_col)) <= tol


def price_above_vah(row: Any, close_col: str = "close", vah_col: str = "vah") -> bool:
    """True when close is above the Value Area High."""
    return _f(row, close_col) > _f(row, vah_col)


def price_below_val(row: Any, close_col: str = "close", val_col: str = "val") -> bool:
    """True when close is below the Value Area Low."""
    return _f(row, close_col) < _f(row, val_col)


def price_in_value_area(row: Any, close_col: str = "close",
                        vah_col: str = "vah", val_col: str = "val") -> bool:
    """True when close is inside the session Value Area (VAL <= close <= VAH)."""
    return _f(row, val_col) <= _f(row, close_col) <= _f(row, vah_col)


# --------------------------------------------------------------------------- #
# RVOL signals
# --------------------------------------------------------------------------- #
def rvol_above_2x(row: Any, rvol_col: str = "rvol") -> bool:
    """True when RVOL >= 2.0 (double average activity for this time of day)."""
    return _f(row, rvol_col) >= 2.0


def rvol_above_threshold(row: Any, rvol_col: str = "rvol",
                         threshold: float = 1.5) -> bool:
    return _f(row, rvol_col) >= threshold


def rvol_below_threshold(row: Any, rvol_col: str = "rvol",
                         threshold: float = 0.5) -> bool:
    """True when RVOL is below threshold (low activity / chop filter)."""
    return _f(row, rvol_col) <= threshold


# --------------------------------------------------------------------------- #
# Footprint / CVD signals
# --------------------------------------------------------------------------- #
def footprint_imbalance_bull(row: Any, imb_bull_col: str = "imbalance_bull") -> bool:
    """True when a bullish footprint imbalance (aggressive buying) is detected."""
    return _f(row, imb_bull_col) == 1.0


def footprint_imbalance_bear(row: Any, imb_bear_col: str = "imbalance_bear") -> bool:
    """True when a bearish footprint imbalance (aggressive selling) is detected."""
    return _f(row, imb_bear_col) == 1.0


def iceberg_present(row: Any, iceberg_col: str = "iceberg") -> bool:
    """True when an iceberg (hidden order) is detected at the current level."""
    return _f(row, iceberg_col) == 1.0


def cvd_rising(row: Any, cvd_col: str = "cvd",
               prev_row: Any | None = None) -> bool:
    """True when CVD is increasing (buying pressure building)."""
    now = _f(row, cvd_col)
    if prev_row is None:
        return now > 0.0
    return now > _f(prev_row, cvd_col)


def cvd_falling(row: Any, cvd_col: str = "cvd",
                prev_row: Any | None = None) -> bool:
    """True when CVD is decreasing (selling pressure building)."""
    now = _f(row, cvd_col)
    if prev_row is None:
        return now < 0.0
    return now < _f(prev_row, cvd_col)


__all__ = [
    "above_vwap",
    "below_vwap",
    "vwap_band_breach_upper",
    "vwap_band_breach_lower",
    "at_session_poc",
    "price_above_vah",
    "price_below_val",
    "price_in_value_area",
    "rvol_above_2x",
    "rvol_above_threshold",
    "rvol_below_threshold",
    "footprint_imbalance_bull",
    "footprint_imbalance_bear",
    "iceberg_present",
    "cvd_rising",
    "cvd_falling",
]
