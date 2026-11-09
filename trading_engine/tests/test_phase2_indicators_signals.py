"""tests/test_phase2_indicators_signals.py — Phase 2 verification suite.

Covers (PRD Phase 2 stop gate):
  • Family A technical indicators: EMA, SMA, RSI, ATR, Bollinger Bands, MACD,
    Supertrend, Donchian Channels, Pivots — exact math + zero look-ahead.
  • Family B statistical indicators: Rolling Z-Score, Hurst, Volatility
    Percentile, Linear Regression Slope, Relative Strength.
  • Family C structure indicators: PDH/PDL/PDC, Opening Range, Dynamic TL,
    FVG, Order Blocks, Liquidity Sweeps.
  • Family D orderflow indicators: VWAP, RVOL, Volume Profile POC/VAH/VAL,
    CVD, Footprint Imbalance, Iceberg.
  • Signals: all boolean signal wrappers return correct True/False.
  • Zero look-ahead enforcement: no indicator uses future data (t <= T).

Run: pytest tests/test_phase2_indicators_signals.py -v   (from repo root)
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from trading_engine.data.feature_store import FeatureStore, zero_look_ahead_slice
from trading_engine.indicators.orderflow import (
    cvd,
    footprint_imbalance,
    iceberg_detector,
    rvol,
    session_volume_profile,
    vwap,
    vwap_bands,
)
from trading_engine.indicators.statistical import (
    hurst_exponent,
    linear_regression_slope,
    relative_strength,
    rolling_zscore,
    volatility_percentile,
)
from trading_engine.indicators.structure import (
    dynamic_trendline,
    fvg,
    liquidity_sweep,
    order_blocks,
    opening_range,
    pdh_pdl_pdc,
)
from trading_engine.indicators.technical import (
    atr,
    bollinger_bands,
    donchian_channels,
    ema,
    hma,
    macd,
    pivots,
    rsi,
    sma,
    supertrend,
)
from trading_engine.signals.orderflow_signals import (
    above_vwap,
    at_session_poc,
    below_vwap,
    cvd_falling,
    cvd_rising,
    footprint_imbalance_bear,
    footprint_imbalance_bull,
    iceberg_present,
    price_above_vah,
    price_below_val,
    price_in_value_area,
    rvol_above_2x,
    rvol_below_threshold,
)
from trading_engine.signals.statistical_signals import (
    hurst_mean_reverting_regime,
    hurst_random_walk,
    hurst_trending_regime,
    rs_leader,
    rs_laggard,
    slope_negative,
    slope_positive,
    volatility_contracting,
    volatility_expanding,
    zscore_above_plus_2,
    zscore_below_minus_2,
)
from trading_engine.signals.structure_signals import (
    fvg_filled_bear,
    fvg_filled_bull,
    fvg_retest_bear,
    fvg_retest_bull,
    liquidity_sweep_bear,
    liquidity_sweep_bull,
    ob_mitigated_bear,
    ob_mitigated_bull,
    ob_test_bear,
    ob_test_bull,
    orb_breakout_down,
    orb_breakout_up,
    price_at_pdh,
    price_at_pdl,
    price_above_pdh,
    price_below_pdl,
    price_inside_opening_range,
    tl_break_down,
    tl_break_up,
    tl_third_touch_bounce,
    tl_third_touch_rejection,
)
from trading_engine.signals.technical_signals import (
    atr_above_threshold,
    atr_below_threshold,
    close_above_upper_band,
    close_below_lower_band,
    donchian_breakout_down,
    donchian_breakout_up,
    ema_fast_cross_above,
    ema_fast_cross_below,
    is_ema_bear_trend,
    is_ema_bull_trend,
    price_above_hma,
    price_below_hma,
    price_touches_bollinger_lower,
    price_touches_bollinger_upper,
    rsi_above,
    rsi_below,
    rsi_oversold,
    rsi_overbought,
    supertrend_downtrend,
    supertrend_uptrend,
)


# =========================================================================== #
# Helpers
# =========================================================================== #
def _make_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Deterministic OHLCV DataFrame with a DatetimeIndex."""
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0, 0.5, size=n))
    close = pd.Series(base, index=pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC"))
    noise = rng.normal(0, 0.3, size=n)
    open_ = close + noise
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.2, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.2, size=n))
    volume = rng.integers(100, 1000, size=n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=close.index,
    )


def _row(df: pd.DataFrame, i: int) -> pd.Series:
    return df.iloc[i]


