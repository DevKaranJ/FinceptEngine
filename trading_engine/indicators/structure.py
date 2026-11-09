"""indicators/structure.py — Family C: Price Action & Market Structure.

Pure geometric / structural price levels:
  • Prior Day High / Low / Close (PDH / PDL / PDC)
  • Opening Range High / Low (ORH / ORL)
  • 3-Touch Dynamic Trendlines (TL) — support/resistance touches
  • Fair Value Gaps (FVG) — bullish / bearish imbalance gaps
  • Order Blocks (OB) — bullish / bearish last opposing candle before impulse
  • Liquidity Sweeps — wicks that pierce recent swing highs/lows then reverse

Each function takes a pandas DataFrame (columns ``open``, ``high``, ``low``,
``close``) plus parameters and returns a numeric ``pd.Series`` or dict of
Series/levels.

Zero look-ahead: every level is derived from completed / past bars only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "pdh_pdl_pdc",
    "opening_range",
    "dynamic_trendline",
    "fvg",
    "order_blocks",
    "liquidity_sweep",
]


# --------------------------------------------------------------------------- #
# Family C — Price Structure / Levels
# --------------------------------------------------------------------------- #
def pdh_pdl_pdc(high: pd.Series, low: pd.Series, close: pd.Series) -> dict[str, pd.Series]:
    """Prior Day High / Low / Close.

    For intraday timeframes, these are the previous calendar day's H/L/C,
    carried forward (forward-filled) throughout the current day so every bar
    sees the prior day's levels — no future data.

    Returns ``{"pdh": ..., "pdl": ..., "pdc": ...}``.
    """
    df = pd.DataFrame({"high": high, "low": low, "close": close})
    # Normalize index to a DatetimeIndex so we can group by calendar date.
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    tz_naive = df.index.tz_localize(None) if df.index.tz else df.index
    df["date"] = tz_naive.date

    # Each day's H/L/C, then map the PREVIOUS calendar day's levels onto every
    # bar of the current day (carried forward). shift(1) within each date group
    # is wrong (row-shift); instead we compute daily aggregates then lookup the
    # prior date's aggregate for each bar.
    daily_high = df.groupby("date")["high"].max()
    daily_low = df.groupby("date")["low"].min()
    daily_close = df.groupby("date")["close"].last()

    dates = sorted(daily_high.index)
    prev_day_map = {}
    for i in range(1, len(dates)):
        prev_day_map[dates[i]] = dates[i - 1]

    prev_date = df["date"].map(prev_day_map)
    pdh = prev_date.map(daily_high)
    pdl = prev_date.map(daily_low)
    pdc = prev_date.map(daily_close)

    return {"pdh": pdh, "pdl": pdl, "pdc": pdc}


def opening_range(
    high: pd.Series, low: pd.Series, open_time: str = "09:15", minutes: int = 30
) -> dict[str, pd.Series]:
    """Opening Range High / Low (ORH / ORL).

    For the first ``minutes`` of each session (starting at ``open_time``),
    compute the session's high and low, then forward-fill those levels for the
    rest of the session. Only bars within the opening window contribute.

    Returns ``{"orh": ..., "orl": ...}``.
    """
    df = pd.DataFrame({"high": high, "low": low})
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    tz_naive = df.index.tz_localize(None) if df.index.tz else df.index
    df["date"] = tz_naive.date

    start_minutes = _time_to_minutes(open_time)
    end_minutes = start_minutes + minutes

    def in_opening_window(ts):
        m = ts.hour * 60 + ts.minute
        return start_minutes <= m < end_minutes

    mask = tz_naive.map(in_opening_window)
    or_high = df.loc[mask].groupby("date")["high"].transform("max")
    or_low = df.loc[mask].groupby("date")["low"].transform("min")

    # Forward fill the OR levels across the whole session day.
    orh = or_high.groupby(df["date"]).ffill()
    orl = or_low.groupby(df["date"]).ffill()

    return {"orh": orh.reindex(df.index), "orl": orl.reindex(df.index)}


def dynamic_trendline(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int = 50, min_touches: int = 3
) -> dict[str, pd.Series]:
    """3-Touch Dynamic Trendlines.

    Fits a linear regression slope over the past ``window`` bars and detects
    whether price is respecting a dynamic support (uptrend) or resistance
    (downtrend) line. Returns the trendline level and a touch count.

    Returns ``{"tl_support": ..., "tl_resistance": ..., "tl_touches": ...}``.
    """
    if window < min_touches:
        raise ValueError("dynamic_trendline window must be >= min_touches")

    x = np.arange(window, dtype=float)

    def _fit(arr_high: np.ndarray, arr_low: np.ndarray):
        # Support line fit to lows; resistance fit to highs.
        def slope_intercept(y):
            if np.any(~np.isfinite(y)):
                return np.nan, np.nan
            x_mean = x.mean()
            y_mean = y.mean()
            denom = np.sum((x - x_mean) ** 2)
            if denom == 0:
                return 0.0, y_mean
            slope = np.sum((x - x_mean) * (y - y_mean)) / denom
            intercept = y_mean - slope * x_mean
            return float(slope), float(intercept)

        return slope_intercept(arr_low), slope_intercept(arr_high)

    support_fit = low.rolling(window=window, min_periods=window).apply(
        lambda a: _fit(a, a)[0][0], raw=True
    )
    resistance_fit = high.rolling(window=window, min_periods=window).apply(
        lambda a: _fit(a, a)[1][0], raw=True
    )
    support_intercept = low.rolling(window=window, min_periods=window).apply(
        lambda a: _fit(a, a)[0][1], raw=True
    )
    resistance_intercept = high.rolling(window=window, min_periods=window).apply(
        lambda a: _fit(a, a)[1][1], raw=True
    )

    n = len(close)
    tl_support = np.full(n, np.nan, dtype=float)
    tl_resistance = np.full(n, np.nan, dtype=float)
    tl_touches = np.zeros(n, dtype=int)

    for i in range(window - 1, n):
        s_slope = support_fit.iloc[i]
        s_int = support_intercept.iloc[i]
        r_slope = resistance_fit.iloc[i]
        r_int = resistance_intercept.iloc[i]
        if not (np.isfinite(s_slope) and np.isfinite(s_int) and np.isfinite(r_slope) and np.isfinite(r_int)):
            continue
        # Trendline levels at current bar (x = window-1 offset from window start).
        tl_support[i] = s_slope * (window - 1) + s_int
        tl_resistance[i] = r_slope * (window - 1) + r_int

        # Count touches: price wick within a small band of the line.
        band = close.iloc[i] * 0.001  # 0.1% tolerance band
        low_touch = abs(low.iloc[i] - tl_support[i]) <= band
        high_touch = abs(high.iloc[i] - tl_resistance[i]) <= band
        tl_touches[i] = int(low_touch) + int(high_touch)

    return {
        "tl_support": pd.Series(tl_support, index=close.index),
        "tl_resistance": pd.Series(tl_resistance, index=close.index),
        "tl_touches": pd.Series(tl_touches, index=close.index),
    }


def fvg(high: pd.Series, low: pd.Series, close: pd.Series) -> dict[str, pd.Series]:
    """Fair Value Gaps (FVG).

    A 3-candle pattern:
      • Bullish FVG: candle[i-1].low > candle[i+1].high (gap up between them,
        middle candle i is the "FVG candle"). Gap zone = [candle[i+1].high,
        candle[i-1].low].
      • Bearish FVG: candle[i-1].high < candle[i+1].low (gap down). Gap zone =
        [candle[i-1].high, candle[i+1].low].

    Uses shift(1) / shift(-1) relative to the FVG candle — the gap is fully
    formed once candle i+1 closes, so for bar i+1 the levels are known past
    data. Returned Series are aligned so bar T sees gaps formed at or before T.

    Returns ``{"fvg_bull_top": ..., "fvg_bull_bottom": ..., "fvg_bear_top": ...,
    "fvg_bear_bottom": ..., "fvg_bull_active": ..., "fvg_bear_active": ...}``
    where active Series are 1.0 while price is inside/near the unfilled gap.
    """
    n = len(close)
    fvg_bull_top = np.full(n, np.nan, dtype=float)
    fvg_bull_bottom = np.full(n, np.nan, dtype=float)
    fvg_bear_top = np.full(n, np.nan, dtype=float)
    fvg_bear_bottom = np.full(n, np.nan, dtype=float)
    fvg_bull_active = np.zeros(n, dtype=float)
    fvg_bear_active = np.zeros(n, dtype=float)

    # i is the middle (FVG) candle. Gap forms between i-1 and i+1.
    # Once candle i+1 closes (bar i+1), the gap is known past data.
    for i in range(1, n - 1):
        h_prev = high.iloc[i - 1]
        l_prev = low.iloc[i - 1]
        h_next = high.iloc[i + 1]
        l_next = low.iloc[i + 1]

        # Bullish FVG: next candle's low > previous candle's high (gap up).
        if l_next > h_prev:
            # The gap becomes known at bar i+1 (when next candle closes).
            fvg_bull_top[i + 1] = l_prev  # top of gap = prev candle high? actually gap bottom
            fvg_bull_bottom[i + 1] = h_prev
            # correct orientation: bullish gap zone between h_prev and l_next; top=l_next? 
            # We define bull zone [bottom=h_prev, top=l_prev] if l_prev>h_prev... 
            # Let's set: bull_top = max(l_prev, l_next side), bull_bottom = min.
            # Simpler robust: top = max(h_prev, l_next) won't be a gap. Use gap between h_prev and l_next.
            pass
        # Bearish FVG: next candle's high < previous candle's low (gap down).
        if h_next < l_prev:
            pass

    # Recompute cleanly: gap zone is between candle i-1 and candle i+1 extremes.
    for i in range(1, n - 1):
        h_prev = float(high.iloc[i - 1])
        l_prev = float(low.iloc[i - 1])
        h_next = float(high.iloc[i + 1])
        l_next = float(low.iloc[i + 1])

        # Bullish: gap up — previous candle's HIGH < next candle's LOW.
        if h_prev < l_next:
            fvg_bull_bottom[i + 1] = h_prev
            fvg_bull_top[i + 1] = l_next
        # Bearish: gap down — previous candle's LOW > next candle's HIGH.
        if l_prev > h_next:
            fvg_bear_top[i + 1] = l_prev
            fvg_bear_bottom[i + 1] = h_next

    # Active: price currently within/near an unfilled gap (track last unfilled gap).
    last_bull = None
    last_bear = None
    for i in range(n):
        if not np.isnan(fvg_bull_top[i]):
            last_bull = (fvg_bull_bottom[i], fvg_bull_top[i])
        if not np.isnan(fvg_bear_top[i]):
            last_bear = (fvg_bear_bottom[i], fvg_bear_top[i])
        c = float(close.iloc[i])
        if last_bull is not None:
            fvg_bull_active[i] = 1.0 if last_bull[0] <= c <= last_bull[1] else 0.0
            # Gap fills when price returns into it; once filled, deactivate.
            if c <= last_bull[0]:
                last_bull = None
        if last_bear is not None:
            fvg_bear_active[i] = 1.0 if last_bear[0] <= c <= last_bear[1] else 0.0
            if c >= last_bear[1]:
                last_bear = None

    return {
        "fvg_bull_top": pd.Series(fvg_bull_top, index=close.index),
        "fvg_bull_bottom": pd.Series(fvg_bull_bottom, index=close.index),
        "fvg_bear_top": pd.Series(fvg_bear_top, index=close.index),
        "fvg_bear_bottom": pd.Series(fvg_bear_bottom, index=close.index),
        "fvg_bull_active": pd.Series(fvg_bull_active, index=close.index),
        "fvg_bear_active": pd.Series(fvg_bear_active, index=close.index),
    }


def order_blocks(
    high: pd.Series, low: pd.Series, close: pd.Series, lookback: int = 20
) -> dict[str, pd.Series]:
    """Order Blocks (OB).

    A bullish OB = the last bearish (down) candle before a strong upward
    impulse; its [low, high] zone is a future support demand zone.
    A bearish OB = the last bullish (up) candle before a strong downward
    impulse; its [low, high] zone is a future resistance supply zone.

    Impulse strength = close-to-close move exceeding ``lookback``-period ATR
    scaled. Returns the most recent unmitigated OB zone and whether price is
    currently inside it.

    Returns ``{"ob_bull_top": ..., "ob_bull_bottom": ..., "ob_bear_top": ...,
    "ob_bear_bottom": ..., "ob_bull_active": ..., "ob_bear_active": ...}``.
    """
    if lookback < 2:
        raise ValueError("order_blocks lookback must be >= 2")

    # Simple impulse proxy: |close - close.shift(lookback)| > mean body over lookback.
    body = (close - close.shift(1)).abs()
    avg_body = body.rolling(window=lookback, min_periods=lookback).mean()

    n = len(close)
    ob_bull_top = np.full(n, np.nan, dtype=float)
    ob_bull_bottom = np.full(n, np.nan, dtype=float)
    ob_bear_top = np.full(n, np.nan, dtype=float)
    ob_bear_bottom = np.full(n, np.nan, dtype=float)
    ob_bull_active = np.zeros(n, dtype=float)
    ob_bear_active = np.zeros(n, dtype=float)

    last_bull = None
    last_bear = None
    for i in range(lookback, n):
        ab = avg_body.iloc[i]
        if not np.isfinite(ab) or ab == 0:
            continue
        move = float(close.iloc[i] - close.iloc[i - lookback])
        # Upward impulse: last down-candle before it is a bullish OB.
        if move > 2.0 * ab:
            # Scan back from i-1 for the most recent bearish candle
            # (close[j] < close[j-1]) within the lookback window.
            for j in range(i - 1, max(i - lookback - 1, 0), -1):
                if close.iloc[j] < close.iloc[j - 1]:
                    last_bull = (float(low.iloc[j]), float(high.iloc[j]))
                    break
        # Downward impulse: last up-candle before it is a bearish OB.
        elif move < -2.0 * ab:
            for j in range(i - 1, max(i - lookback - 1, 0), -1):
                if close.iloc[j] > close.iloc[j - 1]:
                    last_bear = (float(low.iloc[j]), float(high.iloc[j]))
                    break

        ob_bull_top[i] = last_bull[1] if last_bull else np.nan
        ob_bull_bottom[i] = last_bull[0] if last_bull else np.nan
        ob_bear_top[i] = last_bear[1] if last_bear else np.nan
        ob_bear_bottom[i] = last_bear[0] if last_bear else np.nan

        c = float(close.iloc[i])
        if last_bull is not None:
            ob_bull_active[i] = 1.0 if last_bull[0] <= c <= last_bull[1] else 0.0
            if c <= last_bull[0]:
                last_bull = None  # mitigated
        if last_bear is not None:
            ob_bear_active[i] = 1.0 if last_bear[0] <= c <= last_bear[1] else 0.0
            if c >= last_bear[1]:
                last_bear = None  # mitigated

    return {
        "ob_bull_top": pd.Series(ob_bull_top, index=close.index),
        "ob_bull_bottom": pd.Series(ob_bull_bottom, index=close.index),
        "ob_bear_top": pd.Series(ob_bear_top, index=close.index),
        "ob_bear_bottom": pd.Series(ob_bear_bottom, index=close.index),
        "ob_bull_active": pd.Series(ob_bull_active, index=close.index),
        "ob_bear_active": pd.Series(ob_bear_active, index=close.index),
    }


def liquidity_sweep(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20
) -> dict[str, pd.Series]:
    """Liquidity Sweep detection.

    A bullish liquidity sweep: price makes a new ``window``-bar low (wick
    below recent swing low) but closes back above it — stop-hunt then reversal.
    A bearish liquidity sweep: new ``window``-bar high wick but closes back below.

    Returns ``{"sweep_bull": ..., "sweep_bear": ...}`` as 0/1 Series where 1
    marks the bar that closed back inside (the reversal confirmation bar).
    """
    if window < 2:
        raise ValueError("liquidity_sweep window must be >= 2")

    n = len(close)
    swing_low = low.rolling(window=window, min_periods=window).min()
    swing_high = high.rolling(window=window, min_periods=window).max()

    sweep_bull = np.zeros(n, dtype=float)
    sweep_bear = np.zeros(n, dtype=float)

    for i in range(1, n):
        # Bullish sweep: wick below prior swing low, close above prior swing low.
        prev_swing_low = swing_low.iloc[i - 1]
        if np.isfinite(prev_swing_low) and low.iloc[i] < prev_swing_low and close.iloc[i] > prev_swing_low:
            sweep_bull[i] = 1.0
        # Bearish sweep: wick above prior swing high, close below prior swing high.
        prev_swing_high = swing_high.iloc[i - 1]
        if np.isfinite(prev_swing_high) and high.iloc[i] > prev_swing_high and close.iloc[i] < prev_swing_high:
            sweep_bear[i] = 1.0

    return {
        "sweep_bull": pd.Series(sweep_bull, index=close.index),
        "sweep_bear": pd.Series(sweep_bear, index=close.index),
    }


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _time_to_minutes(t_str: str) -> int:
    """Convert 'HH:MM' to minutes since midnight."""
    parts = t_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])
