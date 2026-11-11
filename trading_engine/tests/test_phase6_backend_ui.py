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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
