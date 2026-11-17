"""trading_engine/tests/test_phase6_e2e_trader.py — 4-Tier Opaque-Box E2E Test Suite.

Milestone M4: Comprehensive E2E Trader Verification
Covers:
  • Tier 1: Feature Coverage (R1–R5 happy paths, schema, contracts, UI assets, baseline strategy)
  • Tier 2: Boundary & Corner Cases (R1–R5 boundary limits, HTTP 422 gates, NaN/inf sanitization, division by zero)
  • Tier 3: Cross-Feature Interactions (Feeder -> DB -> WS -> Snapshot, Manual Order -> Risk -> Logger -> Memory, Research -> Gatekeeper -> Reports, Circuit Breaker)
  • Tier 4: Real-World Trader Application Scenarios (Sizing lifecycle, viewport polling immutability, Strategy Lab diagnostics, volatility stress, lockdown defense)
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sqlite3
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

import trading_engine.config as config
import trading_engine.memory.db as db_module
import trading_engine.backend.server as server_module
import trading_engine.memory.trade_logger as logger_module
import trading_engine.validation.gatekeeper as gatekeeper_module
import trading_engine.agents.research_loop as research_module
import trading_engine.data.feature_store as feature_module
from trading_engine.data.feature_store import FeatureStore
from trading_engine.evaluation.analyzer import (
    compute_performance,
    compute_risk,
    compute_regime_breakdown,
    detect_weaknesses,
)
from trading_engine.indicators.technical import atr, donchian_channels, ema, hma, rsi
from trading_engine.memory.trade_logger import TradeLogger
from trading_engine.risk.risk_manager import RiskManager
from trading_engine.strategies.approved.baseline_demonstration_strategy import (
    BaselineDemonstrationStrategy,
)
from trading_engine.strategies.base_strategy import BaseStrategy
from trading_engine.validation.backtester import Backtester, BacktestResult
from trading_engine.validation.gatekeeper import (
    ValidationGatekeeper,
    PARAM_PCT_SHIFTS,
    HEATMAP_PASS_RATIO,
    HEATMAP_PF_MIN,
)


# =========================================================================== #
# Pure ASGI Test Client Implementation                                        #
# =========================================================================== #

class ConnectionClosedError(Exception):
    pass


class AsgiResponse:
    """Standard HTTP response returned by AsgiTestClient."""

    def __init__(self, status_code: int, headers: dict[str, str], content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class AsgiWebSocketConnection:
    """Synchronous context manager wrapping ASGI WebSocket conversation."""

    def __init__(self, app: Any, path: str):
        self.app = app
        self.path = path
        self.loop = asyncio.new_event_loop()
        self.incoming_queue: asyncio.Queue = None  # type: ignore[assignment]
        self.outgoing_queue: asyncio.Queue = None  # type: ignore[assignment]
        self.task: asyncio.Task | None = None

    def __enter__(self) -> AsgiWebSocketConnection:
        asyncio.set_event_loop(self.loop)
        self.incoming_queue = asyncio.Queue()
        self.outgoing_queue = asyncio.Queue()
        self.incoming_queue.put_nowait({"type": "websocket.connect"})

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = parsed.query.encode("utf-8")

        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query,
            "headers": [(b"host", b"127.0.0.1:8765")],
            "subprotocols": [],
            "server": ("127.0.0.1", 8765),
            "client": ("127.0.0.1", 54321),
        }

        async def receive() -> dict[str, Any]:
            return await self.incoming_queue.get()

        async def send(message: dict[str, Any]) -> None:
            await self.outgoing_queue.put(message)

        self.task = self.loop.create_task(self.app(scope, receive, send))

        # Wait for accept
        start = self.loop.run_until_complete(self.outgoing_queue.get())
        if start.get("type") != "websocket.accept":
            raise RuntimeError(f"WebSocket rejected connection: {start}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.incoming_queue.put_nowait({"type": "websocket.disconnect", "code": 1000})
            if self.task and not self.task.done():
                self.loop.run_until_complete(asyncio.wait([self.task], timeout=0.5))
        except Exception:
            pass
        finally:
            self.loop.close()

    def receive_json(self, timeout: float = 2.0) -> dict[str, Any]:
        """Receive the next text message as parsed JSON."""
        msg = self.receive_text(timeout=timeout)
        return json.loads(msg)

    def receive_text(self, timeout: float = 2.0) -> str:
        """Receive the next raw text message."""
        async def _get():
            while True:
                msg = await asyncio.wait_for(self.outgoing_queue.get(), timeout=timeout)
                if msg.get("type") == "websocket.send":
                    return msg.get("text", "")
                if msg.get("type") == "websocket.close":
                    raise ConnectionClosedError("WebSocket closed by server")

        return self.loop.run_until_complete(_get())

    def send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON text message to the server."""
        self.send_text(json.dumps(data))

    def send_text(self, text: str) -> None:
        """Send a raw text message to the server."""
        self.incoming_queue.put_nowait({"type": "websocket.receive", "text": text})


class AsgiTestClient:
    """Pure Python ASGI 3.0 test client for FastAPI / Starlette applications."""

    def __init__(self, app: Any):
        self.app = app

    def get(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> AsgiResponse:
        return self.request("GET", url, params=params, headers=headers)

    def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        data: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> AsgiResponse:
        return self.request("POST", url, params=params, json_body=json, data=data, headers=headers)

    def websocket_connect(self, url: str) -> AsgiWebSocketConnection:
        return AsgiWebSocketConnection(self.app, url)

    def request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> AsgiResponse:
        return asyncio.run(self._async_request(method, url, params, json_body, data, headers))

    async def _async_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
        req_headers: dict[str, str] | None = None,
    ) -> AsgiResponse:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        query = parsed.query

        if params:
            qs = urllib.parse.urlencode(params)
            query = f"{query}&{qs}" if query else qs

        raw_headers: list[tuple[bytes, bytes]] = []
        body = b""
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            raw_headers.append((b"content-type", b"application/json"))
        elif data is not None:
            body = data if isinstance(data, bytes) else str(data).encode("utf-8")

        raw_headers.append((b"content-length", str(len(body)).encode("utf-8")))
        raw_headers.append((b"host", b"127.0.0.1:8765"))

        if req_headers:
            for k, v in req_headers.items():
                raw_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": method.upper(),
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query.encode("utf-8"),
            "headers": raw_headers,
            "server": ("127.0.0.1", 8765),
            "client": ("127.0.0.1", 54321),
        }

        sent: list[dict[str, Any]] = []
        request_sent = False

        async def receive() -> dict[str, Any]:
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        await self.app(scope, receive, send)

        start_msg = next((m for m in sent if m["type"] == "http.response.start"), None)
        status = start_msg["status"] if start_msg else 500
        resp_headers = {}
        if start_msg and "headers" in start_msg:
            resp_headers = {
                k.decode("latin1"): v.decode("latin1") for k, v in start_msg["headers"]
            }

        resp_content = b"".join(
            [m.get("body", b"") for m in sent if m["type"] == "http.response.body"]
        )
        return AsgiResponse(status, resp_headers, resp_content)


# =========================================================================== #
# Test Isolation Fixture & App Client                                         #
# =========================================================================== #

@pytest.fixture(autouse=True)
def isolated_trading_engine_db(tmp_path, monkeypatch):
    """Guarantees tests execute against an isolated temporary SQLite database,
    protecting production trading_engine.db from modification or deletion.
    """
    test_db_path = str(tmp_path / "e2e_test_trading_engine.db")

    # 1. Initialize schema in test database
    db_module.initialize_database(test_db_path)

    # 2. Patch DB_PATH across all modules
    for mod in (
        config, server_module, db_module, logger_module,
        gatekeeper_module, research_module, feature_module,
    ):
        if hasattr(mod, "DB_PATH"):
            monkeypatch.setattr(mod, "DB_PATH", test_db_path)

    # 3. Intercept get_connection as a bulletproof safety net
    orig_get_conn = db_module.get_connection

    def safe_get_connection(db_path=None) -> sqlite3.Connection:
        if db_path is None or db_path == "trading_engine.db" or os.path.abspath(str(db_path)) == os.path.abspath("trading_engine.db"):
            return orig_get_conn(test_db_path)
        return orig_get_conn(db_path)

    monkeypatch.setattr(db_module, "get_connection", safe_get_connection)
    monkeypatch.setattr(server_module, "get_connection", safe_get_connection)

    # 4. Intercept initialize_database as well
    orig_init_db = db_module.initialize_database

    def safe_init_db(db_path=None):
        if db_path is None or db_path == "trading_engine.db" or os.path.abspath(str(db_path)) == os.path.abspath("trading_engine.db"):
            return orig_init_db(test_db_path)
        return orig_init_db(db_path)

    monkeypatch.setattr(db_module, "initialize_database", safe_init_db)

    # 5. Intercept cleanup helpers to forbid deleting production database
    def safe_cleanup(path: str) -> None:
        if os.path.abspath(str(path)) == os.path.abspath("trading_engine.db") or path == "trading_engine.db":
            raise RuntimeError("CRITICAL: Attempted to delete production trading_engine.db during test!")
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(path + suffix)
            except FileNotFoundError:
                pass

    monkeypatch.setattr("trading_engine.tests.test_phase5_research_agents._cleanup_db", safe_cleanup, raising=False)

    # 6. Reset server.live state before each test
    with server_module.live._lock:
        server_module.live.status = "RUNNING"
        server_module.live.connected_feeds = []
        server_module.live.last_candle = None
        server_module.live.positions = {}
        server_module.live.pending_manual_ticket = None
        server_module.live.clients.clear()

    yield test_db_path


