"""tests/test_phase4_eval_validation.py — Phase 4 verification suite.

Covers (PRD Phase 4 stop gate):
  • validation/backtester.py — event-driven historical backtest runner generating
    trade logs in trades_memory; zero look-ahead (t <= T).
  • evaluation/analyzer.py — Performance / Risk / Regime breakdown + structured
    Weakness Detection JSON report.
  • validation/gatekeeper.py — 4 independent tests (OOS 70/30, Walk-Forward
    K=5, Parameter Sensitivity Heatmap 5x5, Cost Stress 1.5x) outputting
    APPROVED / REJECTED; never lets AI self-approve.
  • Cross-module: weakness detection + gatekeeper approval/rejection logic.

Run: pytest trading_engine/tests/test_phase4_eval_validation.py -v   (from repo root)
"""

from __future__ import annotations

import json
import math
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from trading_engine.config import DB_PATH, DEFAULT_SLIPPAGE_BP
from trading_engine.evaluation.analyzer import (
    compute_performance,
    compute_risk,
    compute_regime_breakdown,
    detect_weaknesses,
    weakness_report_json,
)
from trading_engine.memory.db import get_connection
from trading_engine.memory.trade_logger import TradeLogger
from trading_engine.validation.backtester import Backtester, BacktestResult
from trading_engine.validation.gatekeeper import ValidationGatekeeper
from trading_engine.strategies.base_strategy import BaseStrategy


# =========================================================================== #
# Helpers                                                                     #
# =========================================================================== #
def _make_ohlcv(n: int = 400, seed: int = 11) -> pd.DataFrame:
    """Deterministic OHLCV DataFrame with a UTC DatetimeIndex (1min bars)."""
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0, 0.5, size=n))
    close = pd.Series(base, index=pd.date_range("2026-11-10 09:15", periods=n,
                                                freq="1min", tz="UTC"))
    noise = rng.normal(0, 0.3, size=n)
    open_ = close + noise
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.2, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.2, size=n))
    volume = rng.integers(100, 1000, size=n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=close.index,
    )


def _build_feature_df(n: int = 400, seed: int = 11) -> pd.DataFrame:
    """Feature DataFrame consumed by the fixture strategies below.

    Columns: close, high, low, volume, ema_20, ema_50, atr_14, hma_20
    """
    df = _make_ohlcv(n=n, seed=seed)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    from trading_engine.indicators.technical import atr, ema, hma
    df["ema_20"] = ema(close, length=20)
    df["ema_50"] = ema(close, length=50)
    df["hma_20"] = hma(close, length=20)
    df["atr_14"] = atr(high, low, close, length=14)
    # Force ATR above its SMA everywhere so the strategy gate passes.
    df["atr_14"] = df["atr_14"].rolling(window=14, min_periods=1).mean() * 1.5
    return df


def _tmp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _cleanup_db(path: str) -> None:
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass


# --------------------------------------------------------------------------- #
# Strategy fixture for backtester tests                                       #
# --------------------------------------------------------------------------- #
class _TrendFollow(BaseStrategy):
    """Deterministic long-only strategy: enters at precomputed trigger indices."""

    strategy_id = "TREND_FOLLOW_TEST"
    default_params = {
        "ema_fast_len": 20,
        "ema_slow_len": 50,
        "atr_len": 14,
        "atr_mult_threshold": 1.15,
        "hma_len": 20,
        "sl_atr_mult": 1.5,
        "tp_rr_ratio": 1.5,
        "tp2_rr_ratio": 3.0,
    }

    def __init__(self, params=None, trigger_indices=None):
        super().__init__(params)
        self.trigger_indices = set(trigger_indices or [])

    def evaluate(self, df_features, current_idx):
        if current_idx in self.trigger_indices:
            row = df_features.iloc[current_idx]
            close = float(row["close"])
            atr = float(row["atr_14"])
            risk = self.params["sl_atr_mult"] * atr
            return self.build_signal(
                row=row, direction="LONG",
                entry_price=close, stop_loss_raw=close - risk,
                target_1_raw=close + risk * self.params["tp_rr_ratio"],
                target_2_raw=close + risk * self.params["tp2_rr_ratio"],
                active_signals=["EMA_CROSS"],
                regime_snapshot={"volatility_regime": "EXPANDING_ATR"},
            )
        return None


