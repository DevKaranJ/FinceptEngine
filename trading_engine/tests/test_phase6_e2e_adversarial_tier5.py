"""trading_engine/tests/test_phase6_e2e_adversarial_tier5.py — Tier 5 Adversarial Hardening Suite.

Milestone 5 Phase 2: White-Box Stress Testing & Edge-Case Coverage for FinceptEngine:
  • Extreme & Boundary Values (Trillion-dollar notional, 1e-8 fractional sizing, zero/negative equity, NaN/Inf)
  • Concurrency & Race Conditions (Concurrent multi-threaded orders, SQLite WAL locking, duplicate IDs)
  • Execution Realism & Slippage Gaps (Price gap opening beyond stop, take-profit gaps, scratch fee friction)
  • Protocol & Malformed Payloads (Unexpected fields, invalid JSON bytes, inverted directions, R:R precision)
  • WebSocket Stream Resilience (Rapid client churn, corrupt frames, ping recovery, dead socket pruning)
  • Database & Memory Integrity (Double-close idempotency, MAE/MFE immutability, SQL injection immunity)
  • Mathematical Pathologies (Zero volatility, flash crashes, 1000x pumps, Wilder's RSI, Supertrend NaN latches)
  • Strategy & Risk Edge Cases (Micro-price stop losses, dual-trend conflicts, leverage caps, position stacking)
  • Evaluation & Diagnostics Serialization (100% win/loss trades, break-even PF, RFC 8259 JSON compliance)
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sqlite3
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
from trading_engine.backend.server import app, _sanitize_json
from trading_engine.data.clock import iso_now_utc
from trading_engine.data.feature_store import FeatureStore
from trading_engine.evaluation.analyzer import (
    compute_performance,
    compute_risk,
    compute_regime_breakdown,
    detect_weaknesses,
    weakness_report_json,
)
from trading_engine.indicators.statistical import (
    hurst_exponent,
    linear_regression_slope,
    relative_strength,
    rolling_zscore,
    volatility_percentile,
)
from trading_engine.indicators.structure import dynamic_trendline, opening_range, pdh_pdl_pdc
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
from trading_engine.memory.db import initialize_database, get_connection
from trading_engine.memory.trade_logger import TradeLogger
from trading_engine.risk.risk_manager import RiskManager
from trading_engine.execution.paper_simulator import PaperSimulator, PaperPosition
from trading_engine.strategies.approved.baseline_demonstration_strategy import (
    BaselineDemonstrationStrategy,
)
from trading_engine.validation.backtester import Backtester
from trading_engine.validation.gatekeeper import ValidationGatekeeper


# =========================================================================== #
# ASGI Pure-Python Test Client & WebSocket Wrapper                            #
# =========================================================================== #

class ConnectionClosedError(Exception):
    pass


class AsgiResponse:
    def __init__(self, status_code: int, headers: dict[str, str], content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        # Strict RFC 8259 JSON parse check: disallow Infinity and NaN
        if "Infinity" in self.text or "NaN" in self.text:
            raise ValueError(f"Non-compliant RFC 8259 JSON: {self.text[:100]}")
        return json.loads(self.text)


class AsgiWebSocketConnection:
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
        msg = self.receive_text(timeout=timeout)
        return json.loads(msg)

    def receive_text(self, timeout: float = 2.0) -> str:
        async def _get():
            while True:
                msg = await asyncio.wait_for(self.outgoing_queue.get(), timeout=timeout)
                if msg.get("type") == "websocket.send":
                    return msg.get("text", "")
                if msg.get("type") == "websocket.close":
                    raise ConnectionClosedError("WebSocket closed by server")

        return self.loop.run_until_complete(_get())

    def send_json(self, data: dict[str, Any]) -> None:
        self.send_text(json.dumps(data))

    def send_text(self, text: str) -> None:
        self.incoming_queue.put_nowait({"type": "websocket.receive", "text": text})


class AsgiTestClient:
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
# Test Isolation Fixture (Protects production trading_engine.db)             #
# =========================================================================== #

@pytest.fixture(autouse=True)
def isolated_trading_engine_db(tmp_path, monkeypatch):
    """Protects production trading_engine.db from any mutation or deletion."""
    test_db_path = str(tmp_path / "tier5_adversarial_test.db")
    db_module.initialize_database(test_db_path)

    for mod in (
        config, server_module, db_module, logger_module,
        gatekeeper_module, research_module, feature_module,
    ):
        if hasattr(mod, "DB_PATH"):
            monkeypatch.setattr(mod, "DB_PATH", test_db_path)

    orig_get_conn = db_module.get_connection

    def safe_get_connection(db_path=None) -> sqlite3.Connection:
        if db_path is None or db_path == "trading_engine.db" or os.path.abspath(str(db_path)) == os.path.abspath("trading_engine.db"):
            return orig_get_conn(test_db_path)
        return orig_get_conn(db_path)

    monkeypatch.setattr(db_module, "get_connection", safe_get_connection)
    monkeypatch.setattr(server_module, "get_connection", safe_get_connection)

    with server_module.live._lock:
        server_module.live.status = "RUNNING"
        server_module.live.connected_feeds = []
        server_module.live.last_candle = None
        server_module.live.positions = {}
        server_module.live.pending_manual_ticket = None
        server_module.live.clients.clear()

    yield test_db_path


@pytest.fixture
def isolated_adv_db(isolated_trading_engine_db):
    """Alias fixture for compatibility."""
    return isolated_trading_engine_db


@pytest.fixture
def client(isolated_trading_engine_db):
    return AsgiTestClient(server_module.app)


# =========================================================================== #
# 1. Extreme & Boundary Values                                                #
# =========================================================================== #

def test_adv_t5_01_extreme_trillion_dollar_notional(client, isolated_trading_engine_db):
    """Verify extreme $10^12 notional order parses, persists to SQLite, and computes costs."""
    payload = {
        "strategy_id": "INSTITUTIONAL_WHALE",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "target_1_price": 52000.0,
        "position_size": 20000000.0,  # 20M units @ 50k = $1 Trillion notional
        "notes": "Adversarial extreme size test",
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    trade_id = res.json()["trade_id"]

    logger = TradeLogger(db_path=isolated_trading_engine_db)
    trade = logger.get_trade(trade_id)
    assert trade is not None
    assert trade["position_size"] == 20000000.0
    assert trade["entry_price"] == 50000.0

    rm = RiskManager(account_equity=1e14)
    notional = trade["entry_price"] * trade["position_size"]
    assert notional == 1e12
    slippage = rm.slippage_cost(notional)
    assert slippage == 1e8  # $100 Million slippage @ 1 bp


def test_adv_t5_02_fractional_sub_satoshi_position_sizing(client, isolated_trading_engine_db):
    """Verify fractional sub-satoshi sizing (1e-8) maintains positive denominator guards."""
    payload = {
        "strategy_id": "MICRO_SCALPER",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "entry_price": 50000.0,
        "stop_loss": 40000.0,
        "target_1_price": 70000.0,
        "position_size": 1e-8,
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    trade_id = res.json()["trade_id"]

    logger = TradeLogger(db_path=isolated_trading_engine_db)
    closed = logger.close_trade(
        trade_id,
        exit_time_utc="2026-11-17T07:00:00Z",
        exit_price=70000.0,
        exit_reason="TARGET_1",
    )
    assert closed is not None
    assert closed["status"] == "CLOSED"
    assert closed["gross_pnl"] > 0
    assert not math.isnan(closed["r_multiple"])
    assert not math.isinf(closed["r_multiple"])


def test_adv_t5_03_zero_equity_circuit_breaker_behavior():
    """Verify RiskManager behavior with exact zero equity."""
    rm = RiskManager(account_equity=0.0)
    pos_size, risk_amt, rps = rm.size_position(100.0, 95.0)
    assert pos_size == 0.0
    assert risk_amt == 0.0
    assert rps == 5.0


def test_adv_t5_04_negative_equity_guard():
    """Verify negative equity prevents opening positive positions."""
    rm = RiskManager(account_equity=-5000.0)
    pos_size, risk_amt, _ = rm.size_position(100.0, 95.0)
    assert pos_size <= 0.0


def test_adv_t5_05_nan_in_order_payload_rejected_422(client):
    """Verify NaN strings or values in prices trigger HTTP 400 or 422 cleanly."""
    res = client.post("/api/trades/manual", json={
        "direction": "LONG",
        "entry_price": "NaN",
        "stop_loss": 90.0,
        "target_1_price": 120.0,
        "position_size": 1.0,
    })
    assert res.status_code in (400, 422)


def test_adv_t5_06_infinite_target_handling_overflow_protection(client):
    """Verify Infinity in targets does not crash server with unhandled 500 OverflowError."""
    res = client.post("/api/trades/manual", json={
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "target_1_price": "Infinity",
        "position_size": 1.0,
    })
    # Must reject cleanly with client error, never internal 500
    assert res.status_code in (400, 422)


# =========================================================================== #
# 2. Concurrency & Race Conditions                                            #
# =========================================================================== #

def test_adv_t5_07_concurrent_rapid_manual_orders_wal_integrity(client, isolated_trading_engine_db):
    """Verify 20 rapid simultaneous manual orders commit to SQLite WAL without locking."""
    errors = []
    trade_ids = []

    def submit_order(i: int):
        order = {
            "strategy_id": f"CONCURRENT_BOT_{i}",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "direction": "LONG",
            "entry_price": 60000.0 + i,
            "stop_loss": 59000.0,
            "target_1_price": 62000.0 + i,
            "position_size": 0.1,
            "notes": f"thread_{i}",
        }
        try:
            res = client.post("/api/trades/manual", json=order)
            if res.status_code == 200:
                trade_ids.append(res.json()["trade_id"])
            else:
                errors.append((i, res.status_code, res.text))
        except Exception as exc:
            errors.append((i, type(exc).__name__, str(exc)))

    threads = [threading.Thread(target=submit_order, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent order errors: {errors}"
    assert len(trade_ids) == 20
    assert len(set(trade_ids)) == 20  # All IDs must be strictly unique

    mem_res = client.get("/api/trades/memory?limit=50")
    assert mem_res.status_code == 200
    assert mem_res.json()["total"] >= 20


def test_adv_t5_08_duplicate_trade_id_integrity_error(isolated_trading_engine_db):
    """Verify passing an identical trade_id twice raises IntegrityError without leaking connection."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    tid = "DUPLICATE_TEST_ID_001"
    logger.open_trade(
        strategy_id="TEST",
        execution_mode="MANUAL_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-17T06:00:00Z",
        entry_price=100.0,
        stop_loss=90.0,
        target_1_price=120.0,
        target_2_price=None,
        position_size=1.0,
        regime_snapshot={},
        active_signals=[],
        trade_id=tid,
    )

    with pytest.raises(sqlite3.IntegrityError):
        logger.open_trade(
            strategy_id="TEST",
            execution_mode="MANUAL_LIVE",
            symbol="BTCUSDT",
            timeframe="1m",
            direction="LONG",
            entry_time_utc="2026-11-17T06:01:00Z",
            entry_price=101.0,
            stop_loss=91.0,
            target_1_price=121.0,
            target_2_price=None,
            position_size=1.0,
            regime_snapshot={},
            active_signals=[],
            trade_id=tid,
        )