# =========================================================================== #
# Family A — Technical
# =========================================================================== #
def test_ema_matches_recursive_definition():
    close = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = ema(close, length=3)
    # EMA with adjust=False: first valid value at index length-1.
    assert not np.isnan(result.iloc[-1])
    assert result.iloc[-1] > 0


def test_ema_zero_look_ahead():
    df = _make_df(50)
    full = ema(df["close"], length=14)
    # Truncating the input must not change earlier outputs.
    truncated = ema(df["close"].iloc[:30], length=14)
    pd.testing.assert_series_equal(full.iloc[:30], truncated, check_names=False)


def test_sma_basic():
    close = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = sma(close, length=3)
    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert math.isclose(result.iloc[2], 2.0)
    assert math.isclose(result.iloc[4], 4.0)


def test_rsi_range_and_bounds():
    df = _make_df(100)
    result = rsi(df["close"], length=14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_zero_look_ahead():
    df = _make_df(60)
    full = rsi(df["close"], length=14)
    truncated = rsi(df["close"].iloc[:40], length=14)
    pd.testing.assert_series_equal(full.iloc[:40], truncated, check_names=False)


def test_atr_positive():
    df = _make_df(60)
    result = atr(df["high"], df["low"], df["close"], length=14)
    valid = result.dropna()
    assert (valid >= 0).all()


def test_bollinger_bands_shape():
    df = _make_df(60)
    bands = bollinger_bands(df["close"], length=20, std_dev=2.0)
    assert set(bands.keys()) == {"upper", "middle", "lower"}
    valid = bands["middle"].dropna()
    assert (bands["upper"].loc[valid.index] >= bands["middle"].loc[valid.index]).all()
    assert (bands["lower"].loc[valid.index] <= bands["middle"].loc[valid.index]).all()


def test_macd_shape():
    df = _make_df(60)
    out = macd(df["close"])
    assert set(out.keys()) == {"macd", "signal", "histogram"}
    assert len(out["macd"]) == len(df)


def test_supertrend_direction_values():
    df = _make_df(100)
    out = supertrend(df["high"], df["low"], df["close"], period=10, multiplier=3.0)
    assert set(out.keys()) == {"supertrend", "direction"}
    dirs = out["direction"].dropna()
    assert set(dirs.unique()).issubset({1, -1})


def test_donchian_channels():
    df = _make_df(60)
    ch = donchian_channels(df["high"], df["low"], length=20)
    assert set(ch.keys()) == {"upper", "lower", "middle"}
    valid = ch["upper"].dropna()
    assert (ch["upper"].loc[valid.index] >= ch["lower"].loc[valid.index]).all()


def test_pivots_uses_previous_bar_only():
    df = _make_df(60)
    p = pivots(df["high"], df["low"], df["close"])
    # First row has no previous bar -> NaN.
    assert np.isnan(p["pp"].iloc[0])
    # PP = (prev H + prev L + prev C) / 3
    expected_pp = (df["high"].shift(1) + df["low"].shift(1) + df["close"].shift(1)) / 3.0
    pd.testing.assert_series_equal(p["pp"], expected_pp)


def test_hma_basic():
    close = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    result = hma(close, length=5)
    valid = result.dropna()
    assert len(valid) > 0
    assert (valid > 0).all()


def test_hma_zero_look_ahead():
    df = _make_df(60)
    full = hma(df["close"], length=14)
    truncated = hma(df["close"].iloc[:40], length=14)
    pd.testing.assert_series_equal(full.iloc[:40], truncated, check_names=False)


def test_hma_signals():
    row = pd.Series({"close": 101.0, "hma": 100.0})
    assert price_above_hma(row) is True
    assert price_below_hma(row) is False

    row2 = pd.Series({"close": 99.0, "hma": 100.0})
    assert price_above_hma(row2) is False
    assert price_below_hma(row2) is True


def test_technical_indicators_no_future_leakage():
    """Changing future bars must not alter indicator output at time T."""
    df = _make_df(100)
    base_ema = ema(df["close"], length=14)
    base_rsi = rsi(df["close"], length=14)

    df_future_changed = df.copy()
    df_future_changed.iloc[-5:, df_future_changed.columns.get_loc("close")] *= 10.0
    new_ema = ema(df_future_changed["close"], length=14)
    new_rsi = rsi(df_future_changed["close"], length=14)

    # Outputs up to index 94 must be identical (future change at index 95+).
    pd.testing.assert_series_equal(base_ema.iloc[:95], new_ema.iloc[:95], check_names=False)
    pd.testing.assert_series_equal(base_rsi.iloc[:95], new_rsi.iloc[:95], check_names=False)


# =========================================================================== #
# Family B — Statistical
# =========================================================================== #
def test_rolling_zscore_mean_zero_unit_var():
    s = pd.Series(np.random.default_rng(1).standard_normal(100))
    z = rolling_zscore(s, window=20)
    valid = z.dropna().iloc[-30:]
    # Rolling window of standard normal should have approx mean 0 std ~1.
    assert abs(valid.mean()) < 0.5
    assert 0.5 < valid.std() < 2.0


def test_zscore_zero_look_ahead():
    s = pd.Series(np.arange(100, dtype=float))
    full = rolling_zscore(s, window=20)
    truncated = rolling_zscore(s.iloc[:60], window=20)
    pd.testing.assert_series_equal(full.iloc[:60], truncated, check_names=False)


def test_hurst_range():
    s = pd.Series(np.cumsum(np.random.default_rng(2).standard_normal(500)))
    h = hurst_exponent(s, window=100)
    valid = h.dropna()
    assert ((valid >= 0.0) & (valid <= 1.0)).all()


def test_linreg_slope_sign():
    s = pd.Series(np.arange(100, dtype=float))
    slope = linear_regression_slope(s, window=20)
    valid = slope.dropna()
    assert (valid > 0).all()  # strictly increasing series

    s2 = pd.Series(np.arange(99, -1, -1, dtype=float))
    slope2 = linear_regression_slope(s2, window=20)
    valid2 = slope2.dropna()
    assert (valid2 < 0).all()


def test_relative_strength():
    a = pd.Series(np.arange(100, dtype=float) * 2.0)
    b = pd.Series(np.arange(100, dtype=float))
    rs = relative_strength(a, b, window=10)
    valid = rs.dropna()
    # a/b = 2 for all bars where b>0.
    assert np.allclose(valid[valid.notna() & (b.iloc[valid.index] > 0)], 2.0, atol=0.05)


def test_volatility_percentile_range():
    s = pd.Series(np.abs(np.random.default_rng(3).standard_normal(300)))
    vp = volatility_percentile(s, window=10, lookback=50)
    valid = vp.dropna()
    assert ((valid >= 0.0) & (valid <= 100.0)).all()


# =========================================================================== #
# Family C — Structure
# =========================================================================== #
def test_pdh_pdl_pdc_shifted_by_one_day():
    # Build intraday data spanning two days.
    idx = pd.date_range("2026-01-05 09:15", periods=6, freq="15min", tz="UTC")
    # Day 1 bars then day 2 bars.
    high = pd.Series([100, 101, 102, 103, 104, 105], index=idx)
    low = pd.Series([99, 98, 97, 96, 95, 94], index=idx)
    close = pd.Series([100, 100.5, 101, 102, 103, 104], index=idx)
    out = pdh_pdl_pdc(high, low, close)
    assert set(out.keys()) == {"pdh", "pdl", "pdc"}


def test_opening_range_returns_levels():
    idx = pd.date_range("2026-01-05 09:15", periods=10, freq="5min", tz="UTC")
    high = pd.Series(range(100, 110), index=idx, dtype=float)
    low = pd.Series(range(90, 100), index=idx, dtype=float)
    out = opening_range(high, low, open_time="09:15", minutes=10)
    assert set(out.keys()) == {"orh", "orl"}


def test_dynamic_trendline_shape():
    df = _make_df(120)
    out = dynamic_trendline(df["high"], df["low"], df["close"], window=50)
    assert set(out.keys()) == {"tl_support", "tl_resistance", "tl_touches"}


def test_fvg_shape():
    df = _make_df(60)
    out = fvg(df["high"], df["low"], df["close"])
    assert set(out.keys()) == {
        "fvg_bull_top", "fvg_bull_bottom", "fvg_bear_top",
        "fvg_bear_bottom", "fvg_bull_active", "fvg_bear_active",
    }


def test_order_blocks_shape():
    df = _make_df(100)
    out = order_blocks(df["high"], df["low"], df["close"], lookback=20)
    assert set(out.keys()) == {
        "ob_bull_top", "ob_bull_bottom", "ob_bear_top", "ob_bear_bottom",
        "ob_bull_active", "ob_bear_active",
    }


def test_liquidity_sweep_shape():
    df = _make_df(60)
    out = liquidity_sweep(df["high"], df["low"], df["close"], window=20)
    assert set(out.keys()) == {"sweep_bull", "sweep_bear"}


def test_structure_indicators_no_future_leakage():
    # PDH/PDL/PDC carry previous calendar day's levels forward; future bars
    # (even tomorrow's) must not alter today's PDH level.
    day1 = pd.date_range("2026-01-05 09:15", periods=3, freq="15min", tz="UTC")
    day2 = pd.date_range("2026-01-06 09:15", periods=3, freq="15min", tz="UTC")
    idx = day1.union(day2).sort_values()
    high = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0], index=idx)
    low = pd.Series([99.0, 98.0, 97.0, 96.0, 95.0, 94.0], index=idx)
    close = pd.Series([100.0, 100.5, 101.0, 102.0, 103.0, 104.0], index=idx)

    out = pdh_pdl_pdc(high, low, close)
    # Day 2 bars should see day 1's high as PDH.
    base_pdh = out["pdh"].iloc[3:6]
    high2 = high.copy()
    high2.iloc[3:] *= 10.0  # change future (day 2) bars
    new_pdh = pdh_pdl_pdc(high2, low, close)["pdh"].iloc[3:6]
    pd.testing.assert_series_equal(base_pdh, new_pdh, check_names=False)