# =========================================================================== #
# Backtester tests                                                            #
# =========================================================================== #
def test_backtester_runs_and_records_trades():
    df = _build_feature_df(n=400, seed=11)
    strat = _TrendFollow(trigger_indices=[150, 200, 250])
    path = _tmp_db_path()
    try:
        bt = Backtester(strat, account_equity=10000.0, db_path=path)
        res = bt.run(df, start_idx=50, end_idx=400)

        assert res.total_trades >= 1
        assert isinstance(res.profit_factor, (int, float))
        assert res.win_count + res.loss_count == res.total_trades
        assert len(res.equity_curve) == 400 - 50
        # Persisted to SQLite.
        logger = TradeLogger(db_path=path)
        closed = logger.list_trades(strategy_id="TREND_FOLLOW_TEST",
                                    execution_mode="BACKTEST", status="CLOSED")
        assert len(closed) == res.total_trades
        for t in closed:
            assert t["net_pnl"] is not None
            assert t["r_multiple"] is not None
            assert t["mae_pct"] is not None
            assert t["mfe_pct"] is not None
            assert t["exit_reason"] in ("STOP_LOSS", "TAKE_PROFIT", "TIME_EXIT")
    finally:
        _cleanup_db(path)


def test_backtester_zero_look_ahead():
    """Truncating the future must not change results for earlier bars."""
    df_full = _build_feature_df(n=400, seed=11)
    strat_full = _TrendFollow(trigger_indices=[150])
    path_full = _tmp_db_path()
    try:
        res_full = Backtester(strat_full, db_path=path_full).run(
            df_full, start_idx=100, end_idx=200)
    finally:
        _cleanup_db(path_full)

    # Same underlying bars, just truncated — indicators use only t <= T.
    df_trunc = df_full.iloc[:200].copy()
    strat_trunc = _TrendFollow(trigger_indices=[150])
    path_trunc = _tmp_db_path()
    try:
        res_trunc = Backtester(strat_trunc, db_path=path_trunc).run(
            df_trunc, start_idx=100, end_idx=200)
    finally:
        _cleanup_db(path_trunc)

    assert len(res_full.closed_trades) == len(res_trunc.closed_trades)
    for a, b in zip(res_full.closed_trades, res_trunc.closed_trades):
        assert a["entry_price"] == b["entry_price"]
        assert a["net_pnl"] == b["net_pnl"]
        assert a["exit_price"] == b["exit_price"]


def test_backtester_flat_close_at_end():
    """Open positions are closed at the last bar's close (TIME_EXIT)."""
    df = _build_feature_df(n=400, seed=11)
    strat = _TrendFollow(trigger_indices=[390])
    path = _tmp_db_path()
    try:
        res = Backtester(strat, db_path=path).run(df, start_idx=100, end_idx=400)
        time_exits = [t for t in res.closed_trades
                      if t["exit_reason"] == "TIME_EXIT"]
        assert len(time_exits) >= 1
    finally:
        _cleanup_db(path)


def test_backtester_summary_structure():
    df = _build_feature_df(n=400, seed=11)
    strat = _TrendFollow(trigger_indices=[150, 200])
    path = _tmp_db_path()
    try:
        res = Backtester(strat, db_path=path).run(df, start_idx=50, end_idx=400)
        s = res.summary()
        for key in ("strategy_id", "symbol", "timeframe", "total_trades",
                    "win_count", "loss_count", "win_rate_pct", "profit_factor",
                    "total_net_pnl", "max_drawdown_pct", "expectancy_r",
                    "account_equity"):
            assert key in s
    finally:
        _cleanup_db(path)


# =========================================================================== #
# Analyzer tests                                                              #
# =========================================================================== #
def _sample_trades() -> list[dict]:
    return [
        {"net_pnl": 100.0, "r_multiple": 1.0, "direction": "LONG",
         "regime_snapshot": {"volatility_regime": "LOW_ATR"}},
        {"net_pnl": -40.0, "r_multiple": -0.4, "direction": "LONG",
         "regime_snapshot": {"volatility_regime": "LOW_ATR"}},
        {"net_pnl": 60.0, "r_multiple": 0.6, "direction": "SHORT",
         "regime_snapshot": {"volatility_regime": "HIGH_ATR"}},
        {"net_pnl": -90.0, "r_multiple": -0.9, "direction": "SHORT",
         "regime_snapshot": {"volatility_regime": "HIGH_ATR"}},
        {"net_pnl": 30.0, "r_multiple": 0.3, "direction": "LONG",
         "regime_snapshot": {"volatility_regime": "LOW_ATR"}},
    ]


