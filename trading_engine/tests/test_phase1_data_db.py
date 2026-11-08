"""tests/test_phase1_data_db.py — Deterministic Phase 1 verification suite.

Covers (PRD Phase 1 stop gate):
  • SQLite WAL schema creation for all 5 tables (memory/db.py)
  • Market session clock logic (data/clock.py): crypto 24/7, NSE IST window, bar alignment
  • Binance kline payload normalization (data/feeds/binance_ws.py) — offline, no network

Run: pytest tests/test_phase1_data_db.py -v   (from repo root)
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from trading_engine.config import (
    CRYPTO_TRADEABLE_PAIRS,
    DB_PATH,
    NSE_SESSION_IST_END,
    NSE_SESSION_IST_START,
    NSE_TRADING_DAYS,
    ZERO_LOOK_AHEAD,
)
from trading_engine.data.clock import (
    MarketSession,
    iso_now_utc,
    iso_utc,
    now_utc,
)
from trading_engine.data.feeds.binance_ws import KLINE_TO_TIMEFRAME, _normalize_bar
from trading_engine.memory.db import (
    CREATE_INDEXES,
    TABLE_SCHEMA,
    get_connection,
    initialize_database,
    log_activity,
    now_utc_iso,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def tmp_db_path():
    """A temp SQLite path so tests never touch trading_engine.db."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass


@pytest.fixture()
def session():
    return MarketSession()


# --------------------------------------------------------------------------- #
# config.py
# --------------------------------------------------------------------------- #
def test_config_constants():
    assert ZERO_LOOK_AHEAD is True
    assert CRYPTO_TRADEABLE_PAIRS == ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    assert NSE_TRADING_DAYS == (0, 1, 2, 3, 4)
    assert NSE_SESSION_IST_START.hour == 9 and NSE_SESSION_IST_START.minute == 15
    assert NSE_SESSION_IST_END.hour == 15 and NSE_SESSION_IST_END.minute == 30


# --------------------------------------------------------------------------- #
# memory/db.py — SQLite WAL schema
# --------------------------------------------------------------------------- #
def test_initialize_database_creates_all_tables(tmp_db_path):
    initialize_database(db_path=tmp_db_path)
    conn = get_connection(db_path=tmp_db_path)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    expected = set(TABLE_SCHEMA.keys())
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_wal_mode_enabled(tmp_db_path):
    initialize_database(db_path=tmp_db_path)
    conn = get_connection(db_path=tmp_db_path)
    try:
        cur = conn.execute("PRAGMA journal_mode;")
        mode = cur.fetchone()[0]
    finally:
        conn.close()
    assert mode.lower() == "wal"