@pytest.fixture
def client(isolated_trading_engine_db):
    """ASGI Test Client targeting server_module.app with isolated state."""
    return AsgiTestClient(server_module.app)


# =========================================================================== #
# Synthetic Data Helpers                                                      #
# =========================================================================== #

def _seed_bars(
    db_path: str,
    n: int = 60,
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    market_type: str = "CRYPTO_SPOT",
    base_price: float = 68000.0,
    freq_seconds: int = 60,
) -> list[dict[str, Any]]:
    """Seed synthetic OHLCV bars into ohlcv_bars table."""
    conn = db_module.get_connection(db_path)
    now = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)
    bars = []
    try:
        for i in range(n):
            t = (now - timedelta(seconds=(n - 1 - i) * freq_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
            price = base_price + (10.0 if i % 2 == 0 else -10.0) + (i * 0.5)
            bar = {
                "symbol": symbol,
                "market_type": market_type,
                "timeframe": timeframe,
                "open_time_utc": t,
                "open": price,
                "high": price + 5.0,
                "low": price - 4.0,
                "close": price + 2.0,
                "volume": 10.0 + (i % 5),
            }
            conn.execute(
                """
                INSERT OR REPLACE INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (bar["symbol"], bar["market_type"], bar["timeframe"],
                 bar["open_time_utc"], bar["open"], bar["high"], bar["low"],
                 bar["close"], bar["volume"]),
            )
            bars.append(bar)
        conn.commit()
    finally:
        conn.close()
    return bars


def _build_feature_df(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Build a deterministic feature DataFrame with OHLCV and indicators."""
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.normal(0.05, 0.4, size=n))
    dates = pd.date_range("2026-11-14 00:00", periods=n, freq="1min", tz="UTC")
    close = pd.Series(base, index=dates)
    noise = rng.normal(0, 0.2, size=n)
    open_ = close + noise
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.3, size=n))
    volume = rng.integers(100, 1000, size=n).astype(float)

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
    df["ema_12"] = ema(close, length=12)
    df["ema_26"] = ema(close, length=26)
    df["ema_20"] = ema(close, length=20)
    df["ema_50"] = ema(close, length=50)
    df["hma_20"] = hma(close, length=20)
    df["atr_14"] = atr(high, low, close, length=14)
    df["atr_14_sma"] = df["atr_14"].rolling(window=14, min_periods=1).mean()
    df["rsi_14"] = rsi(close, length=14)
    dc = donchian_channels(high, low, length=20)
    df["donchian_upper_20"] = dc["upper"]
    df["donchian_middle_20"] = dc["middle"]
    df["donchian_lower_20"] = dc["lower"]
    return df


# =========================================================================== #
# Tier 1: Feature Coverage (R1–R5, >= 25 Tests)                              #
# =========================================================================== #

def test_t1_r1_01_market_snapshot_happy_path(client, isolated_trading_engine_db):
    """R1: Happy path snapshot retrieval returns status 200 and standard metadata."""
    _seed_bars(isolated_trading_engine_db, n=60, symbol="BTCUSDT", timeframe="1m")
    res = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=1m&limit=500")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["timeframe"] == "1m"
    assert data["market_type"] == "CRYPTO_SPOT"
    assert isinstance(data["bars"], list)
    assert len(data["bars"]) == 60
    assert data["count"] == 60
    assert isinstance(data["overlays"], dict)


def test_t1_r1_02_market_snapshot_custom_symbol_timeframe(client, isolated_trading_engine_db):
    """R1: Snapshot handles distinct symbol and timeframe queries without bleeding data."""
    _seed_bars(isolated_trading_engine_db, n=55, symbol="ETHUSDT", timeframe="5m")
    res = client.get("/api/market/snapshot?symbol=ETHUSDT&timeframe=5m&limit=100")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "ETHUSDT"
    assert data["timeframe"] == "5m"
    assert data["count"] == 55


def test_t1_r1_03_snapshot_indicator_overlays_schema(client, isolated_trading_engine_db):
    """R1: Snapshot overlays dict includes all 8 indicator streams aligned with bars."""
    _seed_bars(isolated_trading_engine_db, n=70, symbol="BTCUSDT", timeframe="1m")
    res = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=1m&limit=70")
    assert res.status_code == 200
    overlays = res.json()["overlays"]
    required_keys = [
        "ema_20", "ema_50", "hma_20",
        "donchian_upper_20", "donchian_middle_20", "donchian_lower_20",
        "atr_14", "rsi_14",
    ]
    for key in required_keys:
        assert key in overlays, f"Missing overlay key {key}"
        assert len(overlays[key]) == 70, f"Overlay {key} length mismatch"


def test_t1_r1_04_snapshot_reverse_chronology_alignment(client, isolated_trading_engine_db):
    """R1: Bars and overlays follow reverse chronology (newest first, index 0 is latest bar)."""
    seeded = _seed_bars(isolated_trading_engine_db, n=60, symbol="BTCUSDT", timeframe="1m")
    res = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=1m&limit=60")
    assert res.status_code == 200
    bars = res.json()["bars"]
    assert len(bars) >= 2
    assert bars[0]["t"] > bars[1]["t"], "Bars must be ordered newest first"
    assert bars[0]["c"] == seeded[-1]["close"], "bars[0] must align with newest close"


def test_t1_r1_05_snapshot_donchian_band_relations(client, isolated_trading_engine_db):
    """R1: Donchian bands satisfy upper >= middle >= lower and middle == (upper + lower) / 2."""
    _seed_bars(isolated_trading_engine_db, n=80, symbol="BTCUSDT", timeframe="1m")
    res = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=1m&limit=80")
    overlays = res.json()["overlays"]
    uppers = overlays["donchian_upper_20"]
    middles = overlays["donchian_middle_20"]
    lowers = overlays["donchian_lower_20"]

    valid_checked = 0
    for u, m, l in zip(uppers, middles, lowers):
        if u is not None and m is not None and l is not None:
            assert u >= m >= l, f"Donchian band inversion: upper={u}, middle={m}, lower={l}"
            assert math.isclose(m, (u + l) / 2.0, rel_tol=1e-3, abs_tol=1e-3)
            valid_checked += 1
    assert valid_checked > 20, "Should have verified valid Donchian points"


def test_t1_r1_06_snapshot_rsi_atr_bounded_values(client, isolated_trading_engine_db):
    """R1: RSI overlay values are bounded within [0, 100] and ATR is non-negative."""
    _seed_bars(isolated_trading_engine_db, n=80, symbol="BTCUSDT", timeframe="1m")
    res = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=1m&limit=80")
    overlays = res.json()["overlays"]
    rsi_vals = [v for v in overlays["rsi_14"] if v is not None]
    atr_vals = [v for v in overlays["atr_14"] if v is not None]

    assert len(rsi_vals) > 0
    assert len(atr_vals) > 0
    assert all(0.0 <= v <= 100.0 for v in rsi_vals), "RSI values must be in [0, 100]"
    assert all(v >= 0.0 for v in atr_vals), "ATR values must be non-negative"


def test_t1_r1_07_chart_engine_js_viewport_persistence_contract():
    """R1: chart_engine.js provides the public ChartEngine API and handles loadSnapshot/onCandle."""
    path = "trading_engine/frontend/js/chart_engine.js"
    assert os.path.exists(path), f"{path} must exist"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "window.chartEngine" in content
    assert "loadSnapshot" in content
    assert "onCandle" in content
    assert "timeScale" in content


def test_t1_r1_08_chart_engine_volume_subpane_and_color_coding():
    """R1: Chart styling and candle color definitions are institutional-grade."""
    path = "trading_engine/frontend/js/chart_engine.js"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "upColor" in content
    assert "downColor" in content
    assert "CandlestickSeries" in content or "addCandlestickSeries" in content


def test_t1_r1_09_chart_hover_legend_and_toggle_chips_contract():
    """R1: HTML layout contains chart container and indicator hints / toggle elements."""
    path = "trading_engine/frontend/index.html"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    assert 'id="chart-container"' in content
    assert "chart-hints" in content
    assert "EMA20/50" in content
    assert "Donchian20" in content


