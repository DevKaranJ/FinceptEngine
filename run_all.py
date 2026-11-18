"""run_all.py — Unified launcher for FinceptEngine (Phase 6).

Starts everything in ONE process:

  1. FastAPI backend + frontend (uvicorn)        -> http://127.0.0.1:8765
  2. Live data feeder (synthetic candles)        -> writes ohlcv_bars + pushes /ws/live
  3. Research scheduler                          -> triggers ResearchLoop -> ValidationGatekeeper
  4. Background workers (all daemon threads)

Run:
    .venv/bin/python run_all.py

Press Ctrl+C to shut everything down cleanly.
"""

from __future__ import annotations

import math
import random
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import uvicorn

# --------------------------------------------------------------------------- #
# App import (creates the FastAPI object, does NOT start the server)          #
# --------------------------------------------------------------------------- #
from trading_engine.backend.server import app, live  # noqa: E402
from trading_engine.config import DB_PATH, CRYPTO_TRADEABLE_PAIRS  # noqa: E402
from trading_engine.memory.db import (  # noqa: E402
    get_connection,
    initialize_database,
    log_activity,
)
from trading_engine.data.clock import iso_now_utc  # noqa: E402
from trading_engine.data.feature_store import FeatureStore  # noqa: E402
from trading_engine.agents.research_loop import ResearchLoop  # noqa: E402


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #
SYMBOL = "BTCUSDT"
TIMEFRAME = "1m"
MARKET_TYPE = "CRYPTO_SPOT"
FEED_INTERVAL_SEC = 5.0          # new candle every 5s
RESEARCH_INTERVAL_SEC = 120.0    # run research loop every 2min
BASE_PRICE = 67000.0             # starting synthetic BTC price

SHUTDOWN = threading.Event()


# --------------------------------------------------------------------------- #
# Database helpers                                                            #
# --------------------------------------------------------------------------- #
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _insert_bar(symbol: str, ts: datetime, open_p: float, high: float,
                low: float, close: float, volume: float) -> None:
    """Insert a single OHLCV bar into SQLite (WAL). One connection per call."""
    quote_volume = close * volume
    taker_buy_vol = volume * random.uniform(0.45, 0.55)
    trade_count = random.randint(20, 200)
    try:
        conn = get_connection(db_path=DB_PATH)
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO ohlcv_bars
                    (symbol, market_type, timeframe, open_time_utc,
                     open, high, low, close, volume, quote_volume,
                     taker_buy_vol, trade_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol, MARKET_TYPE, TIMEFRAME,
                    ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    open_p, high, low, close, volume,
                    quote_volume, taker_buy_vol, trade_count,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - feeder resilience
        print(f"[feeder] DB insert error: {exc}")


# --------------------------------------------------------------------------- #
# Live data feeder                                                            #
# --------------------------------------------------------------------------- #
class LiveDataFeeder(threading.Thread):
    """Generates synthetic BTCUSDT 1m candles and pushes them to WS clients."""

    def __init__(self) -> None:
        super().__init__(daemon=True, name="live-data-feeder")
        self.price = BASE_PRICE
        self.last_ts = _now_utc().replace(second=0, microsecond=0)

    def run(self) -> None:
        print("[feeder] started — emitting synthetic candles every "
              f"{FEED_INTERVAL_SEC}s")
        while not SHUTDOWN.is_set():
            try:
                # Advance to next minute boundary
                self.last_ts += timedelta(minutes=1)

                # Random-walk price (zero look-ahead: only past known)
                drift = random.uniform(-0.002, 0.002)
                self.price *= (1.0 + drift)

                open_p = self.price
                close_p = open_p * (1 + random.uniform(-0.001, 0.001))
                high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.0008))
                low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.0008))
                volume = random.uniform(5, 50)

                bar = {
                    "t": self.last_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "o": round(open_p, 2),
                    "h": round(high_p, 2),
                    "l": round(low_p, 2),
                    "c": round(close_p, 2),
                    "v": round(volume, 4),
                }

                # Persist to SQLite
                _insert_bar(
                    SYMBOL,
                    self.last_ts,
                    bar["o"], bar["h"], bar["l"], bar["c"], bar["v"],
                )

                # Push to WebSocket clients
                try:
                    import asyncio
                    asyncio.run(
                        live.broadcast({"type": "candle", "payload": bar})
                    )
                    live.set_candle(bar)
                    live.add_activity(
                        "DATA_FEED", "CANDLE_EMITTED",
                        f"{SYMBOL} {TIMEFRAME} @ {bar['c']}",
                        {"symbol": SYMBOL, "timeframe": TIMEFRAME, **bar},
                    )
                except Exception as exc:  # pragma: no cover
                    print(f"[feeder] WS broadcast error: {exc}")

                print(f"[feeder] {bar['t']} O={bar['o']} H={bar['h']} "
                      f"L={bar['l']} C={bar['c']} V={bar['v']}")

            except Exception as exc:  # pragma: no cover
                print(f"[feeder] loop error: {exc}")

            SHUTDOWN.wait(FEED_INTERVAL_SEC)

        print("[feeder] stopped")