def test_adv_t5_09_concurrent_read_write_wal_non_blocking(client, isolated_trading_engine_db):
    """Verify readers on snapshot/memory do not block concurrent writers in SQLite WAL mode."""
    stop_event = threading.Event()
    read_counts = [0]
    write_counts = [0]

    def writer_loop():
        i = 0
        while not stop_event.is_set():
            client.post("/api/trades/manual", json={
                "direction": "LONG",
                "entry_price": 50000.0 + i,
                "stop_loss": 49000.0,
                "target_1_price": 52000.0,
                "position_size": 0.1,
            })
            write_counts[0] += 1
            i += 1
            if write_counts[0] >= 10:
                break

    def reader_loop():
        while not stop_event.is_set():
            res = client.get("/api/market/snapshot?limit=50")
            assert res.status_code == 200
            read_counts[0] += 1
            if write_counts[0] >= 10:
                break

    t_writer = threading.Thread(target=writer_loop)
    t_reader = threading.Thread(target=reader_loop)

    t_writer.start()
    t_reader.start()

    t_writer.join(timeout=5.0)
    t_reader.join(timeout=5.0)
    stop_event.set()

    assert write_counts[0] >= 5
    assert read_counts[0] >= 5


# =========================================================================== #
# 3. Execution Realism & Slippage Gaps                                        #
# =========================================================================== #