def test_ohlcv_bars_primary_key_enforced(tmp_db_path):
    initialize_database(db_path=tmp_db_path)
    conn = get_connection(db_path=tmp_db_path)
    try:
        conn.execute(
            """
            INSERT INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low, close,
                 volume, quote_volume, taker_buy_vol, trade_count)
            VALUES ('BTCUSDT','CRYPTO_SPOT','1m','2026-11-08T09:00:00Z',100,101,99,100.5,10,1000,5,3)
            """
        )
        conn.commit()
        # Duplicate PK should raise IntegrityError on INSERT OR FAIL (we use plain insert here).
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO ohlcv_bars
                    (symbol, market_type, timeframe, open_time_utc, open, high, low, close,
                     volume, quote_volume, taker_buy_vol, trade_count)
                VALUES ('BTCUSDT','CRYPTO_SPOT','1m','2026-11-08T09:00:00Z',100,101,99,100.5,10,1000,5,3)
                """
            )
            conn.commit()
    finally:
        conn.close()


def test_trades_memory_roundtrip(tmp_db_path):
    initialize_database(db_path=tmp_db_path)
    conn = get_connection(db_path=tmp_db_path)
    try:
        conn.execute(
            """
            INSERT INTO trades_memory
                (trade_id, strategy_id, execution_mode, symbol, timeframe, direction, status,
                 entry_time_utc, entry_price, stop_loss, target_1_price, position_size,
                 regime_snapshot_json, active_signals_json)
            VALUES ('TRD_001','EMA_BREAKOUT_V1','PAPER_LIVE','BTCUSDT','1m','LONG','OPEN',
                    '2026-11-08T09:00:00Z',68420.50,68180.00,68910.00,0.146,
                    '{"volatility_regime":"LOW_VOLATILITY"}','["EMA_CROSS"]')
            """
        )
        conn.commit()
        cur = conn.execute("SELECT trade_id, strategy_id FROM trades_memory WHERE trade_id='TRD_001'")
        row = cur.fetchone()
        assert row is not None
        assert row["trade_id"] == "TRD_001"
        assert row["strategy_id"] == "EMA_BREAKOUT_V1"
    finally:
        conn.close()


def test_strategy_registry_and_validation_reports_exist(tmp_db_path):
    initialize_database(db_path=tmp_db_path)
    conn = get_connection(db_path=tmp_db_path)
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('strategy_registry','validation_reports','system_activity_log')"
        )
        names = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
    assert names == {"strategy_registry", "validation_reports", "system_activity_log"}


def test_indexes_created(tmp_db_path):
    initialize_database(db_path=tmp_db_path)
    conn = get_connection(db_path=tmp_db_path)
    try:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
    expected = {idx.split("idx_")[1].split("_")[0] for idx in CREATE_INDEXES}  # rough check
    assert any("ohlcv" in i for i in indexes)
    assert any("trades" in i for i in indexes)


def test_log_activity_writes_row(tmp_db_path):
    initialize_database(db_path=tmp_db_path)
    log_activity("DATA_FEED", "WS_CONNECTED", "test event", {"k": "v"}, db_path=tmp_db_path)
    conn = get_connection(db_path=tmp_db_path)
    try:
        cur = conn.execute(
            "SELECT component, event_type, summary FROM system_activity_log WHERE summary='test event'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row["component"] == "DATA_FEED"
        assert row["event_type"] == "WS_CONNECTED"
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# data/clock.py
# --------------------------------------------------------------------------- #
def test_now_utc_is_aware_and_recent():
    ts = now_utc()
    assert ts.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - ts).total_seconds()) < 5


def test_iso_now_utc_format():
    s = iso_now_utc()
    assert s.endswith("Z")
    datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def test_iso_utc_formats_aware_datetime():
    ts = datetime(2026, 11, 8, 9, 15, tzinfo=timezone.utc)
    assert iso_utc(ts) == "2026-11-08T09:15:00Z"


def test_crypto_session_always_open(session):
    ts = datetime(2026, 11, 8, 3, 30, tzinfo=timezone.utc)  # odd hour
    assert session.is_crypto_session_open(ts) is True


def test_nse_session_open_weekday(session):
    # Monday 2026-11-09 10:00 IST = 2026-11-09 04:30 UTC
    ts = datetime(2026, 11, 9, 4, 30, tzinfo=timezone.utc)
    assert session.is_nse_session_open(ts) is True


def test_nse_session_closed_weekend(session):
    # Saturday 2026-11-07 10:00 IST
    ts = datetime(2026, 11, 7, 4, 30, tzinfo=timezone.utc)
    assert session.is_nse_session_open(ts) is False


def test_nse_session_closed_outside_hours(session):
    # Monday 2026-11-09 08:00 IST (before open) = 02:30 UTC
    ts = datetime(2026, 11, 9, 2, 30, tzinfo=timezone.utc)
    assert session.is_nse_session_open(ts) is False
    # Monday 2026-11-09 16:00 IST (after close) = 10:30 UTC
    ts = datetime(2026, 11, 9, 10, 30, tzinfo=timezone.utc)
    assert session.is_nse_session_open(ts) is False


def test_align_bar_open_utc_1m():
    ts = datetime(2026, 11, 8, 9, 7, 42, tzinfo=timezone.utc)
    aligned = MarketSession.align_bar_open_utc(ts, "1m")
    assert aligned == datetime(2026, 11, 8, 9, 7, tzinfo=timezone.utc)


def test_align_bar_open_utc_5m():
    ts = datetime(2026, 11, 8, 9, 7, 42, tzinfo=timezone.utc)
    aligned = MarketSession.align_bar_open_utc(ts, "5m")
    assert aligned == datetime(2026, 11, 8, 9, 5, tzinfo=timezone.utc)


def test_align_bar_open_utc_1h():
    ts = datetime(2026, 11, 8, 9, 42, tzinfo=timezone.utc)
    aligned = MarketSession.align_bar_open_utc(ts, "1h")
    assert aligned == datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)


def test_align_bar_open_utc_1d():
    ts = datetime(2026, 11, 8, 14, 30, tzinfo=timezone.utc)
    aligned = MarketSession.align_bar_open_utc(ts, "1d")
    assert aligned == datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc)


def test_crypto_session_reset_utc(session):
    ts = datetime(2026, 11, 8, 23, 30, tzinfo=timezone.utc)
    reset = session.crypto_session_reset_utc(ts)
    assert reset == datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# data/feeds/binance_ws.py — offline normalization
# --------------------------------------------------------------------------- #
def test_normalize_bar_shape():
    kline_event = {
        "s": "BTCUSDT",
        "k": {
            "t": 1731062400000,  # 2024-11-08 12:00:00 UTC
            "T": 1731062459999,
            "s": "BTCUSDT",
            "i": "1m",
            "f": 100,
            "L": 110,
            "o": "68000.00",
            "h": "68100.00",
            "l": "67900.00",
            "c": "68050.00",
            "v": "12.5",
            "n": 45,
            "x": True,
            "q": "850625.00",
            "V": "6.2",
            "Q": "425312.50",
        },
    }
    bar = _normalize_bar("BTCUSDT", "1m", kline_event["k"])
    assert bar["symbol"] == "BTCUSDT"
    assert bar["market_type"] == "CRYPTO_SPOT"
    assert bar["timeframe"] == "1m"
    assert bar["open"] == 68000.0
    assert bar["high"] == 68100.0
    assert bar["low"] == 67900.0
    assert bar["close"] == 68050.0
    assert bar["volume"] == 12.5
    assert bar["trade_count"] == 45
    assert bar["open_time_utc"].endswith("Z")


def test_kline_to_timeframe_mapping():
    assert KLINE_TO_TIMEFRAME["1m"] == "1m"
    assert KLINE_TO_TIMEFRAME["5m"] == "5m"
    assert KLINE_TO_TIMEFRAME["1h"] == "1h"
    assert KLINE_TO_TIMEFRAME["1d"] == "1d"
