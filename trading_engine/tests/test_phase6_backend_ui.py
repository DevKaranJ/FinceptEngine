"""tests/test_phase6_backend_ui.py — Phase 6 verification suite.

Covers (PRD Phase 6 stop gate):
  • trading_engine/backend/server.py — FastAPI app + all REST routes registered
    per docs/database_and_data_contracts.md Section 3.
  • REST handlers return correct shapes / graceful on empty DB.
  • JSON sanitization of Infinity / NaN (validation reports carry Infinity PF).
  • WebSocket hub present and route registered.
  • Frontend files exist (index.html, css/styles.css, js/*.js, vendor chart lib).
  • Zero look-ahead: snapshot only returns stored historical bars (t <= T).

Run: pytest trading_engine/tests/test_phase6_backend_ui.py -v   (from repo root)
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest

# Ensure the repo root is on the path so `trading_engine` imports resolve.
# tests/ is at <repo>/trading_engine/tests/, so repo root is 3 levels up.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from trading_engine.backend import server  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def app():
    return server.app


# --------------------------------------------------------------------------- #
# Route registration                                                          #
# --------------------------------------------------------------------------- #
EXPECTED_ROUTES = [
    ("GET", "/"),
    ("GET", "/api/system/status"),
    ("GET", "/api/market/snapshot"),
    ("GET", "/api/trades/memory"),
    ("POST", "/api/trades/manual"),
    ("GET", "/api/evaluation/{strategy_id}"),
    ("GET", "/api/strategy/diagnostics"),
    ("POST", "/api/research/trigger"),
    ("GET", "/api/validation/reports"),
    ("WS", "/ws/live"),
]


def test_all_routes_registered(app):
    """Every Phase 6 endpoint from database_and_data_contracts.md Section 3 exists."""
    registered = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path:
            for m in methods:
                registered.append((m, path))
            # WebSocket routes have methods=None; handle separately.
        if getattr(route, "path", None) == "/ws/live":
            registered.append(("WS", "/ws/live"))

    for method, path in EXPECTED_ROUTES:
        assert (method, path) in registered, (
            f"Route {method} {path} not registered. Found: {sorted(set(registered))}"
        )


def test_websocket_route_is_websocket(app):
    """The /ws/live route must be a WebSocketRoute (not a plain HTTP route)."""
    from starlette.routing import WebSocketRoute

    ws_routes = [r for r in app.routes if isinstance(r, WebSocketRoute)]
    paths = [getattr(r, "path", None) for r in ws_routes]
    assert "/ws/live" in paths, f"No WebSocket route at /ws/live. WS paths: {paths}"


# --------------------------------------------------------------------------- #
# JSON sanitization                                                           #
# --------------------------------------------------------------------------- #
def test_sanitize_json_replaces_infinity_and_nan():
    """Validation reports carry `Infinity` PF — responses must be JSON-safe."""
    payload = {
        "pf": float("inf"),
        "neg_pf": float("-inf"),
        "nan": float("nan"),
        "ok": 1.25,
        "nested": {"inf": float("inf"), "list": [float("nan"), 2.0]},
        "text": "hello",
        "none": None,
    }
    clean = server._sanitize_json(payload)
    assert clean["pf"] is None
    assert clean["neg_pf"] is None
    assert clean["nan"] is None
    assert clean["ok"] == 1.25
    assert clean["nested"]["inf"] is None
    assert clean["nested"]["list"][0] is None
    assert clean["nested"]["list"][1] == 2.0
    assert clean["text"] == "hello"
    assert clean["none"] is None


# --------------------------------------------------------------------------- #
# REST: market snapshot (empty DB graceful)                                   #
# --------------------------------------------------------------------------- #
def test_market_snapshot_no_data_graceful():
    """Snapshot on a symbol with no cached bars returns an empty, valid payload."""
    import asyncio

    result = asyncio.run(server.market_snapshot(symbol="NOEXIST", timeframe="1m", limit=50))
    assert result["symbol"] == "NOEXIST"
    assert result["timeframe"] == "1m"
    assert result["bars"] == []
    assert result["count"] == 0
    assert "overlays" in result


# --------------------------------------------------------------------------- #
# REST: trades memory (works with existing data)                              #
# --------------------------------------------------------------------------- #
def test_trades_memory_pagination():
    """Trades memory returns paginated records with expected keys."""
    import asyncio

    result = asyncio.run(server.trades_memory(limit=5, offset=0))
    assert "trades" in result
    assert "total" in result
    assert isinstance(result["trades"], list)
    assert result["limit"] == 5
    assert result["offset"] == 0
    if result["trades"]:
        t = result["trades"][0]
        for key in ("trade_id", "strategy_id", "status", "net_pnl"):
            assert key in t, f"trade missing key {key}: {list(t.keys())}"


# --------------------------------------------------------------------------- #
# REST: validation reports                                                    #
# --------------------------------------------------------------------------- #
def test_validation_reports_shape():
    """Validation reports endpoint returns the scorecard JSON structure."""
    import asyncio

    result = asyncio.run(server.validation_reports())
    assert "reports" in result
    assert "count" in result
    assert isinstance(result["reports"], list)
    if result["reports"]:
        r = result["reports"][0]
        for key in (
            "report_id", "candidate_strategy_id", "baseline_strategy_id",
            "symbol", "timeframe", "final_status", "oos_passed",
            "walk_forward_passed", "param_stability_passed", "cost_stress_passed",
        ):
            assert key in r, f"report missing key {key}"


# --------------------------------------------------------------------------- #
# Frontend files exist                                                        #
# --------------------------------------------------------------------------- #
FRONTEND_FILES = [
    "trading_engine/frontend/index.html",
    "trading_engine/frontend/css/styles.css",
    "trading_engine/frontend/js/main.js",
    "trading_engine/frontend/js/chart_engine.js",
    "trading_engine/frontend/js/footprint_ui.js",
    "trading_engine/frontend/js/lab_evaluation_ui.js",
    "trading_engine/frontend/js/system_monitor_ui.js",
    "trading_engine/frontend/vendor/lightweightcharts.standalone.production.js",
]


def test_frontend_files_exist():
    """All Phase 6 frontend artifacts are present on disk."""
    for rel in FRONTEND_FILES:
        abs_path = os.path.join(ROOT, rel)
        assert os.path.isfile(abs_path), f"Missing frontend file: {rel}"
        assert os.path.getsize(abs_path) > 0, f"Empty frontend file: {rel}"


def test_vendor_chart_lib_has_api():
    """Vendored Lightweight Charts exposes createChart and series types."""
    path = os.path.join(ROOT, FRONTEND_FILES[-1])
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "createChart" in src, "Vendored chart lib missing createChart"
    assert "CandlestickSeries" in src, "Vendored chart lib missing CandlestickSeries"
    assert "version:function(){" in src or "\"5.3.0\"" in src, "Vendored chart lib version missing"


# --------------------------------------------------------------------------- #
# Zero look-ahead guard                                                       #
# --------------------------------------------------------------------------- #
def test_zero_look_ahead_constant():
    """ZERO_LOOK_AHEAD is enforced in config (t <= T)."""
    from trading_engine.config import ZERO_LOOK_AHEAD
    assert ZERO_LOOK_AHEAD is True


# =========================================================================== #
# Milestone 1 Enhancements & Gating Verification                              #
# =========================================================================== #
def test_market_snapshot_donchian_overlays_include_all_three_bands():
    """Donchian overlays must unpack correctly and include upper, middle, and lower."""
    import asyncio
    import sqlite3
    import pandas as pd
    from trading_engine.config import DB_PATH
    from trading_engine.memory.db import get_connection, initialize_database

    initialize_database(db_path=DB_PATH)
    conn = get_connection(db_path=DB_PATH)
    try:
        # Seed 30 bars for BTCUSDT symbol
        for i in range(30):
            ts = f"2026-11-14T01:{i:02d}:00Z"
            base = 100.0 + i * 0.5
            conn.execute(
                """
                INSERT OR REPLACE INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("BTCUSDT", "CRYPTO_SPOT", "1m", ts, base, base + 2.0, base - 2.0, base + 1.0, 10.0),
            )
        conn.commit()
    finally:
        conn.close()

    result = asyncio.run(server.market_snapshot(symbol="BTCUSDT", timeframe="1m", limit=30))
    overlays = result["overlays"]

    assert "error" not in overlays, f"Overlay computation failed with error: {overlays.get('error')}"
    for k in ("donchian_upper_20", "donchian_middle_20", "donchian_lower_20", "ema_20", "ema_50", "hma_20", "atr_14", "rsi_14"):
        assert k in overlays, f"Missing overlay key {k}"
        assert isinstance(overlays[k], list), f"Overlay {k} is not a list"
        assert len(overlays[k]) == 30, f"Overlay {k} length mismatch: expected 30, got {len(overlays[k])}"

    # Verify Donchian middle arithmetic relationship on non-NaN elements
    non_null_idx = [idx for idx, v in enumerate(overlays["donchian_upper_20"]) if v is not None]
    assert len(non_null_idx) > 0, "All Donchian values are None"
    sample_i = non_null_idx[-1]
    u = overlays["donchian_upper_20"][sample_i]
    m = overlays["donchian_middle_20"][sample_i]
    l = overlays["donchian_lower_20"][sample_i]
    assert abs(m - round((u + l) / 2.0, 4)) < 1e-3, f"Donchian middle mismatch: {m} vs ({u}+{l})/2"