def test_adv_t5_10_execution_gap_through_stop_loss_realism(isolated_trading_engine_db):
    """Verify gap-down bar triggering stop loss fills realistically at the gap price rather than impossible ideal stop."""
    strat = BaselineDemonstrationStrategy()
    sim = PaperSimulator(strategy=strat, account_equity=10000.0, db_path=isolated_trading_engine_db)

    trade_id = sim.logger.open_trade(
        strategy_id="GAP_AUDIT",
        execution_mode="PAPER_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-17T00:00:00Z",
        entry_price=100.0,
        stop_loss=95.0,
        target_1_price=110.0,
        target_2_price=120.0,
        position_size=10.0,
        regime_snapshot={},
        active_signals=[],
    )
    pos = PaperPosition(
        trade_id=trade_id,
        strategy_id="GAP_AUDIT",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_price=100.0,
        stop_loss=95.0,
        target_1=110.0,
        target_2=120.0,
        position_size=10.0,
        entry_time_utc="2026-11-17T00:00:00Z",
    )
    sim.positions[trade_id] = pos

    # Crash bar: High=88.0, Low=80.0, Close=82.0 (entire bar below stop 95.0)
    res = sim._check_exits(pos, high=88.0, low=80.0, close=82.0, current_time_utc="2026-11-17T00:01:00Z")
    assert res.action == "CLOSED_STOP_LOSS"
    # Realistic gap fill occurs at bar high (88.0) when whole bar trades below stop
    assert res.exit_price == 88.0


def test_adv_t5_11_short_execution_gap_through_stop_loss_realism(isolated_trading_engine_db):
    """Verify SHORT position on gap-up bar triggers stop exit with realistic gap price."""
    strat = BaselineDemonstrationStrategy()
    sim = PaperSimulator(strategy=strat, account_equity=10000.0, db_path=isolated_trading_engine_db)

    trade_id = sim.logger.open_trade(
        strategy_id="SHORT_GAP_AUDIT",
        execution_mode="PAPER_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="SHORT",
        entry_time_utc="2026-11-17T00:00:00Z",
        entry_price=100.0,
        stop_loss=105.0,
        target_1_price=90.0,
        target_2_price=80.0,
        position_size=10.0,
        regime_snapshot={},
        active_signals=[],
    )
    pos = PaperPosition(
        trade_id=trade_id,
        strategy_id="SHORT_GAP_AUDIT",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="SHORT",
        entry_price=100.0,
        stop_loss=105.0,
        target_1=90.0,
        target_2=80.0,
        position_size=10.0,
        entry_time_utc="2026-11-17T00:00:00Z",
    )
    sim.positions[trade_id] = pos

    # Gap-up bar: Low=110.0, High=115.0, Close=112.0 (entire bar above stop 105.0)
    res = sim._check_exits(pos, high=115.0, low=110.0, close=112.0, current_time_utc="2026-11-17T00:01:00Z")
    assert res.action == "CLOSED_STOP_LOSS"
    # Realistic gap fill occurs at bar low (110.0) when whole bar trades above stop
    assert res.exit_price == 110.0