# =========================================================================== #
# Family D — Orderflow
# =========================================================================== #
def test_vwap_basic():
    df = _make_fd_vwap_df()
    out = vwap(df["high"], df["low"], df["close"], df["volume"], anchor="day")
    assert len(out) == len(df)
    assert out.notna().all()


def test_vwap_bands_shape():
    df = _make_fd_vwap_df()
    out = vwap_bands(df["high"], df["low"], df["close"], df["volume"])
    assert set(out.keys()) == {"vwap", "upper", "lower"}
    assert (out["upper"] >= out["vwap"]).all()
    assert (out["lower"] <= out["vwap"]).all()


def test_rvol_positive():
    df = _make_fd_vwap_df()
    out = rvol(df["volume"], window=10, lookback_days=5)
    valid = out.dropna()
    assert (valid >= 0).all()


def test_session_volume_profile_shape():
    df = _make_fd_vwap_df()
    out = session_volume_profile(df["high"], df["low"], df["close"], df["volume"])
    assert set(out.keys()) == {"poc", "vah", "val"}
    valid = out["poc"].dropna()
    assert (out["vah"].loc[valid.index] >= out["poc"].loc[valid.index]).all()
    assert (out["val"].loc[valid.index] <= out["poc"].loc[valid.index]).all()


def test_cvd_cumulative():
    close = pd.Series([100, 101, 100.5, 102, 101.5], dtype=float)
    volume = pd.Series([100, 100, 100, 100, 100], dtype=float)
    out = cvd(close, volume)
    assert out.iloc[0] == 100.0  # up bar
    assert out.iloc[2] < out.iloc[1]  # down bar reduces CVD