def test_compute_performance_basic():
    trades = _sample_trades()
    perf = compute_performance(trades)
    assert perf["total_trades"] == 5
    assert perf["win_count"] == 3
    assert perf["loss_count"] == 2
    assert math.isclose(perf["win_rate_pct"], 60.0)
    assert math.isclose(perf["gross_profit"], 190.0)
    assert math.isclose(perf["gross_loss"], 130.0)
    assert math.isclose(perf["profit_factor"], round(190.0 / 130.0, 4), rel_tol=1e-6)
    assert perf["net_pnl"] == 60.0


def test_compute_performance_empty():
    perf = compute_performance([])
    assert perf["total_trades"] == 0
    assert perf["profit_factor"] == 0.0


def test_compute_risk_and_drawdown():
    trades = _sample_trades()
    equity = [("t1", 10000.0), ("t2", 10100.0), ("t3", 9900.0),
              ("t4", 9700.0), ("t5", 9900.0)]
    risk = compute_risk(trades, equity_curve=equity)
    assert risk["max_drawdown_pct"] > 0
    assert risk["largest_win"] == 100.0
    assert risk["largest_loss"] == -90.0


def test_compute_regime_breakdown():
    trades = _sample_trades()
    breakdown = compute_regime_breakdown(trades)
    assert "LOW_ATR" in breakdown and "HIGH_ATR" in breakdown
    assert breakdown["LOW_ATR"]["trade_count"] == 3
    assert breakdown["HIGH_ATR"]["trade_count"] == 2
    assert breakdown["LOW_ATR"]["net_pnl"] == 90.0   # 100 - 40 + 30
    assert breakdown["HIGH_ATR"]["net_pnl"] == -30.0  # 60 - 90
    assert breakdown["HIGH_ATR"]["is_losing_regime"] is True


def test_detect_weaknesses_negative_expectancy():
    trades = [
        {"net_pnl": -10.0, "r_multiple": -0.1, "direction": "LONG",
         "regime_snapshot": {"volatility_regime": "LOW_ATR"}} for _ in range(5)
    ]
    report = detect_weaknesses(trades)
    assert "NEGATIVE_EXPECTANCY" in report["flags"]
    assert report["summary"]["expectancy_r"] <= 0.0
    assert report["severity"] == "HIGH"
    assert report["recommendation"] == "REJECT"


def test_detect_weaknesses_losing_regime_flag():
    trades = [
        {"net_pnl": -50.0, "r_multiple": -0.5, "direction": "LONG",
         "regime_snapshot": {"volatility_regime": "CHOPPY"}} for _ in range(5)
    ]
    report = detect_weaknesses(trades)
    assert "LOSING_REGIMES:CHOPPY" in report["flags"]
    assert report["losing_regimes"] == ["CHOPPY"]


def test_weakness_report_json_is_valid_json():
    trades = _sample_trades()
    s = weakness_report_json(trades)
    obj = json.loads(s)
    assert "flags" in obj and "severity" in obj and "summary" in obj


# =========================================================================== #
# Gatekeeper tests                                                            #
# =========================================================================== #
class _ProfitableStrategy(BaseStrategy):
    """Strategy that generates steady small winners → passes gate thresholds.

    Triggers live in ``default_params["trigger_indices"]`` so that gatekeeper
    heatmap variants (built via ``cls(params=params)``) preserve them.
    """

    strategy_id = "PROFITABLE_V2"
    default_params = {
        "ema_fast_len": 20,
        "ema_slow_len": 50,
        "atr_len": 14,
        "atr_mult_threshold": 1.15,
        "hma_len": 20,
        "sl_atr_mult": 1.5,
        "tp_rr_ratio": 2.0,
        "tp2_rr_ratio": 4.0,
        # Spread across in-sample [0,350) for the parameter heatmap, plus one
        # trigger per walk-forward test window in OOS [350, 500).
        "trigger_indices": [100, 200, 300, 380, 410, 440, 470, 495],
    }

    def __init__(self, params=None):
        merged = dict(self.default_params)
        if params:
            merged.update(params)
        super().__init__(merged)
        self.trigger_indices = set(self.params.get("trigger_indices", []))

    def evaluate(self, df_features, current_idx):
        if current_idx in self.trigger_indices:
            row = df_features.iloc[current_idx]
            close = float(row["close"])
            atr = float(row["atr_14"])
            risk = self.params["sl_atr_mult"] * atr
            return self.build_signal(
                row=row, direction="LONG",
                entry_price=close, stop_loss_raw=close - risk,
                target_1_raw=close + risk * self.params["tp_rr_ratio"],
                target_2_raw=close + risk * self.params["tp2_rr_ratio"],
                active_signals=["EMA_CROSS"],
                regime_snapshot={"volatility_regime": "EXPANDING_ATR"},
            )
        return None