def test_adv_t5_12_scratch_trade_fee_slippage_friction(isolated_trading_engine_db):
    """Verify that a scratch trade (exit == entry) incurs loss due to fee/slippage friction."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    tid = logger.open_trade(
        strategy_id="SCRATCH_TEST",
        execution_mode="PAPER_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-17T00:00:00Z",
        entry_price=100.0,
        stop_loss=90.0,
        target_1_price=120.0,
        target_2_price=None,
        position_size=10.0,
        regime_snapshot={},
        active_signals=[],
    )
    closed = logger.close_trade(
        tid,
        exit_time_utc="2026-11-17T00:05:00Z",
        exit_price=100.0,  # Exact scratch
        slippage_cost=2.0,
        commission_cost=2.0,
        exit_reason="MANUAL_SCRATCH",
    )
    assert closed["gross_pnl"] == 0.0
    assert closed["net_pnl"] == -4.0
    assert closed["net_pnl"] < closed["gross_pnl"]


# =========================================================================== #
# 4. Protocol & Malformed Payloads                                            #
# =========================================================================== #

def test_adv_t5_13_payload_injection_unexpected_fields_ignored(client):
    """Verify unexpected/malformed fields in payload are safely discarded without schema fault."""
    payload = {
        "direction": "LONG",
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "target_1_price": 52000.0,
        "position_size": 1.0,
        "__proto__": {"polluted": True},
        "admin": True,
        "drop_table": "'; DROP TABLE trades_memory; --",
        "nested_unknown": {"deep": [1, 2, 3]},
    }
    res = client.post("/api/trades/manual", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_adv_t5_14_malformed_json_bytes_returns_400(client):
    """Verify sending unparseable raw bytes returns HTTP 400 or 422."""
    res = client.post("/api/trades/manual", data=b"{bad_json_not_closed: ")
    assert res.status_code in (400, 422)


def test_adv_t5_15_missing_required_fields_boundary_validation(client):
    """Verify completely empty payload or missing entry_price returns HTTP 400."""
    res = client.post("/api/trades/manual", json={})
    assert res.status_code == 400
    assert "entry_price and position_size must be > 0" in res.json()["detail"]


def test_adv_t5_16_non_numeric_strings_in_float_fields_400(client):
    """Verify strings where floats expected return HTTP 400 with invalid payload message."""
    res = client.post("/api/trades/manual", json={
        "direction": "LONG",
        "entry_price": "one_thousand",
        "stop_loss": 900.0,
        "target_1_price": 1200.0,
        "position_size": 1.0,
    })
    assert res.status_code == 400
    assert "invalid payload" in res.json()["detail"]


def test_adv_t5_17_direction_inversion_boundary_matrix(client):
    """Verify comprehensive directional inversion validation returns HTTP 422."""
    # 1. Invalid direction
    r1 = client.post("/api/trades/manual", json={
        "direction": "SIDEWAYS", "entry_price": 100.0, "stop_loss": 90.0,
        "target_1_price": 120.0, "position_size": 1.0,
    })
    assert r1.status_code == 422

    # 2. LONG target 2 <= target 1
    r2 = client.post("/api/trades/manual", json={
        "direction": "LONG", "entry_price": 100.0, "stop_loss": 90.0,
        "target_1_price": 120.0, "target_2_price": 115.0, "position_size": 1.0,
    })
    assert r2.status_code == 422
    assert "target_2_price" in r2.json()["detail"]

    # 3. SHORT target 2 >= target 1
    r3 = client.post("/api/trades/manual", json={
        "direction": "SHORT", "entry_price": 100.0, "stop_loss": 110.0,
        "target_1_price": 80.0, "target_2_price": 85.0, "position_size": 1.0,
    })
    assert r3.status_code == 422
    assert "target_2_price" in r3.json()["detail"]


def test_adv_t5_18_rr_threshold_precision_matrix(client):
    """Verify exact sub-penny R:R threshold precision boundaries."""
    # 1.4990 -> 422
    r1 = client.post("/api/trades/manual", json={
        "direction": "LONG", "entry_price": 100.0, "stop_loss": 90.0,
        "target_1_price": 114.990, "position_size": 1.0,
    })
    assert r1.status_code == 422

    # 1.4999 -> 422
    r2 = client.post("/api/trades/manual", json={
        "direction": "LONG", "entry_price": 100.0, "stop_loss": 90.0,
        "target_1_price": 114.999, "position_size": 1.0,
    })
    assert r2.status_code == 422

    # 1.5000 -> 200
    r3 = client.post("/api/trades/manual", json={
        "direction": "LONG", "entry_price": 100.0, "stop_loss": 90.0,
        "target_1_price": 115.000, "position_size": 1.0,
    })
    assert r3.status_code == 200


# =========================================================================== #
# 5. WebSocket Stream Resilience                                              #
# =========================================================================== #

def test_adv_t5_19_websocket_rapid_client_churn_no_leak(client):
    """Verify rapid connecting and disconnecting of 15 WS clients cleans up live.clients."""
    for _ in range(15):
        with client.websocket_connect("/ws/live") as ws:
            snap = ws.receive_json()
            assert snap["type"] == "snapshot"

    with server_module.live._lock:
        assert len(server_module.live.clients) == 0


def test_adv_t5_20_websocket_corrupt_frames_recovery(client):
    """Verify server survives corrupted non-JSON frames and recovers to process ping/pong."""
    with client.websocket_connect("/ws/live") as ws:
        _ = ws.receive_json()

        # Send corrupt string frames
        ws.send_text("MALFORMED_NON_JSON_FRAME_{{{")
        ws.send_text("!@#$%^&*()_+")

        # Send valid ping immediately after
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_adv_t5_21_websocket_unknown_message_types_graceful_ack(client):
    """Verify unknown message types receive an acknowledgment rather than terminating connection."""
    with client.websocket_connect("/ws/live") as ws:
        _ = ws.receive_json()

        ws.send_json({"type": "UNREGISTERED_OPCODE", "data": 42})
        ack = ws.receive_json()
        assert ack["type"] == "ack"
        assert ack["received"]["type"] == "UNREGISTERED_OPCODE"


def test_adv_t5_22_websocket_broadcast_with_dead_client_pruning(client):
    """Verify broadcast handles stale/dead clients while delivering to active clients."""
    with client.websocket_connect("/ws/live") as ws_alive:
        _ = ws_alive.receive_json()

        # Simulate dead socket by registering a mock that throws
        class MockDeadSocket:
            async def send_text(self, text):
                raise RuntimeError("Socket disconnected abruptly")

        dead_mock = MockDeadSocket()
        with server_module.live._lock:
            server_module.live.clients.append(dead_mock)  # type: ignore[arg-type]

        # Trigger broadcast
        asyncio.run(server_module.live.broadcast({"type": "status", "payload": {"status": "ACTIVE"}}))

        msg = ws_alive.receive_json()
        assert msg["type"] == "status"
        assert msg["payload"]["status"] == "ACTIVE"

        with server_module.live._lock:
            assert dead_mock not in server_module.live.clients


# =========================================================================== #
# 6. Database & State Integrity                                               #
# =========================================================================== #

def test_adv_t5_23_trade_logger_double_close_idempotent(isolated_trading_engine_db):
    """Verify closing an already CLOSED trade returns None without mutating record."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    tid = logger.open_trade(
        strategy_id="TEST_DOUBLE_CLOSE",
        execution_mode="PAPER_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-17T06:00:00Z",
        entry_price=100.0,
        stop_loss=90.0,
        target_1_price=120.0,
        target_2_price=None,
        position_size=1.0,
        regime_snapshot={},
        active_signals=[],
    )
    first_close = logger.close_trade(tid, exit_time_utc="2026-11-17T06:10:00Z", exit_price=120.0)
    assert first_close is not None
    assert first_close["status"] == "CLOSED"

    # Second close attempt
    second_close = logger.close_trade(tid, exit_time_utc="2026-11-17T06:20:00Z", exit_price=130.0)
    assert second_close is None

    final_record = logger.get_trade(tid)
    assert final_record["exit_price"] == 120.0  # Remains original exit price