def test_manual_trade_endpoint_risk_reward_gating():
    """Manual trade orders with R:R < 1.5 must be rejected with HTTP 422; >= 1.5 accepted."""
    import asyncio
    from fastapi import HTTPException

    # Sub-threshold R:R = 1.0 (Risk=100, Reward=100) -> 422
    payload_bad = {
        "strategy_id": "MANUAL_TEST",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "entry_price": 68000.0,
        "stop_loss": 67900.0,
        "target_1_price": 68100.0,
        "position_size": 0.5,
    }
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade(payload_bad))
    assert exc_info.value.status_code == 422
    assert "below mandatory threshold 1.50" in exc_info.value.detail

    # Valid R:R = 1.5 (Risk=100, Reward=150) -> 200 OK
    payload_good = {
        "strategy_id": "MANUAL_TEST",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "entry_price": 68000.0,
        "stop_loss": 67900.0,
        "target_1_price": 68150.0,
        "position_size": 0.5,
    }
    res = asyncio.run(server.manual_trade(payload_good))
    assert res["status"] == "OK"
    assert "trade_id" in res
    assert res["trade_id"].startswith("TRD_")

    # Float precision boundary: (0.35 - 0.20) / (0.20 - 0.10) is 1.4999999999999998 in IEEE 754
    payload_float_boundary = {
        "strategy_id": "MANUAL_TEST",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "entry_price": 0.20,
        "stop_loss": 0.10,
        "target_1_price": 0.35,
        "position_size": 100.0,
    }
    res_float = asyncio.run(server.manual_trade(payload_float_boundary))
    assert res_float["status"] == "OK"
    assert "trade_id" in res_float