def test_t1_r2_01_root_serves_dark_terminal_html(client):
    """R2: GET / serves the institutional dark terminal shell HTML."""
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert '<div class="terminal-shell">' in res.text
    assert "FinceptEngine" in res.text


def test_t1_r2_02_static_css_styles_http_200(client):
    """R2: GET /css/styles.css serves the dark terminal stylesheet."""
    res = client.get("/css/styles.css")
    assert res.status_code == 200
    assert "text/css" in res.headers.get("content-type", "")
    assert "terminal-shell" in res.text


def test_t1_r2_03_static_js_modules_http_200(client):
    """R2: All required frontend JS modules return HTTP 200."""
    modules = [
        "/js/chart_engine.js",
        "/js/main.js",
        "/js/footprint_ui.js",
        "/js/lab_evaluation_ui.js",
        "/js/system_monitor_ui.js",
    ]
    for mod in modules:
        res = client.get(mod)
        assert res.status_code == 200, f"Failed fetching {mod}"
        assert len(res.content) > 0, f"Empty module {mod}"


def test_t1_r2_04_static_vendor_chart_library_http_200(client):
    """R2: Vendor Lightweight Charts bundle returns HTTP 200 and valid JS content."""
    res = client.get("/vendor/lightweightcharts.standalone.production.js")
    assert res.status_code == 200
    assert len(res.content) > 50000, "Lightweight charts vendor script should be >50KB"


def test_t1_r2_05_dark_palette_tokens_in_css():
    """R2: CSS contains authentic dark institutional charcoal/slate palette tokens."""
    with open("trading_engine/frontend/css/styles.css", "r", encoding="utf-8") as f:
        css = f.read()
    # Dark background tokens
    assert "#0b0e14" in css or "#121721" in css or "#0a0a0b" in css or "#0b0c0e" in css
    assert "#121721" in css or "#1a202c" in css or "#141416" in css or "#0f0f11" in css
    # High-contrast text tokens
    assert "#e2e8f0" in css or "#cbd5e1" in css or "#e8e8ea" in css or "#c9d1d9" in css
    # Semantic accent colors (green / red)
    assert "#00e676" in css or "#27c93f" in css or "#7ee287" in css or "#26a69a" in css
    assert "#ff5252" in css or "#ff5f56" in css or "#ff9a8a" in css or "#ef5350" in css


def test_t1_r2_06_tabular_numbers_css_declaration():
    """R2: CSS applies font-variant-numeric: tabular-nums for monospaced numeric layout."""
    with open("trading_engine/frontend/css/styles.css", "r", encoding="utf-8") as f:
        css = f.read()
    assert "font-variant-numeric: tabular-nums" in css
    assert "monospace" in css


def test_t1_r2_07_navigation_tab_panels_present_in_html():
    """R2: Main index.html defines tab panels for Chart, Footprint, Lab, and Monitor."""
    with open("trading_engine/frontend/index.html", "r", encoding="utf-8") as f:
        html = f.read()
    assert 'id="tab-chart"' in html
    assert 'id="tab-footprint"' in html
    assert 'id="tab-lab"' in html
    assert 'id="tab-monitor"' in html


def test_t1_r3_01_baseline_strategy_contract_a_compliance():
    """R3: BaselineDemonstrationStrategy complies strictly with Contract A schema."""
    strat = BaselineDemonstrationStrategy()
    assert issubclass(BaselineDemonstrationStrategy, BaseStrategy)
    assert strat.strategy_id == "BASELINE_DEMO_V1"

    df = _build_feature_df(n=100)
    # Synthesize guaranteed active trigger at index 60 (bullish trend pullback bounce)
    df.loc[df.index[59], "close"] = 110.0
    df.loc[df.index[59], "ema_20"] = 111.0
    df.loc[df.index[60], "close"] = 112.5
    df.loc[df.index[60], "low"] = 110.5
    df.loc[df.index[60], "high"] = 113.0
    df.loc[df.index[60], "ema_20"] = 111.0
    df.loc[df.index[60], "ema_50"] = 105.0
    df.loc[df.index[60], "hma_20"] = 111.5
    df.loc[df.index[60], "atr_14"] = 1.5

    sig = strat.evaluate(df, current_idx=60)
    assert sig is not None, "Baseline strategy failed to emit signal on conditioned trigger bar"

    required_keys = [
        "strategy_id", "symbol", "timeframe", "timestamp_utc",
        "direction", "entry_price", "stop_loss_raw", "target_1_raw",
        "target_2_raw", "active_signals", "regime_snapshot",
    ]
    for k in required_keys:
        assert k in sig, f"Missing Contract A key: {k}"
    assert sig["strategy_id"] == "BASELINE_DEMO_V1"
    assert sig["direction"] in ("LONG", "SHORT")
    assert isinstance(sig["entry_price"], float)
    assert isinstance(sig["stop_loss_raw"], float)
    assert isinstance(sig["target_1_raw"], float)
    assert isinstance(sig["target_2_raw"], float)
    assert isinstance(sig["active_signals"], list)
    assert isinstance(sig["regime_snapshot"], dict)


def test_t1_r3_02_baseline_strategy_long_trend_pullback_trigger():
    """R3: Baseline strategy triggers LONG signal on bullish trend pullback bounce."""
    strat = BaselineDemonstrationStrategy()
    df = _build_feature_df(n=100)
    # Synthesize strong bullish alignment at index 80:
    df.loc[df.index[79], "close"] = 110.0
    df.loc[df.index[80], "close"] = 112.5
    df.loc[df.index[80], "low"] = 110.5
    df.loc[df.index[80], "high"] = 113.0
    df.loc[df.index[80], "ema_20"] = 111.0
    df.loc[df.index[80], "ema_50"] = 105.0
    df.loc[df.index[80], "hma_20"] = 111.5
    df.loc[df.index[80], "atr_14"] = 1.5

    sig = strat.evaluate(df, current_idx=80)
    assert sig is not None
    assert sig["direction"] == "LONG"
    assert sig["entry_price"] == 112.5


def test_t1_r3_03_baseline_strategy_short_trend_pullback_trigger():
    """R3: Baseline strategy triggers SHORT signal on bearish trend pullback rejection."""
    strat = BaselineDemonstrationStrategy()
    df = _build_feature_df(n=100)
    # Synthesize strong bearish alignment at index 80:
    df.loc[df.index[79], "close"] = 90.0
    df.loc[df.index[80], "close"] = 87.5
    df.loc[df.index[80], "low"] = 87.0
    df.loc[df.index[80], "high"] = 89.5
    df.loc[df.index[80], "ema_20"] = 89.0
    df.loc[df.index[80], "ema_50"] = 95.0
    df.loc[df.index[80], "hma_20"] = 88.5
    df.loc[df.index[80], "atr_14"] = 1.5

    sig = strat.evaluate(df, current_idx=80)
    assert sig is not None
    assert sig["direction"] == "SHORT"
    assert sig["entry_price"] == 87.5


def test_t1_r3_04_baseline_strategy_atr_stops_and_rr_ratios():
    """R3: Baseline strategy sets 1.5x ATR stops and 1.50 / 3.00 R:R take profits."""
    strat = BaselineDemonstrationStrategy()
    df = _build_feature_df(n=100)
    df.loc[df.index[80], "close"] = 100.0
    df.loc[df.index[80], "ema_20"] = 98.0
    df.loc[df.index[80], "ema_50"] = 95.0
    df.loc[df.index[80], "hma_20"] = 99.0
    df.loc[df.index[80], "atr_14"] = 2.0  # ATR = 2.0 -> Risk = 3.0 (1.5x)

    sig = strat.evaluate(df, current_idx=80)
    assert sig is not None
    entry = sig["entry_price"]
    stop = sig["stop_loss_raw"]
    t1 = sig["target_1_raw"]
    t2 = sig["target_2_raw"]

    risk = abs(entry - stop)
    assert math.isclose(risk, 3.0, rel_tol=1e-3)
    reward1 = abs(t1 - entry)
    assert math.isclose(reward1 / risk, 1.5, rel_tol=1e-3)
    reward2 = abs(t2 - entry)
    assert math.isclose(reward2 / risk, 3.0, rel_tol=1e-3)


def test_t1_r3_05_baseline_strategy_backtester_replay(isolated_trading_engine_db):
    """R3: Backtester replays BaselineDemonstrationStrategy producing a BacktestResult."""
    strat = BaselineDemonstrationStrategy()
    df = _build_feature_df(n=150)
    bt = Backtester(strat, account_equity=10000.0, db_path=isolated_trading_engine_db)
    res = bt.run(df, start_idx=25, end_idx=145)
    assert isinstance(res, BacktestResult)
    assert len(res.equity_curve) > 0
    assert res.total_trades >= 0
    assert hasattr(res, "profit_factor")
    assert hasattr(res, "max_drawdown_pct")