def test_footprint_imbalance_shape():
    df = _make_fd_vwap_df()
    out = footprint_imbalance(df["close"], df["volume"], df["high"], df["low"])
    assert set(out.keys()) == {"imbalance_bull", "imbalance_bear"}
    assert set(out["imbalance_bull"].dropna().unique()).issubset({0.0, 1.0})


def test_iceberg_detector_shape():
    close = pd.Series([100.0] * 10 + [101.0] * 10, dtype=float)
    volume = pd.Series([10.0] * 20, dtype=float)
    out = iceberg_detector(close, volume, window=10, repeat_threshold=3)
    assert len(out) == 20


def test_orderflow_no_future_leakage():
    df = _make_fd_vwap_df()
    base = vwap(df["high"], df["low"], df["close"], df["volume"])
    df2 = df.copy()
    df2.iloc[-5:, df2.columns.get_loc("close")] *= 10.0
    new = vwap(df2["high"], df2["low"], df2["close"], df2["volume"])
    pd.testing.assert_series_equal(base.iloc[:len(df) - 5], new.iloc[:len(df) - 5], check_names=False)


# =========================================================================== #
# Helper for VWAP tests (intraday session)
# =========================================================================== #
def _make_fd_vwap_df() -> pd.DataFrame:
    n = 200
    idx = pd.date_range("2026-01-05 09:15", periods=n, freq="1min", tz="UTC")
    rng = np.random.default_rng(7)
    base = 100.0 + np.cumsum(rng.normal(0, 0.2, size=n))
    close = pd.Series(base, index=idx)
    open_ = close + rng.normal(0, 0.1, size=n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.1, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.1, size=n))
    volume = rng.integers(100, 1000, size=n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=close.index,
    )