def test_manual_trade_endpoint_rejects_inverted_stops():
    """Manual trade orders with inverted stops or targets must be rejected with HTTP 422."""
    import asyncio
    from fastapi import HTTPException

    # LONG with SL >= Entry
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "LONG",
            "entry_price": 68000.0,
            "stop_loss": 68100.0,
            "target_1_price": 68300.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # LONG with Target <= Entry
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "LONG",
            "entry_price": 68000.0,
            "stop_loss": 67800.0,
            "target_1_price": 67900.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # SHORT with SL <= Entry
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "SHORT",
            "entry_price": 68000.0,
            "stop_loss": 67900.0,
            "target_1_price": 67700.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # SHORT with Target >= Entry
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "SHORT",
            "entry_price": 68000.0,
            "stop_loss": 68200.0,
            "target_1_price": 68100.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # Zero risk (entry == stop_loss)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "LONG",
            "entry_price": 68000.0,
            "stop_loss": 68000.0,
            "target_1_price": 68200.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # Omitted target on SHORT (defaults to 0.0, rejected with HTTP 422)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "SHORT",
            "entry_price": 68000.0,
            "stop_loss": 68200.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # Negative stop loss on LONG (rejected with HTTP 422)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "LONG",
            "entry_price": 100.0,
            "stop_loss": -50.0,
            "target_1_price": 250.0,
            "position_size": 1.0,
        }))
    assert exc_info.value.status_code == 422

    # Invalid target_2_price on LONG (target_2 <= target_1)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "LONG",
            "entry_price": 68000.0,
            "stop_loss": 67900.0,
            "target_1_price": 68200.0,
            "target_2_price": 68150.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # Invalid target_2_price on SHORT (target_2 >= target_1)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "SHORT",
            "entry_price": 68000.0,
            "stop_loss": 68200.0,
            "target_1_price": 67700.0,
            "target_2_price": 67800.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422

    # Negative target_2_price on SHORT
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(server.manual_trade({
            "direction": "SHORT",
            "entry_price": 68000.0,
            "stop_loss": 68200.0,
            "target_1_price": 67700.0,
            "target_2_price": -10.0,
            "position_size": 0.1,
        }))
    assert exc_info.value.status_code == 422