def test_adv_t5_24_trade_logger_update_mae_mfe_on_closed_trade_noop(isolated_trading_engine_db):
    """Verify MAE/MFE cannot be retroactively updated after trade is CLOSED."""
    logger = TradeLogger(db_path=isolated_trading_engine_db)
    tid = logger.open_trade(
        strategy_id="TEST_MAE_MFE",
        execution_mode="PAPER_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-17T06:00:00Z",
        entry_price=100.0,
        stop_loss=90.0,
        target_1_price=120.0,
        target_2_price=None,
        position_size=1.0,
        regime_snapshot={},
        active_signals=[],
    )
    logger.update_mae_mfe(tid, current_price=105.0, current_high=108.0, current_low=98.0)
    logger.close_trade(tid, exit_time_utc="2026-11-17T06:05:00Z", exit_price=105.0)

    pre_mutate = logger.get_trade(tid)
    mfe_before = pre_mutate["mfe_pct"]

    # Attempt to mutate after close
    logger.update_mae_mfe(tid, current_price=200.0, current_high=250.0, current_low=190.0)
    post_mutate = logger.get_trade(tid)
    assert post_mutate["mfe_pct"] == mfe_before


def test_adv_t5_25_sql_injection_defense_in_evaluation_and_memory(client):
    """Verify SQL injection strings in query parameters are safely parameterized."""
    malicious = "BASELINE'; DROP TABLE trades_memory; --"
    res1 = client.get(f"/api/evaluation/{malicious}")
    assert res1.status_code == 200

    res2 = client.get(f"/api/trades/memory?strategy_id={malicious}")
    assert res2.status_code == 200

    # Ensure trades_memory table is still intact
    status_res = client.get("/api/system/status")
    assert status_res.status_code == 200