class _LosingStrategy(BaseStrategy):
    """Reference baseline that loses → candidate must beat it on ER/MaxDD."""

    strategy_id = "LOSING_V2"
    default_params = {
        "sl_atr_mult": 1.5,
        "tp_rr_ratio": 0.5,
        # OOS-range triggers that lose in an uptrend (SHORT → stop hit as price
        # climbs). Spread across in-sample [0,350) for heatmap plus one per
        # walk-forward window in OOS [350, 500).
        "trigger_indices": [100, 200, 300, 380, 410, 440, 470, 495],
    }

    def __init__(self, params=None):
        merged = dict(self.default_params)
        if params:
            merged.update(params)
        super().__init__(merged)
        self.trigger_indices = set(self.params.get("trigger_indices", []))

    def evaluate(self, df_features, current_idx):
        if current_idx in self.trigger_indices:
            row = df_features.iloc[current_idx]
            close = float(row["close"])
            atr = float(row["atr_14"])
            risk = self.params["sl_atr_mult"] * atr
            # SHORT in a rising market → stop loss hit as price climbs.
            return self.build_signal(
                row=row, direction="SHORT",
                entry_price=close, stop_loss_raw=close + risk * 4,
                target_1_raw=close - risk * self.params["tp_rr_ratio"],
                target_2_raw=close - risk * self.params["tp_rr_ratio"],
                active_signals=["BAD"],
                regime_snapshot={"volatility_regime": "CHOPPY"},
            )
        return None


def _gatekeeper_df(n: int = 500, seed: int = 21) -> pd.DataFrame:
    df = _build_feature_df(n=n, seed=seed)
    trend = np.linspace(100.0, 130.0, n)
    df["close"] = trend
    df["high"] = trend + 1.0
    df["low"] = trend - 1.0
    return df


def test_gatekeeper_approves_profitable_candidate():
    baseline = _LosingStrategy()
    candidate = _ProfitableStrategy()
    path = _tmp_db_path()
    try:
        gk = ValidationGatekeeper(candidate, baseline, db_path=path)
        report = gk.evaluate(_gatekeeper_df(n=500, seed=21),
                             symbol="BTCUSDT", timeframe="1m")
        assert report.final_status == "APPROVED", report.rejection_reason
        assert report.oos_passed is True
        assert report.walk_forward_passed is True
        assert report.param_stability_passed is True
        assert report.cost_stress_passed is True
        # Persisted to SQLite.
        conn = get_connection(db_path=path)
        try:
            row = conn.execute(
                "SELECT final_status FROM validation_reports WHERE report_id=?",
                (report.report_id,),
            ).fetchone()
            assert row is not None and row["final_status"] == "APPROVED"
        finally:
            conn.close()
    finally:
        _cleanup_db(path)


def test_gatekeeper_rejects_losing_candidate():
    baseline = _ProfitableStrategy()
    candidate = _LosingStrategy()
    path = _tmp_db_path()
    try:
        gk = ValidationGatekeeper(candidate, baseline, db_path=path)
        report = gk.evaluate(_gatekeeper_df(n=500, seed=21),
                             symbol="BTCUSDT", timeframe="1m")
        assert report.final_status == "REJECTED", report.rejection_reason
        assert report.rejection_reason is not None
        assert len(report.rejection_reason) > 0
    finally:
        _cleanup_db(path)


def test_gatekeeper_cost_stress_rejects():
    """High slippage breaks the cost stress test → REJECTED (no self-approval)."""
    baseline = _ProfitableStrategy()
    candidate = _ProfitableStrategy()
    path = _tmp_db_path()
    try:
        gk = ValidationGatekeeper(candidate, baseline, db_path=path,
                                  slippage_bp=1000.0)  # absurdly high cost
        report = gk.evaluate(_gatekeeper_df(n=500, seed=21),
                             symbol="BTCUSDT", timeframe="1m")
        assert report.final_status == "REJECTED", report.rejection_reason
        assert "COST_STRESS_FAILED" in (report.rejection_reason or "")
    finally:
        _cleanup_db(path)