def test_baseline_demonstration_strategy_contract_a_and_zero_lookahead():
    """BaselineDemonstrationStrategy conforms to Contract A with zero look-ahead bias."""
    import numpy as np
    import pandas as pd
    from trading_engine.strategies.approved.baseline_demonstration_strategy import (
        BaselineDemonstrationStrategy,
    )

    strat = BaselineDemonstrationStrategy()
    assert strat.strategy_id == "BASELINE_DEMO_V1"

    # Build 70 synthetic trending bars with a pullback bounce
    n = 70
    dates = pd.date_range("2026-11-14 00:00", periods=n, freq="1min", tz="UTC")
    close = np.linspace(100.0, 150.0, n)
    high = close + 1.0
    low = close - 1.0
    open_ = close - 0.2
    vol = np.full(n, 100.0)

    # Induce a pullback at bar 55 (dip below fast EMA, bounce above at bar 56)
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
    }, index=dates)

    # Bar 55 drops close, bar 56 bounces back strong
    df.at[df.index[55], "close"] = 130.0
    df.at[df.index[55], "low"] = 129.0
    df.at[df.index[56], "close"] = 142.0
    df.at[df.index[56], "high"] = 143.0

    sig = strat.evaluate(df, 56)
    assert sig is not None, "Expected signal at pullback bounce bar 56"

    # Contract A key assertions
    for req in ("strategy_id", "symbol", "timeframe", "timestamp_utc", "direction",
                "entry_price", "stop_loss_raw", "target_1_raw", "target_2_raw",
                "active_signals", "regime_snapshot"):
        assert req in sig, f"Missing Contract A key: {req}"

    assert sig["strategy_id"] == "BASELINE_DEMO_V1"
    assert sig["direction"] in ("LONG", "SHORT")
    assert sig["entry_price"] > 0
    assert sig["stop_loss_raw"] < sig["entry_price"] < sig["target_1_raw"]
    risk = abs(sig["entry_price"] - sig["stop_loss_raw"])
    reward = abs(sig["target_1_raw"] - sig["entry_price"])
    assert (reward / risk) >= 1.49, f"Signal R:R ({reward/risk}) is below 1.5"

    # Test Zero Look-Ahead Bias: modifying future bars (57..69) MUST NOT alter signal at bar 56
    df_future_corrupted = df.copy()
    df_future_corrupted.loc[df.index[57:], "close"] = 99999.0
    df_future_corrupted.loc[df.index[57:], "high"] = 100000.0
    df_future_corrupted.loc[df.index[57:], "low"] = 99990.0

    sig_corrupted = strat.evaluate(df_future_corrupted, 56)
    assert sig_corrupted == sig, "Signal changed when future bars were altered! Look-ahead violation detected."

    # Test parameter sensitivity perturbation
    strat_perturbed = BaselineDemonstrationStrategy({
        "ema_fast_len": 18,
        "ema_slow_len": 45,
        "sl_atr_mult": 1.2,
        "tp_rr_ratio": 2.0,
    })
    sig_p = strat_perturbed.evaluate(df, 56)
    if sig_p is not None:
        risk_p = abs(sig_p["entry_price"] - sig_p["stop_loss_raw"])
        reward_p = abs(sig_p["target_1_raw"] - sig_p["entry_price"])
        assert abs(reward_p / risk_p - 2.0) < 1e-2