def test_t1_r4_01_position_sizing_units_formula():
    """R4: Position sizing formula computes Units = (Capital * Risk%) / |Entry - SL|."""
    rm = RiskManager(account_equity=10000.0, max_risk_per_trade_pct=1.0)
    units, risk_amt, risk_per_share = rm.size_position(68000.0, 67800.0, direction="LONG")
    assert math.isclose(units, 0.5, rel_tol=1e-5)
    assert math.isclose(risk_amt, 100.0, rel_tol=1e-5)
    assert math.isclose(risk_per_share, 200.0, rel_tol=1e-5)


def test_t1_r4_02_suggested_atr_stop_long():
    """R4: Suggested ATR stop for LONG equals Entry - (1.5 * ATR)."""
    rm = RiskManager(account_equity=10000.0, atr_stop_buffer_multiplier=1.5)
    stop = rm.atr_stop(entry_price=68000.0, atr=150.0, direction="LONG")
    expected = 68000.0 - (1.5 * 150.0)
    assert math.isclose(stop, expected, rel_tol=1e-5)


def test_t1_r4_03_suggested_atr_stop_short():
    """R4: Suggested ATR stop for SHORT equals Entry + (1.5 * ATR)."""
    rm = RiskManager(account_equity=10000.0, atr_stop_buffer_multiplier=1.5)
    stop = rm.atr_stop(entry_price=68000.0, atr=150.0, direction="SHORT")
    expected = 68000.0 + (1.5 * 150.0)
    assert math.isclose(stop, expected, rel_tol=1e-5)