# =========================================================================== #
# Tier 5.7: Mathematical Pathologies in Indicators                            #
# =========================================================================== #

def test_adv_quant_01_rsi_monotonic_rally_no_nan():
    """ADV-01: RSI must evaluate to 100.0 (not NaN) during a pure monotonic rally."""
    n = 60
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    # Monotonically increasing close prices: zero losses
    close = pd.Series(np.arange(100.0, 100.0 + n), index=dates)
    rsi_vals = rsi(close, length=14)
    valid_window = rsi_vals.iloc[14:]
    # Wilder's definition: when avg_loss == 0, RSI = 100.0, never NaN
    assert not valid_window.isna().any(), f"RSI produced NaN during monotonic rally: {valid_window.tail()}"
    assert np.allclose(valid_window, 100.0, atol=1e-3), f"RSI should be 100.0 on pure rally, got: {valid_window.tail(3)}"


def test_adv_quant_02_rsi_flat_market_stability():
    """ADV-02: Flat market (H=L=C) must produce bounded stable RSI (50.0 or 0.0), not NaN."""
    n = 60
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    flat_close = pd.Series(100.0, index=dates)
    rsi_vals = rsi(flat_close, length=14)
    valid_window = rsi_vals.iloc[14:]
    # Should not produce NaN beyond warmup
    assert not valid_window.isna().any(), f"RSI produced NaN on flat market: {valid_window.tail()}"
    assert ((valid_window >= 0.0) & (valid_window <= 100.0)).all()


def test_adv_quant_03_atr_flat_market_zero_no_crash():
    """ADV-03: Zero volatility flat market yields ATR=0.0 without NaN or inf."""
    n = 60
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    high = pd.Series(100.0, index=dates)
    low = pd.Series(100.0, index=dates)
    close = pd.Series(100.0, index=dates)
    atr_vals = atr(high, low, close, length=14)
    valid_window = atr_vals.iloc[14:]
    assert not valid_window.isna().any()
    assert (valid_window == 0.0).all()


def test_adv_quant_04_supertrend_flat_market_nan_resilience():
    """ADV-04: Supertrend must not latch into an infinite NaN state in flat markets."""
    n = 60
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    high = pd.Series(100.0, index=dates)
    low = pd.Series(100.0, index=dates)
    close = pd.Series(100.0, index=dates)
    st = supertrend(high, low, close, period=10, multiplier=3.0)
    st_vals = st["supertrend"].iloc[10:]
    assert not st_vals.isna().any(), f"Supertrend latched NaN post-warmup: {st_vals.tolist()}"


def test_adv_quant_05_flash_crash_indicators_no_overflow():
    """ADV-05: 99.9% single-bar flash crash shock preserves finite numeric bounds."""
    n = 80
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    close = pd.Series(100.0, index=dates)
    high = pd.Series(105.0, index=dates)
    low = pd.Series(95.0, index=dates)

    # Flash crash on bar 50: drop to 0.01
    close.iloc[50] = 0.01
    high.iloc[50] = 100.0
    low.iloc[50] = 0.01
    close.iloc[51:] = 0.01
    high.iloc[51:] = 0.02
    low.iloc[51:] = 0.01

    e = ema(close, length=20)
    h = hma(close, length=20)
    a = atr(high, low, close, length=14)
    m = macd(close)

    for name, series in [("ema", e), ("hma", h), ("atr", a), ("macd", m["macd"])]:
        valid = series.iloc[30:]
        assert np.isfinite(valid).all(), f"{name} produced inf/nan on flash crash: {valid.iloc[20:25]}"


def test_adv_quant_06_pump_1000x_numerical_stability():
    """ADV-06: 1000x sudden pump in a single bar does not overflow float64 or NaN rolling z-score."""
    n = 80
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    close = pd.Series(50.0, index=dates)
    close.iloc[50:] = 50000.0  # 1000x jump

    z = rolling_zscore(close, window=20)
    valid_post_pump = z.iloc[50:]
    assert np.isfinite(valid_post_pump).all()
    assert valid_post_pump.iloc[0] > 3.0  # Statistical outlier flagged


def test_adv_quant_07_pdh_pdl_pdc_non_monotonic_timestamps():
    """ADV-07: pdh_pdl_pdc maintains exact index alignment even with non-monotonic timestamps."""
    dates = list(pd.date_range("2026-01-01", periods=10, freq="1h", tz="UTC"))
    dates[3], dates[7] = dates[7], dates[3]  # Scramble order
    df = pd.DataFrame({"high": 110.0, "low": 90.0, "close": 100.0}, index=dates)

    res = pdh_pdl_pdc(df["high"], df["low"], df["close"])
    # The output Series MUST match the original Series index, not the sorted index
    assert res["pdh"].index.equals(df.index), "pdh index misaligned with input series!"


