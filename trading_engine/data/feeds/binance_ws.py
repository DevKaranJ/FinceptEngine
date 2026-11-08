"""data/feeds/binance_ws.py — Live 24/7 Crypto Spot WebSocket + REST backfill.

Responsibilities (PRD FR-01 / master_architecture Section 2 / Phase 1):
  • Stream live 1m kline candles + aggTrade ticks for top pairs (BTCUSDT, ETHUSDT, SOLUSDT)
    over Binance public Spot WebSocket (no API key required).
  • REST backfill historical OHLCV bars via /api/v3/klines using stdlib urllib.
  • Normalize every message into a canonical bar dict and write to SQLite (memory/db.py).

Zero look-ahead: bars are persisted only after their close time (kline x = True) is
confirmed, so no future data is ever written before t <= T.

Declared dependencies: `websockets` (WS) + stdlib `urllib.request` (REST).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

import websockets

from ...config import (
    BINANCE_KLINE_INTERVALS,
    BINANCE_REST_BASE_URL,
    BINANCE_WS_BASE_URL,
    CRYPTO_TRADEABLE_PAIRS,
)
from ...memory.db import get_connection, initialize_database, log_activity

logger = logging.getLogger("fincept.data.binance_ws")

# Map Binance kline interval -> internal timeframe label
KLINE_TO_TIMEFRAME: dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "1d": "1d",
}


def _kline_topic(symbol: str, interval: str) -> str:
    """A live kline stream topic, e.g. 'btcusdt@kline_1m'."""
    return f"{symbol.lower()}@kline_{interval}"


def _aggtrade_topic(symbol: str) -> str:
    return f"{symbol.lower()}@aggTrade"


def _normalize_bar(symbol: str, interval: str, k: dict[str, Any]) -> dict[str, Any]:
    """Convert a Binance kline payload into a canonical ohlcv_bars row dict.

    Binance kline event fields (k):
      t = kline start time, T = kline close time, s = symbol, i = interval,
      f = first trade ID, L = last trade ID, o = open, h = high, l = low,
      c = close, v = volume, n = number of trades, x = is final,
      q = quote asset volume, V = taker buy base volume, Q = taker buy quote volume.
    """
    return {
        "symbol": k["s"],
        "market_type": "CRYPTO_SPOT",
        "timeframe": KLINE_TO_TIMEFRAME.get(interval, interval),
        "open_time_utc": datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
        "quote_volume": float(k["q"]),
        "taker_buy_vol": float(k["V"]),
        "trade_count": int(k["n"]),
    }


class BinanceFeed:
    """Binance Spot live WebSocket feeder with optional REST backfill."""

    def __init__(
        self,
        symbols: tuple[str, ...] = CRYPTO_TRADEABLE_PAIRS,
        intervals: tuple[str, ...] = ("1m",),
        db_path: str | None = None,
    ) -> None:
        self.symbols = symbols
        self.intervals = intervals
        self.db_path = db_path
        self._ws: Any = None
        self._running = False
        self._on_bar_callbacks: list[Any] = []

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        initialize_database()
        topics = []
        for symbol in self.symbols:
            for interval in self.intervals:
                topics.append(_kline_topic(symbol, interval))
            topics.append(_aggtrade_topic(symbol))
        stream = "/".join(topics)
        ws_url = f"{BINANCE_WS_BASE_URL}/{stream}"
        logger.info("Connecting Binance WS: %s", ws_url)
        self._ws = await websockets.connect(ws_url, ping_interval=30, ping_timeout=10)
        self._running = True
        log_activity("DATA_FEED", "WS_CONNECTED", f"Subscribed to {len(topics)} topics")

    async def stop(self) -> None:
        self._running = False
        if self._ws is not None:
            await self._ws.close()

    # ------------------------------------------------------------------ #
    # REST backfill (stdlib urllib — no extra dep beyond declared stack)
    # ------------------------------------------------------------------ #
    def backfill_historical(
        self,
        symbol: str,
        interval: str,
        start_ms: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch historical klines via REST /api/v3/klines (oldest first). Synchronous."""
        params = [("symbol", symbol.upper()), ("interval", interval), ("limit", str(limit))]
        if start_ms is not None:
            params.append(("startTime", str(start_ms)))
        query = "&".join(f"{k}={v}" for k, v in params)
        url = f"{BINANCE_REST_BASE_URL}/klines?{query}"
        logger.info("REST backfill: %s", url)
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        bars = [self._rest_kline_to_bar(symbol, interval, row) for row in raw]
        self._persist_bars(bars)
        log_activity(
            "DATA_FEED",
            "REST_BACKFILL",
            f"{symbol} {interval}: {len(bars)} bars",
            {"symbol": symbol, "interval": interval, "count": len(bars)},
        )
        return bars

    @staticmethod
    def _rest_kline_to_bar(symbol: str, interval: str, row: list[Any]) -> dict[str, Any]:
        """Convert a raw REST kline array into a canonical bar dict."""
        (
            open_time,
            open_,
            high,
            low,
            close,
            volume,
            close_time,
            quote_volume,
            trade_count,
            taker_buy_base,
            taker_buy_quote,
            _ignore,
        ) = row
        return {
            "symbol": symbol,
            "market_type": "CRYPTO_SPOT",
            "timeframe": KLINE_TO_TIMEFRAME.get(interval, interval),
            "open_time_utc": datetime.fromtimestamp(open_time / 1000, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": float(open_),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
            "quote_volume": float(quote_volume),
            "taker_buy_vol": float(taker_buy_base),
            "trade_count": int(trade_count),
        }

    # ------------------------------------------------------------------ #
    # Live WebSocket message loop
    # ------------------------------------------------------------------ #
    async def run_forever(self) -> None:
        """Read WebSocket messages until stopped. Finalized klines (x=True) are persisted."""
        if self._ws is None:
            await self.start()
        assert self._ws is not None
        async for msg in self._ws:
            if not self._running:
                break
            await self._on_message(json.loads(msg))

    async def _on_message(self, payload: str | bytes) -> None:
        data = json.loads(payload) if isinstance(payload, (bytes, bytearray)) else payload
        stream = data.get("stream", "")
        kline = data.get("data", {})
        if "@kline_" in stream:
            k = kline.get("k", {})
            if k.get("x") is True:  # kline finalized -> safe to persist (no look-ahead)
                bar = _normalize_bar(kline["s"], k["i"], k)
                self._persist_bar(bar)
                for cb in self._on_bar_callbacks:
                    try:
                        cb(bar)
                    except Exception:  # pragma: no cover - callback failures are non-fatal
                        logger.exception("Bar callback failed")
        elif "@aggTrade" in stream:
            # Tick stream; optionally persisted to trades_memory later (Phase 3).
            pass

    # ------------------------------------------------------------------ #
    # Persistence & callbacks
    # ------------------------------------------------------------------ #
    def _persist_bar(self, bar: dict[str, Any]) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO ohlcv_bars
                    (symbol, market_type, timeframe, open_time_utc, open, high, low,
                     close, volume, quote_volume, taker_buy_vol, trade_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bar["symbol"],
                    bar["market_type"],
                    bar["timeframe"],
                    bar["open_time_utc"],
                    bar["open"],
                    bar["high"],
                    bar["low"],
                    bar["close"],
                    bar["volume"],
                    bar["quote_volume"],
                    bar["taker_buy_vol"],
                    bar["trade_count"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _persist_bars(self, bars: list[dict[str, Any]]) -> None:
        if not bars:
            return
        conn = get_connection(self.db_path)
        try:
            conn.executemany(
                """
                INSERT OR REPLACE INTO ohlcv_bars
                    (symbol, market_type, timeframe, open_time_utc, open, high, low,
                     close, volume, quote_volume, taker_buy_vol, trade_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        b["symbol"], b["market_type"], b["timeframe"], b["open_time_utc"],
                        b["open"], b["high"], b["low"], b["close"], b["volume"],
                        b["quote_volume"], b["taker_buy_vol"], b["trade_count"],
                    )
                    for b in bars
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def on_bar(self, callback: Any) -> None:
        """Register a callback invoked for every finalized live bar."""
        self._on_bar_callbacks.append(callback)


__all__ = [
    "BinanceFeed",
    "_normalize_bar",
    "KLINE_TO_TIMEFRAME",
]