def test_t1_r4_04_valid_rr_order_execution_http_200(client):
    """R4: 1-Click order ticket accepts order with valid R:R >= 1.50 and returns HTTP 200."""
    payload = {
        "strategy_id": "MANUAL_TEST",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "entry_price": 68000.0,
        "stop_loss": 67800.0,      # Risk = 200
        "target_1_price": 68400.0,  # Reward = 400 (R:R = 2.0 >= 1.50)
        "target_2_price": 68800.0,
        "position_size": 0.5,
        "notes": "Valid R:R Tier 1 Test",
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "OK"
    assert data["trade_id"].startswith("TRD_")


def test_t1_r4_05_manual_ticket_websocket_broadcast(client):
    """R4: Submitting a valid manual trade broadcasts a manual_ticket event to WebSocket clients."""
    with client.websocket_connect("/ws/live") as ws:
        init_msg = ws.receive_json()
        assert init_msg.get("type") == "snapshot"

        payload = {
            "strategy_id": "MANUAL",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "direction": "LONG",
            "entry_price": 68000.0,
            "stop_loss": 67800.0,
            "target_1_price": 68400.0,
            "position_size": 0.5,
        }
        res = client.post("/api/trades/manual", json=payload)
        assert res.status_code == 200

        ws_msg = ws.receive_json()
        assert ws_msg["type"] == "manual_ticket"
        assert ws_msg["ticket"]["symbol"] == "BTCUSDT"
        assert ws_msg["ticket"]["direction"] == "LONG"


def test_t1_r4_06_valid_short_order_execution_and_memory_logging(client, isolated_trading_engine_db):
    """R4: Happy-path SHORT manual trade executes with HTTP 200, status OPEN, and direction SHORT."""
    payload = {
        "strategy_id": "MANUAL_SHORT_TEST",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "SHORT",
        "entry_price": 68000.0,
        "stop_loss": 68400.0,      # Risk = 400.0
        "target_1_price": 67200.0,  # Reward = 800.0 (R:R = 2.0 >= 1.50)
        "target_2_price": 66800.0,  # Target 2 = 1200.0 (R:R = 3.0)
        "position_size": 0.25,
        "notes": "Valid SHORT happy-path Tier 1 Test",
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "OK"
    assert data["trade_id"].startswith("TRD_")
    trade_id = data["trade_id"]

    # Verify trade in trades_memory via /api/trades/memory endpoint
    mem_res = client.get("/api/trades/memory?strategy_id=MANUAL_SHORT_TEST")
    assert mem_res.status_code == 200
    mem_data = mem_res.json()
    assert mem_data["total"] >= 1
    matching = [t for t in mem_data["trades"] if t["trade_id"] == trade_id]
    assert len(matching) == 1
    t_record = matching[0]
    assert t_record["direction"] == "SHORT"
    assert t_record["status"] == "OPEN"
    assert math.isclose(float(t_record["entry_price"]), 68000.0, rel_tol=1e-5)
    assert math.isclose(float(t_record["stop_loss"]), 68400.0, rel_tol=1e-5)
    assert math.isclose(float(t_record["target_1_price"]), 67200.0, rel_tol=1e-5)


def test_t1_r5_01_strategy_evaluation_metrics_shape(client, isolated_trading_engine_db):
    """R5: Evaluation API returns complete performance and risk metric dictionaries."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    tid = logger.open_trade(
        strategy_id="BASELINE_DEMO_V1",
        execution_mode="MANUAL_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-14T01:00:00Z",
        entry_price=68000.0,
        stop_loss=67800.0,
        target_1_price=68400.0,
        target_2_price=None,
        position_size=1.0,
        regime_snapshot={"volatility_regime": "NORMAL_ATR"},
        active_signals=["TEST"],
    )
    logger.close_trade(
        trade_id=tid,
        exit_time_utc="2026-11-14T01:30:00Z",
        exit_price=68400.0,
        exit_reason="TAKE_PROFIT",
    )

    res = client.get("/api/evaluation/BASELINE_DEMO_V1")
    assert res.status_code == 200
    data = res.json()
    assert data["strategy_id"] == "BASELINE_DEMO_V1"
    assert data["total_trades"] == 1
    assert "win_rate_pct" in data["overall_metrics"]
    assert "profit_factor" in data["overall_metrics"]
    assert "net_pnl" in data["overall_metrics"]
    assert "max_drawdown_pct" in data["risk_metrics"]


def test_t1_r5_02_strategy_evaluation_equity_curve_array(client, isolated_trading_engine_db):
    """R5: Evaluation API returns continuous equity curve time-series array."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    t1 = logger.open_trade(
        strategy_id="TEST_EQ_STRAT",
        execution_mode="MANUAL_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-14T01:00:00Z",
        entry_price=100.0,
        stop_loss=90.0,
        target_1_price=120.0,
        target_2_price=None,
        position_size=10.0,
        regime_snapshot={},
        active_signals=[],
    )
    logger.close_trade(t1, exit_time_utc="2026-11-14T01:10:00Z", exit_price=120.0)

    t2 = logger.open_trade(
        strategy_id="TEST_EQ_STRAT",
        execution_mode="MANUAL_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-14T01:20:00Z",
        entry_price=120.0,
        stop_loss=110.0,
        target_1_price=140.0,
        target_2_price=None,
        position_size=10.0,
        regime_snapshot={},
        active_signals=[],
    )
    logger.close_trade(t2, exit_time_utc="2026-11-14T01:30:00Z", exit_price=110.0)

    res = client.get("/api/evaluation/TEST_EQ_STRAT")
    assert res.status_code == 200
    eq_curve = res.json()["equity_curve"]
    assert isinstance(eq_curve, list)
    assert len(eq_curve) >= 3
    assert eq_curve[0]["equity"] == 10000.0
    assert math.isclose(eq_curve[-1]["equity"], 10100.0, abs_tol=1.0)


def test_t1_r5_03_strategy_evaluation_regime_breakdown(client, isolated_trading_engine_db):
    """R5: Evaluation API groups closed trades by volatility regime and flags losing regimes."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    t1 = logger.open_trade(
        strategy_id="REGIME_STRAT",
        execution_mode="MANUAL_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-14T01:00:00Z",
        entry_price=100.0,
        stop_loss=90.0,
        target_1_price=120.0,
        target_2_price=None,
        position_size=10.0,
        regime_snapshot={"volatility_regime": "NORMAL_ATR"},
        active_signals=[],
    )
    logger.close_trade(t1, exit_time_utc="2026-11-14T01:10:00Z", exit_price=120.0)

    t2 = logger.open_trade(
        strategy_id="REGIME_STRAT",
        execution_mode="MANUAL_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-14T01:20:00Z",
        entry_price=120.0,
        stop_loss=110.0,
        target_1_price=140.0,
        target_2_price=None,
        position_size=10.0,
        regime_snapshot={"volatility_regime": "LOW_ATR"},
        active_signals=[],
    )
    logger.close_trade(t2, exit_time_utc="2026-11-14T01:30:00Z", exit_price=110.0)

    res = client.get("/api/evaluation/REGIME_STRAT")
    assert res.status_code == 200
    breakdown = res.json()["regime_breakdown"]
    assert "NORMAL_ATR" in breakdown
    assert "LOW_ATR" in breakdown
    assert breakdown["NORMAL_ATR"]["is_losing_regime"] is False
    assert breakdown["LOW_ATR"]["is_losing_regime"] is True


def test_t1_r5_04_strategy_evaluation_structured_weakness_list(client, isolated_trading_engine_db):
    """R5: Evaluation API returns structured list of detected weaknesses with recommendation."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    for i in range(6):
        tid = logger.open_trade(
            strategy_id="WEAK_STRAT",
            execution_mode="MANUAL_LIVE",
            symbol="BTCUSDT",
            timeframe="1m",
            direction="LONG",
            entry_time_utc=f"2026-11-14T01:{i:02d}:00Z",
            entry_price=100.0,
            stop_loss=90.0,
            target_1_price=120.0,
            target_2_price=None,
            position_size=5.0,
            regime_snapshot={"volatility_regime": "CHOPPY"},
            active_signals=[],
        )
        logger.close_trade(tid, exit_time_utc=f"2026-11-14T01:{i:02d}:30Z", exit_price=90.0)

    res = client.get("/api/evaluation/WEAK_STRAT")
    assert res.status_code == 200
    weaknesses = res.json()["weaknesses"]
    assert isinstance(weaknesses, list)
    assert len(weaknesses) > 0
    w0 = weaknesses[0]
    assert "flag" in w0
    assert "severity" in w0
    assert "recommendation" in w0
    assert w0["recommendation"] in ("ACCEPT", "REVIEW", "REJECT")


def test_t1_r5_05_validation_reports_scorecard_and_heatmap(client, isolated_trading_engine_db):
    """R5: Validation reports route returns 4-test scorecard booleans and 5x5 heatmap."""
    conn = db_module.get_connection(isolated_trading_engine_db)
    heatmap_json = json.dumps({
        "grid_size": 25,
        "cells": [{"p1": "len", "p1_value": 20, "p2": "sl", "p2_value": 1.5,
                   "profit_factor": 1.25, "passed": True}] * 25,
        "pass_ratio": 1.0,
        "passed": True,
    })
    try:
        conn.execute(
            """
            INSERT INTO validation_reports
            (report_id, candidate_strategy_id, baseline_strategy_id,
             symbol, timeframe, in_sample_metrics_json,
             out_of_sample_metrics_json, walk_forward_summary_json,
             parameter_heatmap_json, cost_stress_metrics_json,
             oos_passed, walk_forward_passed, param_stability_passed,
             cost_stress_passed, final_status, rejection_reason,
             evaluated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "REP_TEST_01", "V2_CANDIDATE_01", "BASELINE_DEMO_V1",
                "BTCUSDT", "1m",
                json.dumps({"win_rate": 0.60, "profit_factor": 1.45}),
                json.dumps({"win_rate": 0.55, "profit_factor": 1.30}),
                json.dumps({"windows_passed": 4, "total_windows": 5}),
                heatmap_json,
                json.dumps({"stressed_profit_factor": 1.20}),
                1, 1, 1, 1, "APPROVED", None,
                "2026-11-14T02:00:00Z",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    res = client.get("/api/validation/reports")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 1
    rep = data["reports"][0]
    assert rep["oos_passed"] is True
    assert rep["walk_forward_passed"] is True
    assert rep["param_stability_passed"] is True
    assert rep["cost_stress_passed"] is True
    assert rep["final_status"] == "APPROVED"
    assert rep["parameter_heatmap"]["grid_size"] == 25
    assert len(rep["parameter_heatmap"]["cells"]) == 25


def test_t1_r5_06_strategy_diagnostics_endpoint_shape(client):
    """R5: GET /api/strategy/diagnostics returns performance, risk, equity curve, and weaknesses."""
    res = client.get("/api/strategy/diagnostics?strategy_id=BASELINE_DEMO_V1")
    assert res.status_code == 200
    data = res.json()
    assert "strategy_id" in data
    assert "performance" in data
    assert "risk" in data
    assert "equity_curve" in data
    assert "regime_breakdown" in data
    assert "weaknesses" in data


# =========================================================================== #
# Tier 2: Boundary & Corner Cases (R1–R5, >= 25 Tests)                       #
# =========================================================================== #

def test_t2_r1_01_snapshot_limit_min_boundary_50(client, isolated_trading_engine_db):
    """R1: Snapshot query parameter limit=50 (exact min boundary) returns HTTP 200."""
    _seed_bars(isolated_trading_engine_db, n=60)
    res = client.get("/api/market/snapshot?limit=50")
    assert res.status_code == 200
    assert res.json()["count"] <= 50


def test_t2_r1_02_snapshot_limit_max_boundary_2000(client, isolated_trading_engine_db):
    """R1: Snapshot query parameter limit=2000 (exact max boundary) returns HTTP 200."""
    res = client.get("/api/market/snapshot?limit=2000")
    assert res.status_code == 200


def test_t2_r1_03_snapshot_limit_below_min_rejected_422(client):
    """R1: Snapshot query parameter limit=49 (below ge=50) is rejected with HTTP 422."""
    res = client.get("/api/market/snapshot?limit=49")
    assert res.status_code == 422


def test_t2_r1_04_snapshot_limit_above_max_rejected_422(client):
    """R1: Snapshot query parameter limit=2001 (above le=2000) is rejected with HTTP 422."""
    res = client.get("/api/market/snapshot?limit=2001")
    assert res.status_code == 422


def test_t2_r1_05_snapshot_limit_zero_and_negative_rejected_422(client):
    """R1: Snapshot query parameter limit=0 or negative is rejected with HTTP 422."""
    assert client.get("/api/market/snapshot?limit=0").status_code == 422
    assert client.get("/api/market/snapshot?limit=-10").status_code == 422


def test_t2_r1_06_snapshot_empty_db_graceful_response(client):
    """R1: Querying an empty database or unknown symbol returns HTTP 200 with empty collections."""
    res = client.get("/api/market/snapshot?symbol=NONEXISTENT_PAIR")
    assert res.status_code == 200
    data = res.json()
    assert data["bars"] == []
    assert data["count"] == 0
    assert data["overlays"] == {}
    assert "note" in data


def test_t2_r1_07_snapshot_warmup_nan_sanitization(client, isolated_trading_engine_db):
    """R1: Snapshot on early history (fewer than 20 bars) sanitizes NaN values to null."""
    _seed_bars(isolated_trading_engine_db, n=10)
    res = client.get("/api/market/snapshot?limit=50")
    assert res.status_code == 200
    text = res.text
    assert "NaN" not in text
    assert "Infinity" not in text
    overlays = res.json()["overlays"]
    if "ema_20" in overlays and overlays["ema_20"]:
        assert all(v is None for v in overlays["ema_20"])


def test_t2_r2_01_static_missing_file_returns_404(client):
    """R2: Missing static files under /css and /js return HTTP 404."""
    assert client.get("/css/nonexistent_file.css").status_code == 404
    assert client.get("/js/nonexistent_file.js").status_code == 404


def test_t2_r2_02_vendor_chart_filename_resolution(client):
    """R2: Exact vendor bundle path returns 200; misspelled hyphenated path returns 404."""
    assert client.get("/vendor/lightweightcharts.standalone.production.js").status_code == 200
    assert client.get("/vendor/lightweight-charts.standalone.production.js").status_code == 404


def test_t2_r2_03_root_missing_index_fallback(monkeypatch, client):
    """R2: If index.html is missing on disk, GET / returns fallback HTML without 500 error."""
    orig_exists = os.path.exists

    def mock_exists(p):
        if "index.html" in str(p):
            return False
        return orig_exists(p)

    monkeypatch.setattr(os.path, "exists", mock_exists)
    res = client.get("/")
    assert res.status_code == 200
    assert "FinceptEngine" in res.text


def test_t2_r3_01_baseline_strategy_zero_lookahead_future_mutation():
    """R3: Mutating future bars (t > T) does not alter active signal evaluation at bar T."""
    strat = BaselineDemonstrationStrategy()
    df_orig = _build_feature_df(n=120)
    T = 80
    # Condition bar T to emit an active, fully populated signal
    df_orig.loc[df_orig.index[T - 1], "close"] = 110.0
    df_orig.loc[df_orig.index[T - 1], "ema_20"] = 111.0
    df_orig.loc[df_orig.index[T], "close"] = 112.5
    df_orig.loc[df_orig.index[T], "low"] = 110.5
    df_orig.loc[df_orig.index[T], "high"] = 113.0
    df_orig.loc[df_orig.index[T], "ema_20"] = 111.0
    df_orig.loc[df_orig.index[T], "ema_50"] = 105.0
    df_orig.loc[df_orig.index[T], "hma_20"] = 111.5
    df_orig.loc[df_orig.index[T], "atr_14"] = 1.5

    sig_orig = strat.evaluate(df_orig, current_idx=T)
    assert sig_orig is not None, "Baseline strategy must emit an active signal before mutation"
    assert sig_orig["direction"] == "LONG"
    assert sig_orig["entry_price"] == 112.5

    # Drastically mutate future bars (t > T)
    df_mutated = df_orig.copy()
    df_mutated.iloc[T + 1:, df_mutated.columns.get_loc("close")] *= 50.0
    df_mutated.iloc[T + 1:, df_mutated.columns.get_loc("high")] *= 50.0
    df_mutated.iloc[T + 1:, df_mutated.columns.get_loc("low")] *= 0.1
    df_mutated.iloc[T + 1:, df_mutated.columns.get_loc("volume")] *= 1000.0

    sig_mutated = strat.evaluate(df_mutated, current_idx=T)
    assert sig_mutated is not None, "Signal must still be generated after future mutation"
    assert sig_orig == sig_mutated, "Signal changed after future mutation — look-ahead leak!"
    assert sig_mutated["entry_price"] == sig_orig["entry_price"]
    assert sig_mutated["stop_loss_raw"] == sig_orig["stop_loss_raw"]
    assert sig_mutated["target_1_raw"] == sig_orig["target_1_raw"]
    assert sig_mutated["regime_snapshot"] == sig_orig["regime_snapshot"]


def test_t2_r3_02_baseline_strategy_flat_chop_market_no_signal():
    """R3: Flat price series with zero trend returns None (no false signals in chop)."""
    strat = BaselineDemonstrationStrategy()
    n = 100
    dates = pd.date_range("2026-11-14 00:00", periods=n, freq="1min", tz="UTC")
    df_flat = pd.DataFrame(
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 100.0},
        index=dates,
    )
    df_flat["ema_20"] = 100.0
    df_flat["ema_50"] = 100.0
    df_flat["hma_20"] = 100.0
    df_flat["atr_14"] = 0.0
    df_flat["donchian_upper_20"] = 100.0
    df_flat["donchian_lower_20"] = 100.0

    for idx in range(30, 90):
        sig = strat.evaluate(df_flat, current_idx=idx)
        assert sig is None, f"Emitted signal on flat chop bar {idx}"


def test_t2_r3_03_baseline_strategy_zero_atr_guard():
    """R3: When ATR is zero, evaluate returns None to prevent zero-distance stop loss."""
    strat = BaselineDemonstrationStrategy()
    df = _build_feature_df(n=85)
    df.loc[df.index[80], "atr_14"] = 0.0
    sig = strat.evaluate(df, current_idx=80)
    assert sig is None, "Should guard against ATR=0.0"


def test_t2_r3_04_baseline_strategy_warmup_period_safe():
    """R3: Early history indices safely return None without throwing exceptions."""
    strat = BaselineDemonstrationStrategy()
    df = _build_feature_df(n=30)
    for i in range(15):
        res = strat.evaluate(df, current_idx=i)
        assert res is None


def test_t2_r3_05_baseline_strategy_custom_parameter_scaling():
    """R3: Custom parameters (sl_atr_mult=2.5, tp_rr_ratio=2.0) scale stops and targets."""
    strat = BaselineDemonstrationStrategy(params={"sl_atr_mult": 2.5, "tp_rr_ratio": 2.0})
    df = _build_feature_df(n=100)
    df.loc[df.index[80], "close"] = 100.0
    df.loc[df.index[80], "ema_20"] = 98.0
    df.loc[df.index[80], "ema_50"] = 95.0
    df.loc[df.index[80], "hma_20"] = 99.0
    df.loc[df.index[80], "atr_14"] = 2.0

    sig = strat.evaluate(df, current_idx=80)
    assert sig is not None
    entry = sig["entry_price"]
    stop = sig["stop_loss_raw"]
    t1 = sig["target_1_raw"]

    risk = abs(entry - stop)
    assert math.isclose(risk, 5.0, rel_tol=1e-3)
    reward = abs(t1 - entry)
    assert math.isclose(reward / risk, 2.0, rel_tol=1e-3)


def test_t2_r4_01_rr_strictly_rejected_at_14999(client):
    """R4: Order with R:R = 1.4999 (< 1.50) is strictly rejected with HTTP 422."""
    payload = {
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 90.0,          # Risk = 10.0
        "target_1_price": 114.999,  # Reward = 14.999 -> R:R = 1.4999
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 422
    assert "below mandatory threshold 1.50" in res.json()["detail"]


def test_t2_r4_02_rr_accepted_at_15000(client):
    """R4: Order with R:R = 1.5000 (exact boundary) is accepted with HTTP 200."""
    payload = {
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 90.0,          # Risk = 10.0
        "target_1_price": 115.000,  # Reward = 15.000 -> R:R = 1.5000
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_t2_r4_03_rr_accepted_at_15001(client):
    """R4: Order with R:R = 1.5001 (> 1.50) is accepted with HTTP 200."""
    payload = {
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "target_1_price": 115.001,
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_t2_r4_01b_short_rr_strictly_rejected_at_14999(client):
    """R4: SHORT order with R:R = 1.4999 (< 1.50) is strictly rejected with HTTP 422."""
    payload = {
        "direction": "SHORT",
        "entry_price": 100.0,
        "stop_loss": 110.0,        # Risk = 10.0
        "target_1_price": 85.001,  # Reward = 14.999 -> R:R = 1.4999
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 422
    assert "below mandatory threshold 1.50" in res.json()["detail"]


def test_t2_r4_02b_short_rr_accepted_at_15000(client):
    """R4: SHORT order with R:R = 1.5000 (exact boundary) is accepted with HTTP 200."""
    payload = {
        "direction": "SHORT",
        "entry_price": 100.0,
        "stop_loss": 110.0,        # Risk = 10.0
        "target_1_price": 85.000,  # Reward = 15.000 -> R:R = 1.5000
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_t2_r4_03b_short_rr_accepted_at_15001(client):
    """R4: SHORT order with R:R = 1.5001 (> 1.50) is accepted with HTTP 200."""
    payload = {
        "direction": "SHORT",
        "entry_price": 100.0,
        "stop_loss": 110.0,        # Risk = 10.0
        "target_1_price": 84.999,  # Reward = 15.001 -> R:R = 1.5001
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_t2_r4_04_zero_risk_distance_division_by_zero_422(client):
    """R4: Order with StopLoss == Entry (Zero Risk) is trapped and rejected with HTTP 422."""
    payload = {
        "direction": "LONG",
        "entry_price": 68000.0,
        "stop_loss": 68000.0,
        "target_1_price": 68500.0,
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 422


def test_t2_r4_05_directional_inversion_long_stop_above_entry_422(client):
    """R4: LONG order with StopLoss >= Entry is rejected with HTTP 422."""
    payload = {
        "direction": "LONG",
        "entry_price": 68000.0,
        "stop_loss": 68100.0,
        "target_1_price": 68500.0,
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 422
    assert "Inverted stops" in res.json()["detail"]


def test_t2_r4_06_directional_inversion_short_stop_below_entry_422(client):
    """R4: SHORT order with StopLoss <= Entry is rejected with HTTP 422."""
    payload = {
        "direction": "SHORT",
        "entry_price": 68000.0,
        "stop_loss": 67900.0,
        "target_1_price": 67500.0,
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 422
    assert "Inverted stops" in res.json()["detail"]


def test_t2_r4_07_directional_inversion_long_target_below_entry_422(client):
    """R4: LONG order with Target <= Entry is rejected with HTTP 422."""
    payload = {
        "direction": "LONG",
        "entry_price": 68000.0,
        "stop_loss": 67800.0,
        "target_1_price": 67500.0,
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 422


def test_t2_r4_08_directional_inversion_short_target_above_entry_422(client):
    """R4: SHORT order with Target >= Entry is rejected with HTTP 422."""
    payload = {
        "direction": "SHORT",
        "entry_price": 68000.0,
        "stop_loss": 68200.0,
        "target_1_price": 68500.0,
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 422


def test_t2_r4_09_invalid_entry_and_position_size_400(client):
    """R4: Negative or zero entry price or position size returns HTTP 400."""
    bad_payloads = [
        {"direction": "LONG", "entry_price": -100.0, "stop_loss": -150.0, "target_1_price": 0.0, "position_size": 1.0},
        {"direction": "LONG", "entry_price": 68000.0, "stop_loss": 67800.0, "target_1_price": 68400.0, "position_size": 0.0},
        {"direction": "LONG", "entry_price": 68000.0, "stop_loss": 67800.0, "target_1_price": 68400.0, "position_size": -0.5},
    ]
    for p in bad_payloads:
        res = client.post("/api/trades/manual", json=p)
        assert res.status_code == 400


def test_t2_r4_10_malformed_payload_types_400(client):
    """R4: Non-numeric payload types for prices trigger HTTP 400."""
    payload = {
        "direction": "LONG",
        "entry_price": "invalid_string_price",
        "stop_loss": 67800.0,
        "target_1_price": 68400.0,
        "position_size": 1.0,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 400


def test_t2_r5_01_evaluation_zero_trades_graceful_200(client):
    """R5: Evaluation on strategy with 0 closed trades returns HTTP 200 without throwing 500."""
    res = client.get("/api/evaluation/DUMMY_UNKNOWN_STRAT_0_TRADES")
    assert res.status_code == 200
    data = res.json()
    assert data["total_trades"] == 0
    assert data["equity_curve"] == []
    assert data["regime_breakdown"] == {}
    assert data["weaknesses"] == []


def test_t2_r5_02_validation_reports_empty_db_graceful_200(client):
    """R5: Validation reports query on a fresh database returns HTTP 200 with empty list."""
    res = client.get("/api/validation/reports")
    assert res.status_code == 200
    data = res.json()
    assert data["reports"] == []
    assert data["count"] == 0


def test_t2_r5_03_json_sanitization_infinity_and_nan():
    """R5: _sanitize_json recursively converts inf, -inf, and nan into None (JSON null)."""
    payload = {
        "profit_factor": float("inf"),
        "neg_inf": float("-inf"),
        "nan_metric": float("nan"),
        "valid_val": 42.5,
        "nested": {"deep_inf": float("inf"), "list_with_nan": [float("nan"), 10.0]},
    }
    cleaned = server_module._sanitize_json(payload)
    assert cleaned["profit_factor"] is None
    assert cleaned["neg_inf"] is None
    assert cleaned["nan_metric"] is None
    assert cleaned["valid_val"] == 42.5
    assert cleaned["nested"]["deep_inf"] is None
    assert cleaned["nested"]["list_with_nan"][0] is None
    assert cleaned["nested"]["list_with_nan"][1] == 10.0

    dumped = json.dumps(cleaned)
    assert "Infinity" not in dumped
    assert "NaN" not in dumped


def test_t2_r5_04_heatmap_5x5_grid_dimension_and_thresholds(isolated_trading_engine_db):
    """R5: Parameter heatmap produces exactly 25 perturbed cells over top 2 parameters."""
    strat = BaselineDemonstrationStrategy()
    gk = ValidationGatekeeper(candidate=strat, baseline=strat, db_path=isolated_trading_engine_db)
    df = _build_feature_df(n=120)
    heatmap = gk._parameter_heatmap(df, start_idx=25, end_idx=100)
    assert heatmap["grid_size"] == 25
    assert len(heatmap["cells"]) == 25
    assert len(heatmap["param_names"]) == 2
    for cell in heatmap["cells"]:
        assert "p1" in cell and "p2" in cell
        assert "profit_factor" in cell
        assert "passed" in cell
    assert 0.0 <= heatmap["pass_ratio"] <= 1.0


def test_t2_r5_05_regime_breakdown_corrupt_json_handled():
    """R5: Trade records with None or corrupted regime_snapshot are safely grouped into UNKNOWN."""
    trades = [
        {"net_pnl": 50.0, "regime_snapshot": None},
        {"net_pnl": -30.0, "regime_snapshot": "corrupt_json_{{"},
        {"net_pnl": 20.0, "regime_snapshot": {}},
    ]
    breakdown = compute_regime_breakdown(trades)
    assert "UNKNOWN" in breakdown
    assert breakdown["UNKNOWN"]["trade_count"] == 3


def test_t2_r5_06_weakness_detection_below_min_trades_threshold():
    """R5: Sample size guard in detect_weaknesses suppresses noise when closed trades < 5."""
    trades = [{"net_pnl": -100.0, "regime_snapshot": {"volatility_regime": "CHOPPY"}}] * 2
    report = detect_weaknesses(trades, min_trades_for_regime=5)
    assert report["flags"] == []
    assert report["severity"] == "LOW"
    assert report["recommendation"] == "ACCEPT"


# =========================================================================== #
# Tier 3: Cross-Feature Interactions (>= 5 Tests)                            #
# =========================================================================== #

def test_t3_01_feeder_sqlite_websocket_snapshot_pipeline(client, isolated_trading_engine_db):
    """Tier 3: Feeder insertion -> SQLite WAL -> WebSocket streaming -> Snapshot visibility."""
    with client.websocket_connect("/ws/live") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "snapshot"

        # 1. Synthesize candle and insert to SQLite
        bar = {
            "t": "2026-11-14T12:00:00Z",
            "o": 67000.0, "h": 67200.0, "l": 66900.0, "c": 67150.0, "v": 15.25,
        }
        conn = db_module.get_connection(isolated_trading_engine_db)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("BTCUSDT", "CRYPTO_SPOT", "1m", bar["t"], bar["o"], bar["h"], bar["l"], bar["c"], bar["v"]),
            )
            conn.commit()
        finally:
            conn.close()

        # 2. Broadcast candle via server live state
        server_module.live.set_candle(bar)
        asyncio.run(server_module.live.broadcast({"type": "candle", "payload": bar}))

        # 3. WebSocket client receives live candle
        candle_msg = ws.receive_json()
        assert candle_msg["type"] == "candle"
        assert candle_msg["payload"]["c"] == 67150.0

        # 4. REST snapshot reflects newest bar
        res = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=1m&limit=50")
        assert res.status_code == 200
        assert res.json()["bars"][0]["c"] == 67150.0


def test_t3_02_manual_order_risk_gating_logger_memory_flow(client, isolated_trading_engine_db):
    """Tier 3: 1-Click order -> Risk gate validation -> TradeLogger insertion -> Memory retrieval."""
    with client.websocket_connect("/ws/live") as ws:
        _ = ws.receive_json()

        payload = {
            "strategy_id": "MANUAL",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "direction": "LONG",
            "entry_price": 68000.0,
            "stop_loss": 67600.0,      # Risk = 400
            "target_1_price": 68800.0,  # Reward = 800 (R:R = 2.0 >= 1.50)
            "position_size": 0.5,
            "notes": "Tier 3 integration order",
        }
        res = client.post("/api/trades/manual", json=payload)
        assert res.status_code == 200
        trade_id = res.json()["trade_id"]

        ws_msg = ws.receive_json()
        assert ws_msg["type"] == "manual_ticket"
        assert ws_msg["ticket"]["trade_id"] == trade_id

        mem_res = client.get("/api/trades/memory?strategy_id=MANUAL")
        assert mem_res.status_code == 200
        trades = mem_res.json()["trades"]
        matched = [t for t in trades if t["trade_id"] == trade_id]
        assert len(matched) == 1
        assert matched[0]["entry_price"] == 68000.0
        assert matched[0]["stop_loss"] == 67600.0
        assert matched[0]["status"] == "OPEN"


def test_t3_03_research_trigger_to_validation_reports_persistence(client, isolated_trading_engine_db):
    """Tier 3: Research trigger executes loop, evaluates gatekeeper, and persists scorecard report."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    for i in range(8):
        tid = logger.open_trade(
            strategy_id="EMA_BREAKOUT_V1",
            execution_mode="MANUAL_LIVE",
            symbol="BTCUSDT",
            timeframe="1m",
            direction="LONG",
            entry_time_utc=f"2026-11-14T01:{i:02d}:00Z",
            entry_price=100.0,
            stop_loss=90.0,
            target_1_price=120.0,
            target_2_price=None,
            position_size=1.0,
            regime_snapshot={"volatility_regime": "NORMAL_ATR"},
            active_signals=[],
        )
        logger.close_trade(tid, exit_time_utc=f"2026-11-14T01:{i:02d}:30Z", exit_price=90.0)

    fs = FeatureStore(db_path=isolated_trading_engine_db)
    df_features = _build_feature_df(n=250)
    fs.write_features("BTCUSDT", "1m", df_features)

    res = client.post("/api/research/trigger", json={"symbol": "BTCUSDT", "timeframe": "1m"})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["final_status"] in ("APPROVED", "REJECTED")

    rep_res = client.get("/api/validation/reports")
    assert rep_res.status_code == 200
    reports = rep_res.json()["reports"]
    assert len(reports) >= 1
    r0 = reports[0]
    for key in ("oos_passed", "walk_forward_passed", "param_stability_passed", "cost_stress_passed", "final_status"):
        assert key in r0


def test_t3_04_paper_simulator_circuit_breaker_to_status_update(client):
    """Tier 3: RiskManager consecutive loss circuit breaker trip and server status reporting.

    Validates both sides of the circuit breaker lifecycle across component boundaries:
      1. RiskManager internal state: consecutive losses reach threshold, triggering
         is_halted=True, setting halt_reason='MAX_CONSECUTIVE_LOSSES', and denying
         subsequent trades via can_open_trade().allowed=False.
      2. Server status interface: when the engine enters CIRCUIT_BREAKER_HALTED state,
         the REST API (/api/system/status) faithfully reflects this status to the
         frontend monitoring dashboard and connected WebSocket clients.
    """
    rm = RiskManager(account_equity=10000.0, max_consecutive_losses=2)
    rm.close_trade(-100.0, 9900.0)
    assert rm.is_halted is False
    rm.close_trade(-100.0, 9800.0)
    assert rm.is_halted is True
    assert rm.halt_reason == "MAX_CONSECUTIVE_LOSSES"
    assert rm.can_open_trade().allowed is False

    # Simulate server engine status transition triggered by risk circuit breaker
    server_module.live.status = "CIRCUIT_BREAKER_HALTED"
    res = client.get("/api/system/status")
    assert res.status_code == 200
    assert res.json()["status"] == "CIRCUIT_BREAKER_HALTED"


def test_t3_05_snapshot_indicator_overlays_multi_timeframe_isolation(client, isolated_trading_engine_db):
    """Tier 3: Snapshot calculation maintains complete timeframe isolation without bleed."""
    _seed_bars(isolated_trading_engine_db, n=80, symbol="BTCUSDT", timeframe="1m")
    res_1m = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=1m&limit=80")
    assert res_1m.status_code == 200
    assert res_1m.json()["count"] == 80
    assert len(res_1m.json()["overlays"]["ema_20"]) == 80

    res_5m = client.get("/api/market/snapshot?symbol=BTCUSDT&timeframe=5m&limit=50")
    assert res_5m.status_code == 200
    assert res_5m.json()["count"] == 0
    assert res_5m.json()["bars"] == []


# =========================================================================== #
# Tier 4: Real-World Application Scenarios (>= 5 Scenarios)                  #
# =========================================================================== #

def test_t4_01_real_trader_session_atr_sizing_and_position_lifecycle(client, isolated_trading_engine_db):
    """Scenario 4.1: Real trader session ($50k capital, 2% risk, ATR sizing, execution, closure)."""
    capital = 50000.0
    risk_pct = 2.0
    risk_budget = capital * (risk_pct / 100.0)  # $1,000
    current_price = 65000.0
    atr_val = 300.0
    sl_buffer = 1.5 * atr_val  # 450.0
    stop_loss = current_price - sl_buffer  # 64550.0
    pos_size = round(risk_budget / sl_buffer, 4)  # 2.2222
    target_1 = current_price + (2.0 * sl_buffer)  # 65900.0 (R:R = 2.0)

    order_payload = {
        "strategy_id": "MANUAL_PRO_DESK",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "entry_price": current_price,
        "stop_loss": stop_loss,
        "target_1_price": target_1,
        "position_size": pos_size,
        "notes": "Trader session scenario 4.1",
    }
    res = client.post("/api/trades/manual", json=order_payload)
    assert res.status_code == 200
    trade_id = res.json()["trade_id"]

    open_res = client.get("/api/trades/memory?status=OPEN")
    assert open_res.status_code == 200
    open_trades = open_res.json()["trades"]
    matching = [t for t in open_trades if t["trade_id"] == trade_id]
    assert len(matching) == 1
    assert matching[0]["position_size"] == pos_size

    logger = TradeLogger(db_path=isolated_trading_engine_db)
    logger.close_trade(
        trade_id=trade_id,
        exit_time_utc="2026-11-14T12:45:00Z",
        exit_price=target_1,
        exit_reason="TARGET_1_REACHED",
    )

    closed_res = client.get("/api/trades/memory?status=CLOSED")
    assert closed_res.status_code == 200
    closed_trades = closed_res.json()["trades"]
    closed_t = [t for t in closed_trades if t["trade_id"] == trade_id][0]
    assert closed_t["exit_reason"] == "TARGET_1_REACHED"
    assert closed_t["net_pnl"] > 1900.0
    assert closed_t["r_multiple"] >= 1.9


def test_t4_02_multi_turn_viewport_polling_stability(client, isolated_trading_engine_db):
    """Scenario 4.2: Multi-turn viewport polling stability simulation across 5s intervals."""
    _seed_bars(isolated_trading_engine_db, n=80, symbol="BTCUSDT", timeframe="1m")
    snap_0 = client.get("/api/market/snapshot?symbol=BTCUSDT&limit=80").json()
    bars_0 = snap_0["bars"]
    assert len(bars_0) == 80

    conn = db_module.get_connection(isolated_trading_engine_db)
    new_t = "2026-11-14T12:01:00Z"
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO ohlcv_bars
            (symbol, market_type, timeframe, open_time_utc, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("BTCUSDT", "CRYPTO_SPOT", "1m", new_t, 68200.0, 68250.0, 68180.0, 68240.0, 20.0),
        )
        conn.commit()
    finally:
        conn.close()

    snap_1 = client.get("/api/market/snapshot?symbol=BTCUSDT&limit=80").json()
    bars_1 = snap_1["bars"]
    assert bars_1[0]["t"] == new_t
    assert bars_1[1]["t"] == bars_0[0]["t"]
    assert bars_1[1]["c"] == bars_0[0]["c"]

    for _ in range(10):
        burst_res = client.get("/api/market/snapshot?symbol=BTCUSDT&limit=50")
        assert burst_res.status_code == 200


def test_t4_03_strategy_lab_evaluation_and_regime_diagnostics(client, isolated_trading_engine_db):
    """Scenario 4.3: End-to-end Strategy Lab workflow evaluating equity curves and diagnostics."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    for i in range(15):
        tid = logger.open_trade(
            strategy_id="BASELINE_DEMO_V1",
            execution_mode="MANUAL_LIVE",
            symbol="BTCUSDT",
            timeframe="1m",
            direction="LONG",
            entry_time_utc=f"2026-11-14T01:{i:02d}:00Z",
            entry_price=100.0,
            stop_loss=90.0,
            target_1_price=120.0,
            target_2_price=None,
            position_size=10.0,
            regime_snapshot={"volatility_regime": "NORMAL_ATR"},
            active_signals=[],
        )
        exit_p = 120.0 if i < 10 else 90.0
        logger.close_trade(tid, exit_time_utc=f"2026-11-14T01:{i:02d}:30Z", exit_price=exit_p)

    for i in range(15):
        tid = logger.open_trade(
            strategy_id="BASELINE_DEMO_V1",
            execution_mode="MANUAL_LIVE",
            symbol="BTCUSDT",
            timeframe="1m",
            direction="LONG",
            entry_time_utc=f"2026-11-14T02:{i:02d}:00Z",
            entry_price=100.0,
            stop_loss=90.0,
            target_1_price=120.0,
            target_2_price=None,
            position_size=10.0,
            regime_snapshot={"volatility_regime": "LOW_ATR"},
            active_signals=[],
        )
        exit_p = 120.0 if i < 3 else 90.0
        logger.close_trade(tid, exit_time_utc=f"2026-11-14T02:{i:02d}:30Z", exit_price=exit_p)

    res = client.get("/api/evaluation/BASELINE_DEMO_V1")
    assert res.status_code == 200
    data = res.json()
    assert data["total_trades"] == 30
    assert len(data["equity_curve"]) >= 30
    assert data["regime_breakdown"]["LOW_ATR"]["is_losing_regime"] is True
    weakness_flags = [w["flag"] for w in data["weaknesses"]]
    assert any("LOW_ATR" in f for f in weakness_flags)


def test_t4_04_extreme_volatility_spread_widening_and_risk_gating(client):
    """Scenario 4.4: Volatility stress testing (sub-threshold R:R, inverted stops, execution)."""
    res1 = client.post("/api/trades/manual", json={
        "direction": "LONG", "entry_price": 68000.0, "stop_loss": 67500.0,
        "target_1_price": 68600.0,
        "position_size": 1.0,
    })
    assert res1.status_code == 422

    res2 = client.post("/api/trades/manual", json={
        "direction": "LONG", "entry_price": 68000.0, "stop_loss": 68500.0,
        "target_1_price": 69000.0, "position_size": 1.0,
    })
    assert res2.status_code == 422

    res3 = client.post("/api/trades/manual", json={
        "direction": "LONG", "entry_price": 68000.0, "stop_loss": 66000.0,
        "target_1_price": 72000.0,
        "position_size": 0.25,
    })
    assert res3.status_code == 200
    assert res3.json()["ok"] is True


def test_t4_05_circuit_breaker_lockdown_defense(client):
    """Scenario 4.5: System resilience under malformed order flood followed by circuit breaker lockdown."""
    for i in range(15):
        bad_payload = {
            "direction": "LONG",
            "entry_price": -50.0 if i % 2 == 0 else 68000.0,
            "stop_loss": 67800.0,
            "target_1_price": 67000.0,
            "position_size": 0.0 if i % 2 == 1 else 1.0,
        }
        res = client.post("/api/trades/manual", json=bad_payload)
        assert res.status_code in (400, 422)

    health_res = client.get("/api/system/status")
    assert health_res.status_code == 200

    server_module.live.status = "CIRCUIT_BREAKER_HALTED"
    server_module.live.add_activity(
        "RISK_MANAGER", "CIRCUIT_BREAKER_TRIPPED",
        "Automated lockdown after consecutive losses",
        {"halt_reason": "MAX_CONSECUTIVE_LOSSES"},
    )

    status_res = client.get("/api/system/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "CIRCUIT_BREAKER_HALTED"
    recent_acts = status_res.json()["recent_activity"]
    assert any("CIRCUIT_BREAKER_TRIPPED" in a["event_type"] for a in recent_acts)