def test_adv_quant_08_pdh_pdl_pdc_single_day_boundary():
    """ADV-08: Intraday data with only 1 calendar day safely handles missing prior day."""
    dates = pd.date_range("2026-01-01 09:15", periods=50, freq="1min", tz="UTC")
    df = pd.DataFrame({"high": 110.0, "low": 90.0, "close": 100.0}, index=dates)
    res = pdh_pdl_pdc(df["high"], df["low"], df["close"])
    # Should return all NaN without KeyError or crash
    assert len(res["pdh"]) == 50
    assert res["pdh"].isna().all()


# =========================================================================== #
# Tier 5.8: Strategy & Risk Engine Edge Cases                                 #
# =========================================================================== #

def test_adv_quant_09_baseline_micro_price_positive_stop_loss():
    """ADV-09: Micro-priced asset (0.0001) must never generate a negative stop-loss."""
    strat = BaselineDemonstrationStrategy()
    n = 80
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "open": 0.0001,
            "high": 0.00015,
            "low": 0.00008,
            "close": 0.0001,
            "volume": 1000.0,
            "ema_20": 0.00009,
            "ema_50": 0.00008,
            "hma_20": 0.00009,
            "atr_14": 0.0001,  # Large relative ATR
            "donchian_upper_20": 0.00012,
            "donchian_lower_20": 0.00008,
        },
        index=dates,
    )
    # Trigger long breakout on bar 79
    df.loc[df.index[78], "close"] = 0.00009
    df.loc[df.index[79], "close"] = 0.00014
    df.loc[df.index[79], "high"] = 0.00016

    sig = strat.evaluate(df, current_idx=79)
    if sig is not None:
        assert sig["stop_loss_raw"] > 0.0, f"Negative stop loss generated: {sig['stop_loss_raw']}"


def test_adv_quant_10_risk_manager_tight_stop_leverage_limit():
    """ADV-10: Microscopic stop distance (|entry - stop| -> 0) must cap position size and notional."""
    rm = RiskManager(account_equity=10000.0, max_risk_per_trade_pct=1.0)
    # Entry: 100.0, Stop: 99.999999 -> distance = 0.000001
    size, risk_dollars, risk_per_share = rm.size_position(entry_price=100.0, stop_loss=99.999999, direction="LONG")

    notional = size * 100.0
    # On a $10,000 account, leverage must not exceed realistic safety bounds (e.g. max 50x or $500k notional)
    max_reasonable_notional = 10000.0 * 50.0  # 50x max leverage
    assert notional <= max_reasonable_notional, f"Leverage exploded to ${notional:,.2f} on a $10k account!"


def test_adv_quant_11_baseline_dual_trend_conflict_evaluation():
    """ADV-11: Conflicting bull/bear trend indicators evaluate deterministically without crash."""
    strat = BaselineDemonstrationStrategy()
    n = 80
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    # Condition: EMA fast > EMA slow (bull), but Close < EMA slow (bear)
    df = pd.DataFrame(
        {
            "open": 98.0,
            "high": 99.0,
            "low": 96.0,
            "close": 97.0,
            "volume": 100.0,
            "ema_20": 102.0,  # Fast > Slow -> Bull
            "ema_50": 100.0,  # Close < Slow -> Bear
            "hma_20": 98.0,
            "atr_14": 2.0,
            "donchian_upper_20": 105.0,
            "donchian_lower_20": 95.0,
        },
        index=dates,
    )
    # Should evaluate without exception
    sig = strat.evaluate(df, current_idx=70)
    assert sig is None or sig["direction"] in ("LONG", "SHORT")


# =========================================================================== #
# Tier 5.9: Evaluation & Diagnostics Serialization Pathologies               #
# =========================================================================== #

def test_adv_quant_12_evaluation_zero_loss_rfc8259_json_compliance():
    """ADV-12: 100% win trades (gross_loss = 0) must serialize to valid RFC 8259 JSON without bare 'Infinity'."""
    trades = [
        {"net_pnl": 50.0, "r_multiple": 1.5, "direction": "LONG", "exit_reason": "TAKE_PROFIT"},
        {"net_pnl": 30.0, "r_multiple": 2.0, "direction": "SHORT", "exit_reason": "TAKE_PROFIT"},
    ]
    report_str = weakness_report_json(trades)
    assert "Infinity" not in report_str, "weakness_report_json leaked bare 'Infinity' into JSON!"
    # Verify strict JSON parsing works
    parsed = json.loads(report_str)
    assert parsed is not None


def test_adv_quant_13_evaluation_breakeven_profit_factor_zero():
    """ADV-13: All break-even trades (net_pnl == 0.0) must have profit factor 0.0, not inf."""
    trades = [
        {"net_pnl": 0.0, "r_multiple": 0.0, "direction": "LONG", "exit_reason": "TIME_EXIT"},
        {"net_pnl": 0.0, "r_multiple": 0.0, "direction": "SHORT", "exit_reason": "TIME_EXIT"},
    ]
    perf = compute_performance(trades)
    assert perf["profit_factor"] == 0.0, f"Expected PF 0.0 for break-even, got {perf['profit_factor']}"


