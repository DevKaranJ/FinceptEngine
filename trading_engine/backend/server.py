"""backend/server.py — FastAPI REST + WebSocket hub (Phase 6).

REST endpoints:
  GET  /api/system/status          Engine status + recent activity timeline.
  GET  /api/market/snapshot        Historical OHLCV + indicator overlays.
  GET  /api/trades/memory          Paginated trade logs (MAE/MFE/regime).
  POST /api/trades/manual          Log human-executed trade (manual order ticket).
  GET  /api/evaluation/{strategy_id} Performance / Risk / Regime / Weaknesses.
  POST /api/research/trigger       Trigger 4-role AI research loop (V2 gating).
  GET  /api/validation/reports     V1 vs V2 scorecard + heatmap JSON.

WebSocket:
  WS   /ws/live                    Streams candles, paper positions, status badges,
                                   and manual order tickets to the UI.

Zero look-ahead: every read uses t <= T. Data is sourced from SQLite WAL mode so
live WebSocket writes and backtest reads never block.
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from trading_engine.config import (
    DB_PATH,
    DEFAULT_SLIPPAGE_BP,
    CRYPTO_TRADEABLE_PAIRS,
    BINANCE_SPOT_TAKER_BP,
)
from trading_engine.data.clock import iso_now_utc, MarketSession
from trading_engine.memory.db import get_connection, initialize_database, log_activity
from trading_engine.memory.trade_logger import TradeLogger
from trading_engine.data.feature_store import FeatureStore
from trading_engine.evaluation.analyzer import (
    compute_performance,
    compute_risk,
    compute_regime_breakdown,
    detect_weaknesses,
)
from trading_engine.validation.backtester import Backtester
from trading_engine.validation.gatekeeper import ValidationGatekeeper
from trading_engine.strategies.base_strategy import BaseStrategy
from trading_engine.strategies.approved.ema_breakout_v1 import EmaBreakoutV1
from trading_engine.indicators.technical import (
    ema as _ema,
    sma as _sma,
    rsi as _rsi,
    atr as _atr,
    hma as _hma,
    donchian_channels as _donchian,
)

# --------------------------------------------------------------------------- #
# App & paths                                                                 #
# --------------------------------------------------------------------------- #
app = FastAPI(title="FinceptEngine — FastAPI Backend", version="0.1.0")

_frontend_dir = "trading_engine/frontend"
_static_dir = "trading_engine/frontend/vendor"
app.mount("/vendor", StaticFiles(directory=_static_dir), name="vendor")

_engine_started_utc = iso_now_utc()

# --------------------------------------------------------------------------- #
# In-memory live state (populated by the WebSocket publisher)                #
# --------------------------------------------------------------------------- #
class _LiveState:
    """Thread-safe live state shared by REST handlers and WebSocket publisher."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.status: str = "RUNNING"
        self.connected_feeds: list[str] = []
        self.total_strategies_tested: int = 0
        self.approved_count: int = 0
        self.last_candle: dict[str, Any] | None = None
        self.positions: dict[str, dict[str, Any]] = {}
        self.pending_manual_ticket: dict[str, Any] | None = None
        self.clients: list[WebSocket] = []

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "connected_feeds": list(self.connected_feeds),
                "total_strategies_tested": self.total_strategies_tested,
                "approved_count": self.approved_count,
                "uptime_s": self._uptime_s(),
                "last_candle": self.last_candle,
                "positions": self.positions,
                "pending_manual_ticket": self.pending_manual_ticket,
            }

    def _uptime_s(self) -> float:
        try:
            started = datetime.fromisoformat(_engine_started_utc.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - started).total_seconds()
        except Exception:
            return 0.0

    async def broadcast(self, message: dict[str, Any]) -> None:
        text = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        with self._lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            with self._lock:
                for ws in dead:
                    if ws in self.clients:
                        self.clients.remove(ws)

    def register(self, ws: WebSocket) -> None:
        with self._lock:
            if ws not in self.clients:
                self.clients.append(ws)

    def unregister(self, ws: WebSocket) -> None:
        with self._lock:
            if ws in self.clients:
                self.clients.remove(ws)

    def set_candle(self, candle: dict[str, Any]) -> None:
        with self._lock:
            self.last_candle = candle

    def set_positions(self, positions: dict[str, dict[str, Any]]) -> None:
        with self._lock:
            self.positions = dict(positions)

    def set_manual_ticket(self, ticket: dict[str, Any] | None) -> None:
        with self._lock:
            self.pending_manual_ticket = ticket

    def add_activity(self, component: str, event_type: str, summary: str,
                     details: dict[str, Any] | None = None) -> None:
        try:
            log_activity(component, event_type, summary, details, db_path=DB_PATH)
        except Exception:
            pass