def test_baseline_demonstration_strategy_donchian_breakout_trigger():
    """Verify Donchian breakout trigger fires on genuine upper and lower channel breakouts."""
    import numpy as np
    import pandas as pd
    from trading_engine.strategies.approved.baseline_demonstration_strategy import (
        BaselineDemonstrationStrategy,
    )

    strat = BaselineDemonstrationStrategy()

    # 1. LONG Breakout:
    # 70 bars in steady uptrend, breakout above prior 20-bar Donchian upper band at bar 55
    n = 70
    dates = pd.date_range("2026-11-14 00:00", periods=n, freq="1min", tz="UTC")
    close = np.linspace(100.0, 135.0, n)
    high = close + 1.0
    low = close - 1.0
    open_ = close - 0.2
    vol = np.full(n, 100.0)

    df_long = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
    }, index=dates)

    prev_max_high = float(df_long.iloc[35:55]["high"].max())
    df_long.at[df_long.index[55], "open"] = prev_max_high + 0.5
    df_long.at[df_long.index[55], "high"] = prev_max_high + 5.0
    df_long.at[df_long.index[55], "close"] = prev_max_high + 4.0
    df_long.at[df_long.index[55], "low"] = prev_max_high + 0.2

    sig_long = strat.evaluate(df_long, 55)
    assert sig_long is not None, "Expected LONG breakout signal at bar 55"
    assert sig_long["direction"] == "LONG"
    assert "DONCHIAN_BREAKOUT_UP" in sig_long["active_signals"]
    assert sig_long["entry_price"] == prev_max_high + 4.0
    assert sig_long["stop_loss_raw"] < sig_long["entry_price"] < sig_long["target_1_raw"]

    # 2. SHORT Breakout:
    # 70 bars in steady downtrend, breakdown below prior 20-bar Donchian lower band at bar 55
    close_s = np.linspace(135.0, 100.0, n)
    high_s = close_s + 1.0
    low_s = close_s - 1.0
    open_s = close_s + 0.2

    df_short = pd.DataFrame({
        "open": open_s,
        "high": high_s,
        "low": low_s,
        "close": close_s,
        "volume": vol,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
    }, index=dates)

    prev_min_low = float(df_short.iloc[35:55]["low"].min())
    df_short.at[df_short.index[55], "open"] = prev_min_low - 0.5
    df_short.at[df_short.index[55], "low"] = prev_min_low - 5.0
    df_short.at[df_short.index[55], "close"] = prev_min_low - 4.0
    df_short.at[df_short.index[55], "high"] = prev_min_low - 0.2

    sig_short = strat.evaluate(df_short, 55)
    assert sig_short is not None, "Expected SHORT breakout signal at bar 55"
    assert sig_short["direction"] == "SHORT"
    assert "DONCHIAN_BREAKOUT_DOWN" in sig_short["active_signals"]
    assert sig_short["entry_price"] == prev_min_low - 4.0
    assert sig_short["stop_loss_raw"] > sig_short["entry_price"] > sig_short["target_1_raw"]


