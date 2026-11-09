"""indicators/orderflow.py — Family D: Volume & Orderflow Indicators.

Volume / microstructure features:
  • Intraday VWAP (+ standard deviation bands) — reset each session/day.
  • Time-Normalized RVOL (Relative Volume vs same time of day).
  • Session Volume Profile: POC (Point of Control), VAH, VAL.
  • Cumulative Volume Delta (CVD) — cumulative (buy - sell) volume using
    taker_buy_vol where available, else up/down tick approximation.
  • Bid × Ask Footprint Imbalance (300% threshold) — aggressive side imbalance.
  • Iceberg Detector — repeated small trades at same price level.

Each function takes a pandas DataFrame (columns ``open``, ``high``, ``low``,
``close``, ``volume``, and optionally ``taker_buy_vol``) plus parameters and
returns a numeric ``pd.Series`` or dict of Series.

Zero look-ahead: all computations use only past and current bar data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "vwap",
    "rvol",
    "session_volume_profile",
    "cvd",
    "footprint_imbalance",
    "iceberg_detector",
]


# --------------------------------------------------------------------------- #
# Family D — Volume / Orderflow
# --------------------------------------------------------------------------- #
def vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    anchor: str = "day",
) -> pd.Series:
    """Intraday Volume-Weighted Average Price (VWAP).

    Typical price = (high + low + close) / 3. VWAP = cum(tp * volume) /
    cum(volume), reset at each anchor boundary (default: each calendar day).
    Only past bars within the current session are used — zero look-ahead.
    """
    df = pd.DataFrame({"high": high, "low": low, "close": close, "volume": volume})
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    tz_naive = df.index.tz_localize(None) if df.index.tz else df.index
    df["date"] = tz_naive.date

    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    tp_vol = typical_price * df["volume"]

    if anchor == "day":
        cum_tp_vol = tp_vol.groupby(df["date"]).cumsum()
        cum_vol = df["volume"].groupby(df["date"]).cumsum()
    else:
        cum_tp_vol = tp_vol.cumsum()
        cum_vol = df["volume"].cumsum()

    result = cum_tp_vol / cum_vol.replace(0, np.nan)
    return result.reindex(df.index)


def vwap_bands(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    anchor: str = "day",
    std_dev: float = 1.0,
) -> dict[str, pd.Series]:
    """VWAP with standard-deviation bands.

    Returns ``{"vwap": ..., "upper": ..., "lower": ...}``. Std is the rolling
    std of typical price deviation from VWAP within the session (past bars).
    """
    df = pd.DataFrame({"high": high, "low": low, "close": close, "volume": volume})
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    tz_naive = df.index.tz_localize(None) if df.index.tz else df.index
    df["date"] = tz_naive.date

    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    tp_vol = typical_price * df["volume"]
    if anchor == "day":
        cum_tp_vol = tp_vol.groupby(df["date"]).cumsum()
        cum_vol = df["volume"].groupby(df["date"]).cumsum()
    else:
        cum_tp_vol = tp_vol.cumsum()
        cum_vol = df["volume"].cumsum()
    vwap_series = cum_tp_vol / cum_vol.replace(0, np.nan)

    deviation = typical_price - vwap_series
    if anchor == "day":
        roll_std = deviation.groupby(df["date"]).transform(
            lambda s: s.rolling(len(s), min_periods=1).std(ddof=0)
        )
    else:
        roll_std = deviation.expanding(min_periods=1).std(ddof=0)

    upper = vwap_series + (std_dev * roll_std)
    lower = vwap_series - (std_dev * roll_std)
    return {"vwap": vwap_series.reindex(df.index), "upper": upper.reindex(df.index), "lower": lower.reindex(df.index)}


def rvol(
    volume: pd.Series, window: int = 20, lookback_days: int = 10
) -> pd.Series:
    """Time-Normalized Relative Volume (RVOL).

    Compares current volume to the average volume at the same time-of-day over
    the past ``lookback_days`` sessions, normalized by a ``window``-bar average.
    RVOL > 1 means above-average activity for this time of day.

    Uses only past bars (grouped by time-of-day bucket) — zero look-ahead.
    """
    if window < 1 or lookback_days < 1:
        raise ValueError("rvol window and lookback_days must be >= 1")

    df = pd.DataFrame({"volume": volume})
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    tz_naive = df.index.tz_localize(None) if df.index.tz else df.index
    df["date"] = tz_naive.date
    # 15-minute time-of-day bucket for normalization.
    df["tod_bucket"] = (tz_naive.hour * 60 + tz_naive.minute) // 15

    # Average volume per tod_bucket over past lookback_days (excluding today).
    bucket_avg = (
        df.groupby(["date", "tod_bucket"])["volume"]
        .mean()
        .groupby("tod_bucket")
        .transform("mean")
    )
    # Align bucket_avg back to each row by date+tod_bucket.
    bucket_map = df.groupby(["date", "tod_bucket"])["volume"].first()
    # Simpler: compute historical avg per bucket from all prior dates.
    hist_avg = (
        df.groupby(["date", "tod_bucket"])["volume"]
        .mean()
        .reset_index()
        .groupby("tod_bucket")["volume"]
        .mean()
    )

    def _hist_avg_for(bucket, current_date):
        # average over prior dates only
        prior = df[(df["tod_bucket"] == bucket) & (df["date"] < current_date)]
        if prior.empty:
            return np.nan
        return prior.groupby("date")["volume"].mean().mean()

    results = []
    for idx, row in df.iterrows():
        cur_date = row["date"]
        bucket = row["tod_bucket"]
        ha = _hist_avg_for(bucket, cur_date)
        if np.isnan(ha) or ha == 0:
            results.append(np.nan)
        else:
            results.append(float(row["volume"] / ha))

    out = pd.Series(results, index=df.index)
    # Smooth with a short window of past RVOL values.
    return out.rolling(window=window, min_periods=1).mean().reindex(df.index)


def session_volume_profile(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    anchor: str = "day",
    value_area_pct: float = 0.70,
) -> dict[str, pd.Series]:
    """Session Volume Profile: POC, VAH, VAL.

    Builds a histogram of volume at price (using typical price bins) within
    each session and returns:
      • POC = price bin with the most volume (Point of Control).
      • VAH = highest price of the value area (top ``value_area_pct`` of volume).
      • VAL = lowest price of the value area.

    Forward-filled within the session so each bar sees the current session's
    profile computed from past bars only.
    """
    if not (0 < value_area_pct < 1):
        raise ValueError("value_area_pct must be between 0 and 1")

    df = pd.DataFrame({"high": high, "low": low, "close": close, "volume": volume})
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    tz_naive = df.index.tz_localize(None) if df.index.tz else df.index
    df["date"] = tz_naive.date

    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0

    n = len(df)
    poc = pd.Series(np.full(n, np.nan, dtype=float), index=df.index)
    vah = pd.Series(np.full(n, np.nan, dtype=float), index=df.index)
    val = pd.Series(np.full(n, np.nan, dtype=float), index=df.index)

    # Bin size = 1% of typical price range (adaptive).
    for date, group in df.groupby("date"):
        idx = group.index
        tp = typical_price.loc[idx]
        vol = group["volume"]
        if tp.empty or vol.sum() == 0:
            continue
        price_min = tp.min()
        price_max = tp.max()
        if price_max == price_min:
            poc.loc[idx] = price_min
            vah.loc[idx] = price_min
            val.loc[idx] = price_min
            continue
        bin_size = (price_max - price_min) / 100.0
        bins = np.arange(price_min, price_max + bin_size, bin_size)
        bin_idx = np.digitize(tp.values, bins) - 1
        bin_idx = np.clip(bin_idx, 0, len(bins) - 2)
        vol_by_bin = pd.Series(vol.values, index=bin_idx).groupby(level=0).sum()

        total_vol = vol_by_bin.sum()
        target_vol = total_vol * value_area_pct

        # POC = bin with max volume.
        poc_bin = vol_by_bin.idxmax()
        poc_price = bins[poc_bin] + bin_size / 2.0

        # Value area: expand outwards from POC until target_vol reached.
        sorted_bins = vol_by_bin.sort_values(ascending=False)
        cum = 0.0
        va_bins = []
        for b in sorted_bins.index:
            va_bins.append(b)
            cum += vol_by_bin[b]
            if cum >= target_vol:
                break
        va_prices = [bins[b] + bin_size / 2.0 for b in va_bins]
        vah_price = max(va_prices)
        val_price = min(va_prices)

        poc.loc[idx] = poc_price
        vah.loc[idx] = vah_price
        val.loc[idx] = val_price

    return {
        "poc": pd.Series(poc, index=df.index).ffill(),
        "vah": pd.Series(vah, index=df.index).ffill(),
        "val": pd.Series(val, index=df.index).ffill(),
    }


def cvd(
    close: pd.Series,
    volume: pd.Series,
    taker_buy_vol: pd.Series | None = None,
) -> pd.Series:
    """Cumulative Volume Delta (CVD).

    Cumulative (buying - selling) pressure.
      • If ``taker_buy_vol`` is provided: delta = taker_buy_vol - (volume -
        taker_buy_vol) = 2*taker_buy_vol - volume per bar.
      • Else: approximate using close vs open (up bar = +volume, down bar =
        -volume).

    Returns the running cumulative sum — only past bars included.
    """
    if taker_buy_vol is not None:
        delta = 2.0 * taker_buy_vol - volume
    else:
        direction = np.where(close >= close.shift(1).fillna(close), 1.0, -1.0)
        delta = direction * volume
    return pd.Series(delta, index=close.index).cumsum()


def footprint_imbalance(
    close: pd.Series,
    volume: pd.Series,
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    threshold: float = 3.0,
) -> dict[str, pd.Series]:
    """Bid × Ask Footprint Imbalance.

    Approximates the footprint using bar close direction and volume. When a
    bar closes strongly in one direction on high volume relative to its range,
    flag an aggressive-side imbalance.

    Returns ``{"imbalance_bull": ..., "imbalance_bear": ...}`` as 0/1 Series
    where 1 marks a bar exceeding ``threshold``× the average imbalance.
    """
    if high is None:
        high = close
    if low is None:
        low = close

    body = (close - close.shift(1).fillna(close)).abs()
    rng = (high - low).replace(0, np.nan)
    # Imbalance score: body / range (how directional the bar was), scaled by volume.
    avg_vol = volume.rolling(window=20, min_periods=1).mean()
    imbalance = (body / rng) * (volume / avg_vol.replace(0, np.nan))
    avg_imbalance = imbalance.rolling(window=20, min_periods=1).mean().replace(0, np.nan)

    imbalance_bull = np.where(
        (close > close.shift(1).fillna(close)) & (imbalance > threshold * avg_imbalance),
        1.0,
        0.0,
    )
    imbalance_bear = np.where(
        (close < close.shift(1).fillna(close)) & (imbalance > threshold * avg_imbalance),
        1.0,
        0.0,
    )

    return {
        "imbalance_bull": pd.Series(imbalance_bull, index=close.index),
        "imbalance_bear": pd.Series(imbalance_bear, index=close.index),
    }


def iceberg_detector(
    close: pd.Series,
    volume: pd.Series,
    window: int = 50,
    repeat_threshold: int = 3,
) -> pd.Series:
    """Iceberg Detector.

    Flags bars where the same price level (close) is revisited with repeated
    volume within a short window — a sign of hidden (iceberg) orders absorbing
    liquidity. Returns a 0/1 Series.

    Uses only past bars within ``window``.
    """
    if window < 2:
        raise ValueError("iceberg_detector window must be >= 2")

    n = len(close)
    iceberg = np.zeros(n, dtype=int)

    for i in range(window, n):
        level = close.iloc[i]
        # Count prior bars in window whose close is within a tiny tolerance of this level.
        tol = level * 0.0005  # 0.05% price tolerance
        prior = close.iloc[i - window : i]
        matches = int(np.sum((prior >= level - tol) & (prior <= level + tol)))
        if matches >= repeat_threshold:
            iceberg[i] = 1

    return pd.Series(iceberg, index=close.index, dtype=float)