live = _LiveState()


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for key in ("regime_snapshot_json", "active_signals_json", "parameters_json"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except Exception:
                d[key] = {}
    return d


def _sanitize_json(obj: Any) -> Any:
    """Replace Infinity/-Infinity/NaN with JSON-safe null so responses serialize."""
    if isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    return obj


def _ohlcv_query(
    symbol: str,
    timeframe: str,
    limit: int,
    market_type: str = "CRYPTO_SPOT",
) -> tuple[str, list[Any]]:
    q = """
        SELECT open_time_utc, open, high, low, close, volume, quote_volume,
               taker_buy_vol, trade_count
        FROM ohlcv_bars
        WHERE symbol = ? AND timeframe = ? AND market_type = ?
        ORDER BY open_time_utc DESC
        LIMIT ?
    """
    return q, [symbol, timeframe, market_type, limit]


# --------------------------------------------------------------------------- #
# REST: root (serve frontend)                                                 #
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve the dark-mode terminal frontend."""
    index_path = f"{_frontend_dir}/index.html"
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>FinceptEngine</h1><p>Frontend not built yet.</p>",
            status_code=200,
        )


# --------------------------------------------------------------------------- #
# REST: system status                                                         #
# --------------------------------------------------------------------------- #
@app.get("/api/system/status")
async def system_status() -> dict[str, Any]:
    """Engine status, connected feeds, strategy counts, uptime, activity."""
    snap = live.snapshot()
    activity: list[dict[str, Any]] = []
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            rows = conn.execute(
                """
                SELECT timestamp_utc, component, event_type, summary, details_json
                FROM system_activity_log
                ORDER BY id DESC
                LIMIT 50
                """
            ).fetchall()
            for r in rows:
                activity.append({
                    "timestamp_utc": r["timestamp_utc"],
                    "component": r["component"],
                    "event_type": r["event_type"],
                    "summary": r["summary"],
                    "details": json.loads(r["details_json"]) if r["details_json"] else {},
                })
        finally:
            conn.close()
    except Exception:
        pass

    # Counts from the database.
    total_strategies = 0
    approved_count = 0
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            total_strategies = conn.execute(
                "SELECT COUNT(DISTINCT strategy_id) FROM trades_memory"
            ).fetchone()[0]
            approved_count = conn.execute(
                "SELECT COUNT(*) FROM strategy_registry WHERE status IN "
                "('APPROVED_PAPER','CANDIDATE_APPROVED','APPROVED')"
            ).fetchone()[0]
        finally:
            conn.close()
    except Exception:
        pass

    return {
        "status": snap["status"] or "RUNNING",
        "connected_feeds": snap["connected_feeds"],
        "total_strategies_tested": total_strategies or snap["total_strategies_tested"],
        "approved_count": approved_count or snap["approved_count"],
        "uptime_s": round(snap["uptime_s"], 1),
        "last_candle": snap["last_candle"],
        "positions": snap["positions"],
        "pending_manual_ticket": snap["pending_manual_ticket"],
        "recent_activity": activity,
    }


# --------------------------------------------------------------------------- #
# REST: market snapshot (OHLCV + indicator overlays)                          #
# --------------------------------------------------------------------------- #
@app.get("/api/market/snapshot")
async def market_snapshot(
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("1m"),
    limit: int = Query(500, ge=50, le=2000),
) -> dict[str, Any]:
    """Return historical OHLCV plus computed indicator overlays for the chart.

    Only data up to the most recent stored bar is returned (t <= T). No future
    data is ever included.
    """
    market_type = "CRYPTO_SPOT" if symbol in CRYPTO_TRADEABLE_PAIRS else "NSE_EQUITY"

    q, params = _ohlcv_query(symbol, timeframe, limit, market_type)
    rows: list[dict[str, Any]] = []
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            cur = conn.execute(q, params)
            rows = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        rows = []

    if not rows:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "market_type": market_type,
            "bars": [],
            "overlays": {},
            "count": 0,
            "note": "no historical bars cached — run the data feeder first",
        }

    # Reverse to chronological order for indicator computation.
    rows = list(reversed(rows))
    df = pd.DataFrame(rows)

    # Compute overlays on cached history only (zero look-ahead).
    overlays: dict[str, Any] = {}
    try:
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        overlays["ema_20"] = _ema(close, 20).round(4).tolist()
        overlays["ema_50"] = _ema(close, 50).round(4).tolist()
        overlays["rsi_14"] = _rsi(close, 14).round(2).tolist()
        overlays["atr_14"] = _atr(high, low, close, 14).round(4).tolist()
        overlays["hma_20"] = _hma(close, 20).round(4).tolist()
        upper, middle, lower = _donchian(high, low, 20)
        overlays["donchian_upper_20"] = upper.round(4).tolist()
        overlays["donchian_lower_20"] = lower.round(4).tolist()
    except Exception as exc:
        overlays = {"error": str(exc)}

    # Reverse back to descending (newest first) for UI consumption.
    bars_out: list[dict[str, Any]] = []
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        bars_out.append({
            "t": r["open_time_utc"],
            "o": float(r["open"]),
            "h": float(r["high"]),
            "l": float(r["low"]),
            "c": float(r["close"]),
            "v": float(r["volume"] or 0.0),
        })

    # Mirror overlays so index alignment matches descending bars_out.
    for key, vals in list(overlays.items()):
        if isinstance(vals, list):
            overlays[key] = list(reversed(vals))

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "market_type": market_type,
        "bars": bars_out,
        "overlays": _sanitize_json(overlays),
        "count": len(bars_out),
    }


# --------------------------------------------------------------------------- #
# REST: trades memory (paginated)                                             #
# --------------------------------------------------------------------------- #
@app.get("/api/trades/memory")
async def trades_memory(
    strategy_id: str | None = Query(None),
    execution_mode: str | None = Query(None),
    status: str | None = Query(None),
    symbol: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Paginated trade logs from trades_memory with MAE/MFE, fees, regime."""
    conditions: list[str] = []
    params: list[Any] = []
    if strategy_id:
        conditions.append("strategy_id = ?"); params.append(strategy_id)
    if execution_mode:
        conditions.append("execution_mode = ?"); params.append(execution_mode)
    if status:
        conditions.append("status = ?"); params.append(status)
    if symbol:
        conditions.append("symbol = ?"); params.append(symbol)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    q = f"""
        SELECT trade_id, strategy_id, execution_mode, symbol, timeframe, direction,
               status, entry_time_utc, exit_time_utc, entry_price, exit_price,
               stop_loss, target_1_price, target_2_price, position_size,
               slippage_cost, commission_cost, gross_pnl, net_pnl, r_multiple,
               mae_pct, mae_r, mfe_pct, mfe_r, exit_reason,
               regime_snapshot_json, active_signals_json, notes
        FROM trades_memory {where}
        ORDER BY entry_time_utc DESC, trade_id DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    trades: list[dict[str, Any]] = []
    total = 0
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            total = conn.execute(
                f"SELECT COUNT(*) FROM trades_memory {where}", params[:-2]
            ).fetchone()[0]
            rows = conn.execute(q, params).fetchall()
            for r in rows:
                trades.append(_row_to_dict(r))
        finally:
            conn.close()
    except Exception:
        pass

    return {
        "trades": _sanitize_json(trades),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# --------------------------------------------------------------------------- #
# REST: manual trade (1-click order ticket)                                   #
# --------------------------------------------------------------------------- #
class ManualTradeIn:
    def __init__(self, *, strategy_id: str, symbol: str, timeframe: str,
                 direction: str, entry_price: float, stop_loss: float,
                 target_1_price: float, target_2_price: float | None,
                 position_size: float, regime_snapshot: dict[str, Any] | None,
                 active_signals: list[str] | None, notes: str | None) -> None:
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.target_1_price = target_1_price
        self.target_2_price = target_2_price
        self.position_size = position_size
        self.regime_snapshot = regime_snapshot or {}
        self.active_signals = active_signals or []
        self.notes = notes


@app.post("/api/trades/manual")
async def manual_trade(payload: dict[str, Any]) -> dict[str, Any]:
    """Log a human-executed trade from the 1-Click Manual Order Ticket."""
    try:
        trade = ManualTradeIn(
            strategy_id=str(payload.get("strategy_id", "MANUAL")),
            symbol=str(payload.get("symbol", "BTCUSDT")),
            timeframe=str(payload.get("timeframe", "1m")),
            direction=str(payload.get("direction", "LONG")).upper(),
            entry_price=float(payload.get("entry_price", 0.0)),
            stop_loss=float(payload.get("stop_loss", 0.0)),
            target_1_price=float(payload.get("target_1_price", 0.0)),
            target_2_price=payload.get("target_2_price"),
            position_size=float(payload.get("position_size", 0.0)),
            regime_snapshot=payload.get("regime_snapshot") or {},
            active_signals=payload.get("active_signals") or [],
            notes=payload.get("notes"),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid payload: {exc}")

    if trade.entry_price <= 0 or trade.position_size <= 0:
        raise HTTPException(status_code=400, detail="entry_price and position_size must be > 0")

    logger = TradeLogger(db_path=DB_PATH)
    trade_id = logger.open_trade(
        strategy_id=trade.strategy_id,
        execution_mode="MANUAL_LIVE",
        symbol=trade.symbol,
        timeframe=trade.timeframe,
        direction=trade.direction,
        entry_time_utc=iso_now_utc(),
        entry_price=trade.entry_price,
        stop_loss=trade.stop_loss,
        target_1_price=trade.target_1_price,
        target_2_price=trade.target_2_price,
        position_size=trade.position_size,
        regime_snapshot=trade.regime_snapshot,
        active_signals=trade.active_signals,
        notes=trade.notes,
    )

    live.set_manual_ticket({
        "trade_id": trade_id,
        "strategy_id": trade.strategy_id,
        "symbol": trade.symbol,
        "direction": trade.direction,
        "entry_price": trade.entry_price,
        "status": "OPEN",
        "created_at_utc": iso_now_utc(),
    })
    live.add_activity(
        "STRATEGY_ENGINE", "MANUAL_TRADE_LOGGED",
        f"{trade.strategy_id} {trade.direction} {trade.symbol} @ {trade.entry_price}",
        {"trade_id": trade_id, "direction": trade.direction,
         "entry_price": trade.entry_price},
    )
    # Broadcast the new ticket to all WS clients.
    try:
        import asyncio
        asyncio.create_task(live.broadcast({
            "type": "manual_ticket",
            "ticket": live.pending_manual_ticket,
        }))
    except Exception:
        pass

    return {
        "ok": True,
        "trade_id": trade_id,
        "status": "OPEN",
        "message": "Manual trade logged (human executes broker order manually).",
    }


# --------------------------------------------------------------------------- #
# REST: evaluation                                                            #
# --------------------------------------------------------------------------- #
@app.get("/api/evaluation/{strategy_id}")
async def evaluation(strategy_id: str) -> dict[str, Any]:
    """Run EvaluationEngine on a strategy: Performance, Risk, Regime, Weaknesses."""
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            rows = conn.execute(
                """
                SELECT trade_id, strategy_id, execution_mode, symbol, timeframe,
                       direction, status, entry_time_utc, exit_time_utc,
                       entry_price, exit_price, stop_loss, target_1_price,
                       target_2_price, position_size, slippage_cost,
                       commission_cost, gross_pnl, net_pnl, r_multiple,
                       mae_pct, mae_r, mfe_pct, mfe_r, exit_reason,
                       regime_snapshot_json, active_signals_json, notes
                FROM trades_memory
                WHERE strategy_id = ? AND status = 'CLOSED'
                ORDER BY entry_time_utc ASC
                """,
                (strategy_id,),
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        rows = []

    trades = [_row_to_dict(r) for r in rows]

    perf = compute_performance(trades)
    risk = compute_risk(trades, []) if trades else {}
    regime = compute_regime_breakdown(trades) if trades else {}
    weaknesses = detect_weaknesses(trades) if trades else []

    return {
        "strategy_id": strategy_id,
        "execution_mode": "BACKTEST/PAPER_LIVE/MANUAL_LIVE",
        "total_trades": len(trades),
        "overall_metrics": perf,
        "risk_metrics": _sanitize_json(risk),
        "regime_breakdown": _sanitize_json(regime),
        "weaknesses_detected": _sanitize_json(weaknesses),
    }


# --------------------------------------------------------------------------- #
# REST: research trigger                                                      #
# --------------------------------------------------------------------------- #
@app.post("/api/research/trigger")
async def research_trigger(payload: dict[str, Any]) -> dict[str, Any]:
    """Trigger the 4-Agent AI Research Loop for a target strategy.

    Body: { "symbol": "BTCUSDT", "timeframe": "1m" }  (both optional)
    Runs ResearchAgent -> HypothesisAgent -> CodingAgent -> ReviewAgent ->
    ValidationGatekeeper. V1 stays active unless all 4 gate tests pass.
    """
    symbol = str(payload.get("symbol", "BTCUSDT"))
    timeframe = str(payload.get("timeframe", "1m"))

    from trading_engine.agents.research_loop import ResearchLoop

    # Gather V1 closed trades + feature history for the loop.
    trades: list[dict[str, Any]] = []
    df_features = None
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            rows = conn.execute(
                """
                SELECT * FROM trades_memory
                WHERE strategy_id = 'EMA_BREAKOUT_V1' AND status = 'CLOSED'
                ORDER BY entry_time_utc ASC
                """,
            ).fetchall()
            trades = [_row_to_dict(r) for r in rows]
        finally:
            conn.close()
    except Exception:
        pass

    try:
        fs = FeatureStore(db_path=DB_PATH)
        df_features = fs.load_features(symbol, timeframe)
    except Exception:
        df_features = None

    loop = ResearchLoop()
    result = loop.run(
        trades=trades,
        df_features=df_features,
        symbol=symbol,
        timeframe=timeframe,
    )

    live.add_activity(
        "RESEARCH_AGENT", "RESEARCH_TRIGGERED",
        f"Research loop for {symbol} {timeframe}: {result.get('final_status')}",
        {
            "symbol": symbol, "timeframe": timeframe,
            "promoted": result.get("promoted"),
            "final_status": result.get("final_status"),
            "candidate": result.get("candidate_strategy_id"),
        },
    )

    return {
        "ok": True,
        "symbol": symbol,
        "timeframe": timeframe,
        "promoted": result.get("promoted", False),
        "final_status": result.get("final_status"),
        "candidate_strategy_id": result.get("candidate_strategy_id"),
        "baseline_strategy_id": result.get("baseline_strategy_id"),
        "v1_stays_active": result.get("v1_stays_active", True),
        "rejection_reason": result.get("rejection_reason"),
        "gate_summary": result.get("gate_summary"),
        "look_ahead_audit": result.get("look_ahead_audit"),
    }


# --------------------------------------------------------------------------- #
# REST: validation reports                                                    #
# --------------------------------------------------------------------------- #
@app.get("/api/validation/reports")
async def validation_reports() -> dict[str, Any]:
    """V1 vs V2 scorecard: OOS, Walk-Forward, Parameter Heatmap, Cost Stress."""
    reports: list[dict[str, Any]] = []
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            rows = conn.execute(
                """
                SELECT report_id, candidate_strategy_id, baseline_strategy_id,
                       symbol, timeframe, in_sample_metrics_json,
                       out_of_sample_metrics_json, walk_forward_summary_json,
                       parameter_heatmap_json, cost_stress_metrics_json,
                       oos_passed, walk_forward_passed, param_stability_passed,
                       cost_stress_passed, final_status, rejection_reason,
                       evaluated_at_utc
                FROM validation_reports
                ORDER BY evaluated_at_utc DESC
                LIMIT 50
                """
            ).fetchall()
            for r in rows:
                reports.append({
                    "report_id": r["report_id"],
                    "candidate_strategy_id": r["candidate_strategy_id"],
                    "baseline_strategy_id": r["baseline_strategy_id"],
                    "symbol": r["symbol"],
                    "timeframe": r["timeframe"],
                    "in_sample_metrics": json.loads(r["in_sample_metrics_json"]),
                    "out_of_sample_metrics": json.loads(r["out_of_sample_metrics_json"]),
                    "walk_forward_summary": json.loads(r["walk_forward_summary_json"]),
                    "parameter_heatmap": json.loads(r["parameter_heatmap_json"]),
                    "cost_stress_metrics": json.loads(r["cost_stress_metrics_json"]),
                    "oos_passed": bool(r["oos_passed"]),
                    "walk_forward_passed": bool(r["walk_forward_passed"]),
                    "param_stability_passed": bool(r["param_stability_passed"]),
                    "cost_stress_passed": bool(r["cost_stress_passed"]),
                    "final_status": r["final_status"],
                    "rejection_reason": r["rejection_reason"],
                    "evaluated_at_utc": r["evaluated_at_utc"],
                })
        finally:
            conn.close()
    except Exception:
        pass

    return {
        "reports": _sanitize_json(reports),
        "count": len(reports),
    }


# --------------------------------------------------------------------------- #
# WebSocket: /ws/live                                                         #
# --------------------------------------------------------------------------- #
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    """Stream live candles, paper positions, status badges, and order tickets."""
    await ws.accept()
    live.register(ws)
    try:
        # Send initial snapshot immediately.
        await ws.send_text(json.dumps({
            "type": "snapshot",
            "payload": live.snapshot(),
        }, default=str))

        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except Exception:
                continue
            mtype = msg.get("type")

            if mtype == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif mtype == "subscribe":
                feeds = msg.get("feeds", [])
                with live._lock:
                    live.connected_feeds = list(feeds)
                await ws.send_text(json.dumps({
                    "type": "subscribed",
                    "feeds": feeds,
                }))
            elif mtype == "candle":
                live.set_candle(msg.get("payload", {}))
                live.add_activity(
                    "DATA_FEED", "CANDLE_RECEIVED",
                    f"{msg.get('payload',{}).get('symbol','?')} "
                    f"{msg.get('payload',{}).get('timeframe','?')} "
                    f"@ {msg.get('payload',{}).get('c','?')}",
                    msg.get("payload", {}),
                )
                # Echo candle back to all clients (including sender) as a live update.
                await live.broadcast({
                    "type": "candle",
                    "payload": live.last_candle,
                })
            elif mtype == "positions":
                live.set_positions(msg.get("payload", {}))
                await live.broadcast({
                    "type": "positions",
                    "payload": live.positions,
                })
            elif mtype == "status":
                live.status = str(msg.get("payload", {}).get("status", live.status))
                await live.broadcast({
                    "type": "status",
                    "payload": {"status": live.status},
                })
            else:
                # Unknown message: echo back as-is for debugging.
                await ws.send_text(json.dumps({
                    "type": "ack",
                    "received": msg,
                }, default=str))
    except WebSocketDisconnect:
        pass
    finally:
        live.unregister(ws)
