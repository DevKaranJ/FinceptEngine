"""signals/structure_signals.py — Reusable True/False conditions from Family C.

Price Action / Market Structure signals:
  • PDH/PDL/PDC level tests (price at prior day high/low/close)
  • orb_breakout_up / orb_breakout_down (Opening Range breakout)
  • tl_third_touch_bounce / tl_break (Dynamic Trendline touches)
  • fvg_retest_bull / fvg_retest_bear (Fair Value Gap retest)
  • ob_test_bull / ob_test_bear (Order Block test)
  • liquidity_sweep_bull / liquidity_sweep_bear
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _f(row: Any, name: str) -> float:
    if isinstance(row, pd.Series):
        return float(row[name])
    return float(row[name])  # type: ignore[index]


# --------------------------------------------------------------------------- #
# Prior Day High / Low / Close signals
# --------------------------------------------------------------------------- #
def price_at_pdh(row: Any, high_col: str = "high", low_col: str = "low",
                 close_col: str = "close", pdh_col: str = "pdh",
                 tolerance_pct: float = 0.001) -> bool:
    """True when price is testing the Prior Day High (within tolerance)."""
    tol = _f(row, pdh_col) * tolerance_pct
    return (_f(row, high_col) >= _f(row, pdh_col) - tol
            and _f(row, low_col) <= _f(row, pdh_col) + tol)


def price_at_pdl(row: Any, high_col: str = "high", low_col: str = "low",
                 close_col: str = "close", pdl_col: str = "pdl",
                 tolerance_pct: float = 0.001) -> bool:
    """True when price is testing the Prior Day Low (within tolerance)."""
    tol = _f(row, pdl_col) * tolerance_pct
    return (_f(row, high_col) >= _f(row, pdl_col) - tol
            and _f(row, low_col) <= _f(row, pdl_col) + tol)


def price_above_pdh(row: Any, close_col: str = "close", pdh_col: str = "pdh") -> bool:
    """True when close is above the Prior Day High (bullish bias)."""
    return _f(row, close_col) > _f(row, pdh_col)


def price_below_pdl(row: Any, close_col: str = "close", pdl_col: str = "pdl") -> bool:
    """True when close is below the Prior Day Low (bearish bias)."""
    return _f(row, close_col) < _f(row, pdl_col)


# --------------------------------------------------------------------------- #
# Opening Range Breakout (ORB) signals
# --------------------------------------------------------------------------- #
def orb_breakout_up(row: Any, close_col: str = "close",
                    orh_col: str = "orh", orl_col: str = "orl",
                    prev_row: Any | None = None) -> bool:
    """True when price breaks above the Opening Range High."""
    now = _f(row, close_col)
    orh = _f(row, orh_col)
    if prev_row is None:
        return now > orh
    prev_close = _f(prev_row, close_col)
    return prev_close <= orh and now > orh


def orb_breakout_down(row: Any, close_col: str = "close",
                      orh_col: str = "orh", orl_col: str = "orl",
                      prev_row: Any | None = None) -> bool:
    """True when price breaks below the Opening Range Low."""
    now = _f(row, close_col)
    orl = _f(row, orl_col)
    if prev_row is None:
        return now < orl
    prev_close = _f(prev_row, close_col)
    return prev_close >= orl and now < orl


def price_inside_opening_range(row: Any, high_col: str = "high",
                               low_col: str = "low", orh_col: str = "orh",
                               orl_col: str = "orl") -> bool:
    """True when the bar is entirely inside the opening range (chop)."""
    return _f(row, high_col) <= _f(row, orh_col) and _f(row, low_col) >= _f(row, orl_col)


# --------------------------------------------------------------------------- #
# Dynamic Trendline signals
# --------------------------------------------------------------------------- #
def tl_third_touch_bounce(row: Any, close_col: str = "close",
                          tl_support_col: str = "tl_support",
                          tl_touches_col: str = "tl_touches") -> bool:
    """True when price bounces off a trendline with >= 3 touches (support)."""
    return (_f(row, tl_touches_col) >= 3
            and _f(row, close_col) >= _f(row, tl_support_col))


def tl_third_touch_rejection(row: Any, close_col: str = "close",
                             tl_resistance_col: str = "tl_resistance",
                             tl_touches_col: str = "tl_touches") -> bool:
    """True when price rejects a resistance trendline with >= 3 touches."""
    return (_f(row, tl_touches_col) >= 3
            and _f(row, close_col) <= _f(row, tl_resistance_col))


def tl_break_up(row: Any, close_col: str = "close",
                tl_resistance_col: str = "tl_resistance") -> bool:
    """True when price breaks above a dynamic resistance trendline."""
    return _f(row, close_col) > _f(row, tl_resistance_col)


def tl_break_down(row: Any, close_col: str = "close",
                  tl_support_col: str = "tl_support") -> bool:
    """True when price breaks below a dynamic support trendline."""
    return _f(row, close_col) < _f(row, tl_support_col)


# --------------------------------------------------------------------------- #
# Fair Value Gap (FVG) signals
# --------------------------------------------------------------------------- #
def fvg_retest_bull(row: Any, close_col: str = "close",
                    fvg_bull_top_col: str = "fvg_bull_top",
                    fvg_bull_bottom_col: str = "fvg_bull_bottom",
                    fvg_bull_active_col: str = "fvg_bull_active") -> bool:
    """True when price retraces into an unfilled bullish FVG (long setup)."""
    return (_f(row, fvg_bull_active_col) == 1.0
            and _f(row, fvg_bull_bottom_col) <= _f(row, close_col)
            <= _f(row, fvg_bull_top_col))


def fvg_retest_bear(row: Any, close_col: str = "close",
                    fvg_bear_top_col: str = "fvg_bear_top",
                    fvg_bear_bottom_col: str = "fvg_bear_bottom",
                    fvg_bear_active_col: str = "fvg_bear_active") -> bool:
    """True when price retraces into an unfilled bearish FVG (short setup)."""
    return (_f(row, fvg_bear_active_col) == 1.0
            and _f(row, fvg_bear_bottom_col) <= _f(row, close_col)
            <= _f(row, fvg_bear_top_col))


def fvg_filled_bull(row: Any, close_col: str = "close",
                    fvg_bull_bottom_col: str = "fvg_bull_bottom") -> bool:
    """True when price has fallen below a bullish FVG (gap filled — bias shift)."""
    return _f(row, close_col) < _f(row, fvg_bull_bottom_col)


def fvg_filled_bear(row: Any, close_col: str = "close",
                    fvg_bear_top_col: str = "fvg_bear_top") -> bool:
    """True when price has risen above a bearish FVG (gap filled — bias shift)."""
    return _f(row, close_col) > _f(row, fvg_bear_top_col)


# --------------------------------------------------------------------------- #
# Order Block signals
# --------------------------------------------------------------------------- #
def ob_test_bull(row: Any, close_col: str = "close",
                 ob_bull_top_col: str = "ob_bull_top",
                 ob_bull_bottom_col: str = "ob_bull_bottom",
                 ob_bull_active_col: str = "ob_bull_active") -> bool:
    """True when price tests an unmitigated bullish Order Block (demand zone)."""
    return (_f(row, ob_bull_active_col) == 1.0
            and _f(row, ob_bull_bottom_col) <= _f(row, close_col)
            <= _f(row, ob_bull_top_col))


def ob_test_bear(row: Any, close_col: str = "close",
                 ob_bear_top_col: str = "ob_bear_top",
                 ob_bear_bottom_col: str = "ob_bear_bottom",
                 ob_bear_active_col: str = "ob_bear_active") -> bool:
    """True when price tests an unmitigated bearish Order Block (supply zone)."""
    return (_f(row, ob_bear_active_col) == 1.0
            and _f(row, ob_bear_bottom_col) <= _f(row, close_col)
            <= _f(row, ob_bear_top_col))


def ob_mitigated_bull(row: Any, close_col: str = "close",
                      ob_bull_bottom_col: str = "ob_bull_bottom") -> bool:
    """True when price has broken below a bullish OB (mitigated)."""
    return _f(row, close_col) < _f(row, ob_bull_bottom_col)


def ob_mitigated_bear(row: Any, close_col: str = "close",
                      ob_bear_top_col: str = "ob_bear_top") -> bool:
    """True when price has broken above a bearish OB (mitigated)."""
    return _f(row, close_col) > _f(row, ob_bear_top_col)


# --------------------------------------------------------------------------- #
# Liquidity Sweep signals
# --------------------------------------------------------------------------- #
def liquidity_sweep_bull(row: Any, sweep_bull_col: str = "sweep_bull") -> bool:
    """True on the reversal-confirmation bar of a bullish liquidity sweep."""
    return _f(row, sweep_bull_col) == 1.0


def liquidity_sweep_bear(row: Any, sweep_bear_col: str = "sweep_bear") -> bool:
    """True on the reversal-confirmation bar of a bearish liquidity sweep."""
    return _f(row, sweep_bear_col) == 1.0


__all__ = [
    "price_at_pdh",
    "price_at_pdl",
    "price_above_pdh",
    "price_below_pdl",
    "orb_breakout_up",
    "orb_breakout_down",
    "price_inside_opening_range",
    "tl_third_touch_bounce",
    "tl_third_touch_rejection",
    "tl_break_up",
    "tl_break_down",
    "fvg_retest_bull",
    "fvg_retest_bear",
    "fvg_filled_bull",
    "fvg_filled_bear",
    "ob_test_bull",
    "ob_test_bear",
    "ob_mitigated_bull",
    "ob_mitigated_bear",
    "liquidity_sweep_bull",
    "liquidity_sweep_bear",
]