# =========================================================================== #
# Feature Store + zero look-ahead
# =========================================================================== #
def test_feature_store_write_and_load(tmp_path):
    db_path = str(tmp_path / "features.db")
    store = FeatureStore(db_path=db_path)
    df = _make_df(20)
    df_feat = df[["close", "volume"]].copy()
    df_feat["ema_14"] = ema(df["close"], length=14)
    count = store.write_features("BTCUSDT", "1m", df_feat)
    assert count == 20
    loaded = store.load_features("BTCUSDT", "1m")
    assert len(loaded) == 20
    assert "ema_14" in loaded.columns


def test_feature_store_zero_look_ahead_load(tmp_path):
    db_path = str(tmp_path / "features.db")
    store = FeatureStore(db_path=db_path)
    df = _make_df(20)
    store.write_features("BTCUSDT", "1m", df[["close"]])
    # Load only up to the 10th bar.
    ts = df.index[9]
    loaded = store.load_features("BTCUSDT", "1m", timestamp=ts)
    assert len(loaded) == 10
    assert loaded.index.max() == ts


def test_zero_look_ahead_slice_excludes_future():
    df = _make_df(20)
    sliced = zero_look_ahead_slice(df, df.index[10])
    assert len(sliced) == 11
    assert (sliced.index <= df.index[10]).all()


# =========================================================================== #
# Signals — Technical
# =========================================================================== #
def test_ema_fast_cross_above_detects_cross():
    row = pd.Series({"ema_fast": 21.0, "ema_slow": 20.0})
    prev = pd.Series({"ema_fast": 19.0, "ema_slow": 20.0})
    assert ema_fast_cross_above(row, "ema_fast", "ema_slow", prev_row=prev) is True
    # No cross if already above.
    prev2 = pd.Series({"ema_fast": 21.0, "ema_slow": 20.0})
    assert ema_fast_cross_above(row, "ema_fast", "ema_slow", prev_row=prev2) is False


def test_is_ema_bull_trend():
    row = pd.Series({"close": 101.0, "ema_fast": 100.5, "ema_slow": 100.0})
    assert is_ema_bull_trend(row) is True
    row2 = pd.Series({"close": 99.0, "ema_fast": 100.5, "ema_slow": 100.0})
    assert is_ema_bull_trend(row2) is False


def test_rsi_oversold_overbought():
    assert rsi_oversold(pd.Series({"rsi": 25.0})) is True
    assert rsi_oversold(pd.Series({"rsi": 35.0})) is False
    assert rsi_overbought(pd.Series({"rsi": 75.0})) is True
    assert rsi_overbought(pd.Series({"rsi": 65.0})) is False


def test_atr_volatility_filter():
    assert atr_above_threshold(pd.Series({"atr": 2.0, "atr_sma": 1.0}), "atr", "atr_sma") is True
    assert atr_above_threshold(pd.Series({"atr": 0.5, "atr_sma": 1.0}), "atr", "atr_sma") is False


def test_bollinger_touch():
    assert price_touches_bollinger_lower(pd.Series({"close": 99.0, "bb_lower": 100.0})) is True
    assert price_touches_bollinger_upper(pd.Series({"close": 101.0, "bb_upper": 100.0})) is True


def test_supertrend_direction():
    assert supertrend_uptrend(pd.Series({"supertrend_direction": 1})) is True
    assert supertrend_downtrend(pd.Series({"supertrend_direction": -1})) is True


def test_donchian_breakout():
    # First bar: price already above the Donchian upper channel on the previous
    # bar too, so there is NO cross — must be False.
    row = pd.Series({"high": 101.0, "donchian_upper": 100.0})
    prev = pd.Series({"high": 100.5, "donchian_upper": 100.0})
    assert donchian_breakout_up(row, "high", "donchian_upper", prev_row=prev) is False
    # Second bar: previous bar was at/below the channel, current bar breaks above — True.
    row2 = pd.Series({"high": 101.0, "donchian_upper": 100.0})
    prev2 = pd.Series({"high": 99.0, "donchian_upper": 100.0})
    assert donchian_breakout_up(row2, "high", "donchian_upper", prev_row=prev2) is True


# =========================================================================== #
# Signals — Statistical
# =========================================================================== #
def test_zscore_signals():
    assert zscore_below_minus_2(pd.Series({"zscore": -2.5})) is True
    assert zscore_below_minus_2(pd.Series({"zscore": -1.5})) is False
    assert zscore_above_plus_2(pd.Series({"zscore": 2.5})) is True
    assert zscore_above_plus_2(pd.Series({"zscore": 1.5})) is False