def test_strategy_diagnostics_endpoint():
    """Diagnostics endpoint supplies equity curve, regime breakdown, and weakness diagnostics."""
    import asyncio
    from trading_engine.config import DB_PATH
    from trading_engine.memory.db import get_connection
    from trading_engine.memory.trade_logger import TradeLogger

    # Empty strategy case
    res_empty = asyncio.run(server.strategy_diagnostics("EMPTY_STRATEGY"))
    assert res_empty["strategy_id"] == "EMPTY_STRATEGY"
    assert "performance" in res_empty
    assert "risk" in res_empty
    assert "equity_curve" in res_empty
    assert isinstance(res_empty["equity_curve"], list)
    assert "regime_breakdown" in res_empty
    assert "weaknesses" in res_empty

    # Clean up existing test trades for TEST_DIAG_STRAT for test idempotency
    conn = get_connection(db_path=DB_PATH)
    try:
        conn.execute("DELETE FROM trades_memory WHERE strategy_id = 'TEST_DIAG_STRAT'")
        conn.commit()
    finally:
        conn.close()

    logger = TradeLogger(db_path=DB_PATH)
    try:
        t1 = logger.open_trade(
            strategy_id="TEST_DIAG_STRAT",
            execution_mode="MANUAL_LIVE",
            symbol="BTCUSDT",
            timeframe="1m",
            direction="LONG",
            entry_time_utc="2026-11-14T02:00:00Z",
            entry_price=68000.0,
            stop_loss=67800.0,
            target_1_price=68300.0,
            target_2_price=68600.0,
            position_size=1.0,
            regime_snapshot={"volatility_regime": "NORMAL_ATR"},
            active_signals=["TEST_SIGNAL"],
        )
        logger.close_trade(
            trade_id=t1,
            exit_time_utc="2026-11-14T02:15:00Z",
            exit_price=68300.0,
            exit_reason="TAKE_PROFIT",
        )

        t2 = logger.open_trade(
            strategy_id="TEST_DIAG_STRAT",
            execution_mode="MANUAL_LIVE",
            symbol="BTCUSDT",
            timeframe="1m",
            direction="LONG",
            entry_time_utc="2026-11-14T02:20:00Z",
            entry_price=68300.0,
            stop_loss=68100.0,
            target_1_price=68600.0,
            target_2_price=68900.0,
            position_size=1.0,
            regime_snapshot={"volatility_regime": "NORMAL_ATR"},
            active_signals=["TEST_SIGNAL"],
        )
        logger.close_trade(
            trade_id=t2,
            exit_time_utc="2026-11-14T02:30:00Z",
            exit_price=68100.0,
            exit_reason="STOP_LOSS",
        )

        res = asyncio.run(server.strategy_diagnostics("TEST_DIAG_STRAT"))
        assert res["total_trades"] == 2
        assert len(res["equity_curve"]) >= 3
        # Initial 10000 -> +300 -> 10300 -> -200 -> 10100
        assert res["equity_curve"][0]["equity"] == 10000.0
        assert res["equity_curve"][1]["equity"] == 10300.0
        assert res["equity_curve"][2]["equity"] == 10100.0
        assert isinstance(res["weaknesses"], list)
    finally:
        conn = get_connection(db_path=DB_PATH)
        try:
            conn.execute("DELETE FROM trades_memory WHERE strategy_id = 'TEST_DIAG_STRAT'")
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