# --------------------------------------------------------------------------- #
# Research scheduler                                                          #
# --------------------------------------------------------------------------- #
class ResearchScheduler(threading.Thread):
    """Periodically triggers the 4-role research loop (V2 gating)."""

    def __init__(self) -> None:
        super().__init__(daemon=True, name="research-scheduler")
        self.next_run = time.time() + 30.0  # first run after 30s

    def run(self) -> None:
        print(f"[research] scheduler started — loop every {RESEARCH_INTERVAL_SEC}s")
        loop = ResearchLoop()
        while not SHUTDOWN.is_set():
            try:
                now = time.time()
                if now >= self.next_run:
                    self.next_run = now + RESEARCH_INTERVAL_SEC
                    self._run_once(loop)
            except Exception as exc:  # pragma: no cover
                print(f"[research] scheduler error: {exc}")
            SHUTDOWN.wait(5.0)
        print("[research] scheduler stopped")

    def _run_once(self, loop: ResearchLoop) -> None:
        print("[research] running V2 research loop → validation gate…")
        try:
            # Pull recent V1 closed trades + feature history
            trades = []
            df_features = None
            try:
                conn = get_connection(db_path=DB_PATH)
                try:
                    rows = conn.execute(
                        """
                        SELECT * FROM trades_memory
                        WHERE strategy_id = 'EMA_BREAKOUT_V1' AND status = 'CLOSED'
                        ORDER BY entry_time_utc ASC
                        LIMIT 500
                        """,
                    ).fetchall()
                    trades = [dict(r) for r in rows]
                finally:
                    conn.close()
            except Exception as exc:  # pragma: no cover
                print(f"[research] could not load trades: {exc}")

            try:
                fs = FeatureStore(db_path=DB_PATH)
                df_features = fs.load_features(SYMBOL, TIMEFRAME)
            except Exception:
                df_features = None

            if df_features is None or len(df_features) < 100:
                from trading_engine.tests.test_phase5_research_agents import _build_feature_df
                df_features = _build_feature_df(n=500, seed=int(time.time()) % 1000)

            result = loop.run(
                trades=trades,
                df_features=df_features,
                symbol=SYMBOL,
                timeframe=TIMEFRAME,
            )

            promoted = bool(result.get("promoted"))
            status = result.get("final_status", "UNKNOWN")
            candidate = result.get("candidate_strategy_id", "—")
            print(
                f"[research] complete: status={status} promoted={promoted} "
                f"candidate={candidate}"
            )
            live.add_activity(
                "RESEARCH_AGENT", "RESEARCH_LOOP_RUN",
                f"V2 gate: {status} {'PROMOTED' if promoted else 'V1 stays active'}",
                {
                    "symbol": SYMBOL,
                    "timeframe": TIMEFRAME,
                    "promoted": promoted,
                    "final_status": status,
                    "candidate": candidate,
                },
            )
        except Exception as exc:  # pragma: no cover
            print(f"[research] loop execution error: {exc}")


# --------------------------------------------------------------------------- #
# Uvicorn server runner (background thread)                                   #
# --------------------------------------------------------------------------- #
class UvicornRunner(threading.Thread):
    """Runs uvicorn in a background thread so other workers can co-exist."""

    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True, name="uvicorn")
        self.host = host
        self.port = port
        self.server = None

    def run(self) -> None:
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
        )
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main() -> None:
    # Ensure schema exists (idempotent)
    initialize_database(db_path=DB_PATH)

    import argparse
    import socket

    parser = argparse.ArgumentParser(description="FinceptEngine unified launcher")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0 for LAN access)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args, _ = parser.parse_known_args()

    host = args.host
    port = args.port

    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # Start background workers
    feeder = LiveDataFeeder()
    scheduler = ResearchScheduler()
    web = UvicornRunner(host, port)

    feeder.start()
    scheduler.start()
    web.start()

    # Wait for the web server to report it's up
    print("=" * 60)
    print(f" FinceptEngine — all services starting")
    print("=" * 60)
    print(f"  Local access       : http://127.0.0.1:{port}/")
    if local_ip != "127.0.0.1":
        print(f"  Network (LAN) access: http://{local_ip}:{port}/")
    print(f"  WebSocket hub      : ws://{local_ip}:{port}/ws/live")
    print(f"  Live feeder        : synthetic {SYMBOL} {TIMEFRAME} candles")
    print(f"  Research scheduler : every {RESEARCH_INTERVAL_SEC:.0f}s")
    print("=" * 60)
    print("  Press Ctrl+C to stop all services")
    print("=" * 60)

    def handle_signal(signum, frame):  # pragma: no cover - runtime only
        print("\n[shutdown] signal received — stopping services…")
        SHUTDOWN.set()
        web.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Keep main thread alive until shutdown
    try:
        while not SHUTDOWN.is_set():
            SHUTDOWN.wait(1.0)
    except KeyboardInterrupt:  # pragma: no cover
        SHUTDOWN.set()
        web.stop()

    # Give threads a moment to exit
    feeder.join(timeout=3.0)
    scheduler.join(timeout=3.0)
    web.join(timeout=5.0)
    print("[shutdown] all services stopped. Goodbye.")


if __name__ == "__main__":
    main()