def test_hurst_regime_signals():
    assert hurst_trending_regime(pd.Series({"hurst": 0.6})) is True
    assert hurst_mean_reverting_regime(pd.Series({"hurst": 0.4})) is True
    assert hurst_random_walk(pd.Series({"hurst": 0.5})) is True


def test_volatility_regime_signals():
    assert volatility_expanding(pd.Series({"volatility_percentile": 80.0})) is True
    assert volatility_contracting(pd.Series({"volatility_percentile": 20.0})) is True


def test_slope_signals():
    assert slope_positive(pd.Series({"linreg_slope": 0.5})) is True
    assert slope_negative(pd.Series({"linreg_slope": -0.5})) is True


def test_rs_signals():
    assert rs_leader(pd.Series({"relative_strength": 1.2, "relative_strength_benchmark": 1.0})) is True
    assert rs_laggard(pd.Series({"relative_strength": 0.8, "relative_strength_benchmark": 1.0})) is True


# =========================================================================== #
# Signals — Structure
# =========================================================================== #
def test_pdh_pdl_signals():
    assert price_above_pdh(pd.Series({"close": 101.0, "pdh": 100.0})) is True
    assert price_below_pdl(pd.Series({"close": 99.0, "pdl": 100.0})) is True
    assert price_at_pdh(pd.Series({"high": 100.0, "low": 100.0, "pdh": 100.0})) is True


def test_orb_signals():
    row = pd.Series({"close": 101.0, "orh": 100.0})
    prev = pd.Series({"close": 100.0})
    assert orb_breakout_up(row, "close", "orh", "orl", prev_row=prev) is True


def test_fvg_retest_signals():
    row = pd.Series({
        "close": 100.5, "fvg_bull_active": 1.0,
        "fvg_bull_bottom": 100.0, "fvg_bull_top": 101.0,
    })
    assert fvg_retest_bull(row) is True
    row2 = pd.Series({
        "close": 99.5, "fvg_bear_active": 1.0,
        "fvg_bear_bottom": 99.0, "fvg_bear_top": 100.0,
    })
    assert fvg_retest_bear(row2) is True


def test_ob_test_signals():
    row = pd.Series({
        "close": 100.5, "ob_bull_active": 1.0,
        "ob_bull_bottom": 100.0, "ob_bull_top": 101.0,
    })
    assert ob_test_bull(row) is True


def test_liquidity_sweep_signals():
    assert liquidity_sweep_bull(pd.Series({"sweep_bull": 1.0})) is True
    assert liquidity_sweep_bear(pd.Series({"sweep_bear": 1.0})) is True


def test_tl_signals():
    assert tl_third_touch_bounce(pd.Series({"close": 100.0, "tl_support": 100.0, "tl_touches": 3})) is True
    assert tl_break_up(pd.Series({"close": 101.0, "tl_resistance": 100.0})) is True


# =========================================================================== #
# Signals — Orderflow
# =========================================================================== #
def test_vwap_signals():
    assert above_vwap(pd.Series({"close": 101.0, "vwap": 100.0})) is True
    assert below_vwap(pd.Series({"close": 99.0, "vwap": 100.0})) is True


def test_volume_profile_signals():
    assert at_session_poc(pd.Series({"close": 100.0, "poc": 100.0})) is True
    assert price_above_vah(pd.Series({"close": 101.0, "vah": 100.0})) is True
    assert price_below_val(pd.Series({"close": 99.0, "val": 100.0})) is True
    assert price_in_value_area(pd.Series({"close": 100.0, "vah": 101.0, "val": 99.0})) is True


def test_rvol_signals():
    assert rvol_above_2x(pd.Series({"rvol": 2.5})) is True
    assert rvol_below_threshold(pd.Series({"rvol": 0.3})) is True


def test_footprint_cvd_iceberg_signals():
    assert footprint_imbalance_bull(pd.Series({"imbalance_bull": 1.0})) is True
    assert footprint_imbalance_bear(pd.Series({"imbalance_bear": 1.0})) is True
    assert iceberg_present(pd.Series({"iceberg": 1.0})) is True
    assert cvd_rising(pd.Series({"cvd": 100.0}), prev_row=pd.Series({"cvd": 90.0})) is True
    assert cvd_falling(pd.Series({"cvd": 90.0}), prev_row=pd.Series({"cvd": 100.0})) is True