def test_adv_quant_14_evaluation_api_raw_perf_sanitization(client, isolated_adv_db):
    """ADV-14: GET /api/evaluation/{strategy_id} must sanitize raw 'performance' and 'overall_metrics' fields."""
    logger = TradeLogger(db_path=isolated_adv_db)
    # Single winning trade -> profit factor is inf/none
    tid = logger.open_trade(
        strategy_id="TEST_ADV_14",
        execution_mode="MANUAL_LIVE",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        entry_time_utc="2026-11-17T01:00:00Z",
        entry_price=100.0,
        stop_loss=90.0,
        target_1_price=120.0,
        target_2_price=None,
        position_size=1.0,
        regime_snapshot={},
        active_signals=[],
    )
    logger.close_trade(tid, exit_time_utc="2026-11-17T01:10:00Z", exit_price=120.0, exit_reason="TAKE_PROFIT")

    res = client.get("/api/evaluation/TEST_ADV_14")
    assert res.status_code == 200
    # Must be valid RFC 8259 JSON (client.json() enforces "Infinity" not in res.text)
    data = res.json()
    assert "performance" in data
    # profit_factor must serialize to None (null) rather than bare Infinity
    assert data["performance"]["profit_factor"] is None or isinstance(data["performance"]["profit_factor"], (int, float))


def test_adv_quant_15_sanitize_json_numpy_and_tuple_resilience():
    """ADV-15: _sanitize_json handles numpy ndarrays, numpy scalars, and tuples recursively."""
    payload = {
        "tuple_data": (1.0, float("nan"), float("inf")),
        "numpy_nan": np.float64(np.nan),
        "numpy_inf": np.float64(np.inf),
        "numpy_array": np.array([10.0, np.nan, np.inf]),
    }
    cleaned = _sanitize_json(payload)
    # Verify it can be cleanly serialized with standard json.dumps
    dumped = json.dumps(cleaned)
    assert "Infinity" not in dumped
    assert "NaN" not in dumped


def test_adv_quant_16_gatekeeper_oos_zero_baseline_trades_rejection(isolated_adv_db):
    """ADV-16: ValidationGatekeeper must not auto-pass candidate if baseline has zero OOS trades."""
    strat_candidate = BaselineDemonstrationStrategy()
    strat_baseline = BaselineDemonstrationStrategy()
    gk = ValidationGatekeeper(candidate=strat_candidate, baseline=strat_baseline, db_path=isolated_adv_db)

    # 100 bars of data
    dates = pd.date_range("2026-01-01", periods=100, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "open": 100.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 100.0,
            "ema_20": 100.0, "ema_50": 100.0, "hma_20": 100.0, "atr_14": 1.0,
            "donchian_upper_20": 102.0, "donchian_lower_20": 98.0,
        },
        index=dates,
    )
    report = gk.evaluate(df, symbol="BTCUSDT", timeframe="1m")
    # Zero trades should result in REJECTED, never APPROVED
    assert report.final_status == "REJECTED"


def test_adv_quant_17_backtester_whipsaw_concurrent_positions(isolated_adv_db):
    """ADV-17: Backtester whipsaw signals must not result in unlimited unbounded position stacking."""
    strat = BaselineDemonstrationStrategy()
    bt = Backtester(strat, account_equity=10000.0, db_path=isolated_adv_db)

    # Synthetic whipsaw data
    n = 80
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame(
        {
            "open": 100.0, "high": 105.0, "low": 95.0, "close": 100.0, "volume": 100.0,
            "ema_20": 98.0, "ema_50": 95.0, "hma_20": 99.0, "atr_14": 2.0,
            "donchian_upper_20": 102.0, "donchian_lower_20": 98.0,
        },
        index=dates,
    )
    # Alternate breakouts to force entry signals on every bar
    for i in range(40, 60):
        df.loc[df.index[i], "close"] = 104.0 if i % 2 == 0 else 99.0
        df.loc[df.index[i], "high"] = 106.0 if i % 2 == 0 else 100.0

    res = bt.run(df, start_idx=30, end_idx=70)
    # Total open positions at any one bar must not exceed account risk limits
    assert len(bt.positions) <= 5, f"Unbounded position stacking: {len(bt.positions)} positions open concurrently!"


def test_adv_quant_18_volatility_percentile_output_range():
    """ADV-18: volatility_percentile must output values strictly within [0.0, 100.0] or NaN."""
    n = 300
    dates = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    np.random.seed(42)
    prices = 100.0 * np.exp(np.cumsum(np.random.normal(0, 0.01, size=n)))
    close = pd.Series(prices, index=dates)

    vp = volatility_percentile(close, window=20, lookback=50)
    valid = vp.dropna()
    assert (valid >= 0.0).all() and (valid <= 100.0).all(), (
        f"Volatility percentile out of bounds [0, 100]: min={valid.min()}, max={valid.max()}"
    )
