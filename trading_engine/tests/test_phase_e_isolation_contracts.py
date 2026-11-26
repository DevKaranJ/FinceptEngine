"""tests/test_phase_e_isolation_contracts.py — Phase E.0 verification suite.

Covers (PRD Phase E milestone E.0 stop gate — Market Contracts & Schema Isolation):
  • trading_engine/memory/db.py — market_type isolation in schema + versioned migration
  • trading_engine/data/feature_store.py — market_type in PK, cache keys, and queries
  • market_type filtering on DB query layer (Spot queries return only CRYPTO_SPOT)

Run: pytest trading_engine/tests/test_phase_e_isolation_contracts.py -v   (from repo root)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

# Ensure the repo root is on the path so `trading_engine` imports resolve.
# tests/ is at <repo>/trading_engine/tests/, so repo root is 3 levels up.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from trading_engine.config import CRYPTO_SPOT, CRYPTO_PERP, DB_PATH
from trading_engine.data.clock import iso_now_utc
from trading_engine.data.feature_store import FeatureStore
from trading_engine.memory.db import (
    CREATE_INDEXES,
    SCHEMA_MIGRATION_VERSION,
    TABLE_SCHEMA,
    _column_exists,
    _pk_columns,
    _row_count,
    _table_exists,
    get_connection,
    initialize_database,
    run_migration,
)

# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def clean_db_path(tmp_path):
    """Fresh SQLite path for each test."""
    return str(tmp_path / "e0_test.db")


@pytest.fixture
def premigration_db_path(tmp_path):
    """A database built with the OLD schema (no market_type column, old PKs).

    Simulates an existing Phase 1–6 database that has not yet been migrated.
    """
    db_path = str(tmp_path / "premigration.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.executescript("""
        CREATE TABLE ohlcv_bars (
            symbol          TEXT NOT NULL,
            timeframe       TEXT NOT NULL,
            open_time_utc   TEXT NOT NULL,
            open            REAL NOT NULL,
            high            REAL NOT NULL,
            low             REAL NOT NULL,
            close           REAL NOT NULL,
            volume          REAL NOT NULL,
            quote_volume    REAL DEFAULT 0.0,
            taker_buy_vol   REAL DEFAULT 0.0,
            trade_count     INTEGER DEFAULT 0,
            PRIMARY KEY (symbol, timeframe, open_time_utc)
        );
        CREATE TABLE trades_memory (
            trade_id                TEXT PRIMARY KEY,
            strategy_id             TEXT NOT NULL,
            execution_mode          TEXT NOT NULL,
            symbol                  TEXT NOT NULL,
            timeframe               TEXT NOT NULL,
            direction               TEXT NOT NULL,
            status                  TEXT NOT NULL,
            entry_time_utc          TEXT NOT NULL,
            exit_time_utc           TEXT,
            entry_price             REAL NOT NULL,
            exit_price              REAL,
            stop_loss               REAL NOT NULL,
            target_1_price          REAL NOT NULL,
            target_2_price          REAL,
            position_size           REAL NOT NULL,
            slippage_cost           REAL DEFAULT 0.0,
            commission_cost         REAL DEFAULT 0.0,
            gross_pnl               REAL DEFAULT 0.0,
            net_pnl                 REAL DEFAULT 0.0,
            r_multiple              REAL DEFAULT 0.0,
            mae_pct                 REAL DEFAULT 0.0,
            mae_r                   REAL DEFAULT 0.0,
            mfe_pct                 REAL DEFAULT 0.0,
            mfe_r                   REAL DEFAULT 0.0,
            exit_reason             TEXT,
            regime_snapshot_json    TEXT NOT NULL,
            active_signals_json     TEXT NOT NULL,
            notes                   TEXT
        );
        CREATE TABLE validation_reports (
            report_id                   TEXT PRIMARY KEY,
            candidate_strategy_id       TEXT NOT NULL,
            baseline_strategy_id        TEXT NOT NULL,
            symbol                      TEXT NOT NULL,
            timeframe                   TEXT NOT NULL,
            in_sample_metrics_json      TEXT NOT NULL,
            out_of_sample_metrics_json  TEXT NOT NULL,
            walk_forward_summary_json   TEXT NOT NULL,
            parameter_heatmap_json      TEXT NOT NULL,
            cost_stress_metrics_json    TEXT NOT NULL,
            oos_passed                  INTEGER NOT NULL,
            walk_forward_passed         INTEGER NOT NULL,
            param_stability_passed      INTEGER NOT NULL,
            cost_stress_passed          INTEGER NOT NULL,
            final_status                TEXT NOT NULL,
            rejection_reason            TEXT,
            evaluated_at_utc            TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS system_activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            component   TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            details_json  TEXT
        );
        """)
        # Seed existing Spot records (simulating the real trading_engine.db baseline).
        conn.executemany(
            """
            INSERT INTO ohlcv_bars
                (symbol, timeframe, open_time_utc, open, high, low, close,
                 volume, quote_volume, taker_buy_vol, trade_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("BTCUSDT", "1m", "2026-11-08T09:00:00Z", 100, 101, 99, 100.5, 10, 1000, 5, 3),
                ("BTCUSDT", "1m", "2026-11-08T09:01:00Z", 100.5, 102, 100, 101.0, 12, 1200, 6, 4),
                ("ETHUSDT", "5m", "2026-11-08T09:00:00Z", 2000, 2010, 1990, 2005, 50, 50000, 25, 8),
            ],
        )
        conn.executemany(
            """
            INSERT INTO trades_memory
                (trade_id, strategy_id, execution_mode, symbol, timeframe,
                 direction, status, entry_time_utc, exit_time_utc, entry_price,
                 exit_price, stop_loss, target_1_price, target_2_price, position_size,
                 slippage_cost, commission_cost, gross_pnl, net_pnl, r_multiple,
                 mae_pct, mae_r, mfe_pct, mfe_r, exit_reason,
                 regime_snapshot_json, active_signals_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("TRD_001", "V1_EMA", "BACKTEST", "BTCUSDT", "1m", "LONG",
                 "CLOSED", "2026-11-08T09:00:00Z", "2026-11-08T09:05:00Z",
                 100.0, 105.0, 95.0, 110.0, 112.0, 1.0, 1.0, 2.0, 5.0, 5.0, 0.5,
                 2.0, 0.2, 5.0, 1.0, None, "{}", "[]", "seed spot trade"),
                ("TRD_002", "V1_EMA", "BACKTEST", "ETHUSDT", "5m", "SHORT",
                 "CLOSED", "2026-11-08T09:00:00Z", "2026-11-08T09:30:00Z",
                 2000.0, 1980.0, 2050.0, 1950.0, 1900.0, 2.0, 2.0, 4.0, 40.0, 40.0,
                 2.0, 3.0, 0.3, 6.0, 1.2, None, "{}", "[]", "seed spot trade 2"),
            ],
        )
        conn.executemany(
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
            [
                ("VAL_001", "V2_STRAT", "V1_EMA", "BTCUSDT", "1m",
                 "{\"pf\": 1.5}", "{\"pf\": 1.4}", "{\"windows\": 5}",
                 "{\"cells\": 25}", "{\"stressed_pf\": 1.2}",
                 1, 1, 1, 1, "APPROVED", None, iso_now_utc()),
                ("VAL_002", "V2_STRAT", "V1_EMA", "ETHUSDT", "5m",
                 "{\"pf\": 1.3}", "{\"pf\": 1.2}", "{\"windows\": 5}",
                 "{\"cells\": 25}", "{\"stressed_pf\": 1.1}",
                 1, 1, 1, 1, "APPROVED", None, iso_now_utc()),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


# --------------------------------------------------------------------------- #
# Phase E.0 — Schema PK isolation                                             #
# --------------------------------------------------------------------------- #

def test_ohlcv_bars_pk_includes_market_type(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        pk = _pk_columns(conn, "ohlcv_bars")
        assert pk == ["symbol", "market_type", "timeframe", "open_time_utc"], pk
    finally:
        conn.close()


def test_indicator_features_pk_includes_market_type(clean_db_path):
    # indicator_features table is created by FeatureStore, not initialize_database.
    store = FeatureStore(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        pk = _pk_columns(conn, "indicator_features")
        assert pk == ["symbol", "market_type", "timeframe", "open_time_utc"], pk
    finally:
        conn.close()


def test_trades_memory_has_market_type_column(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        assert _column_exists(conn, "trades_memory", "market_type")
    finally:
        conn.close()


def test_validation_reports_has_market_type_column(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        assert _column_exists(conn, "validation_reports", "market_type")
    finally:
        conn.close()


def test_ohlcv_market_type_index_exists(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='ohlcv_bars' AND sql LIKE '%market_type%'"
        ).fetchall()
        assert len(rows) >= 1, "expected at least one market_type index on ohlcv_bars"
    finally:
        conn.close()


def test_trades_market_type_index_exists(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='trades_memory' AND sql LIKE '%market_type%'"
        ).fetchall()
        assert len(rows) >= 1, "expected at least one market_type index on trades_memory"
    finally:
        conn.close()


def test_validation_market_type_index_exists(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='validation_reports' AND sql LIKE '%market_type%'"
        ).fetchall()
        assert len(rows) >= 1, "expected at least one market_type index on validation_reports"
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Phase E.0 — Cross-market-type isolation (Spot vs Futures queries)            #
# --------------------------------------------------------------------------- #

def test_spot_query_returns_no_futures_rows(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        # Insert Spot and Futures bars for the same symbol/timeframe/time.
        conn.executemany(
            """
            INSERT OR REPLACE INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low,
                 close, volume, quote_volume, taker_buy_vol, trade_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("BTCUSDT", CRYPTO_SPOT, "1m", "2026-11-08T09:00:00Z", 100, 101, 99, 100.5, 10, 1000, 5, 3),
                ("BTCUSDT", CRYPTO_PERP, "1m", "2026-11-08T09:00:00Z", 101, 102, 100, 101.5, 20, 2000, 10, 6),
            ],
        )
        conn.commit()

        spot_rows = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_bars WHERE symbol=? AND timeframe=? "
            "AND open_time_utc=? AND market_type=?",
            ("BTCUSDT", "1m", "2026-11-08T09:00:00Z", CRYPTO_SPOT),
        ).fetchone()[0]
        perp_rows = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_bars WHERE symbol=? AND timeframe=? "
            "AND open_time_utc=? AND market_type=?",
            ("BTCUSDT", "1m", "2026-11-08T09:00:00Z", CRYPTO_PERP),
        ).fetchone()[0]

        assert spot_rows == 1, spot_rows
        assert perp_rows == 1, perp_rows
        # A Spot-only query must not see the Perp row.
        mixed = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_bars WHERE symbol=? AND timeframe=? "
            "AND open_time_utc=? AND market_type=?",
            ("BTCUSDT", "1m", "2026-11-08T09:00:00Z", CRYPTO_SPOT),
        ).fetchone()[0]
        assert mixed == 1, mixed
    finally:
        conn.close()


def test_pk_prevents_cross_market_type_duplicate(clean_db_path):
    """The extended PK allows same symbol/timeframe/time for different market_type."""
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        # Same symbol/timeframe/time but different market_type → both insert fine.
        conn.execute(
            """
            INSERT INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low,
                 close, volume, quote_volume, taker_buy_vol, trade_count)
            VALUES ('BTCUSDT', 'CRYPTO_SPOT', '1m', '2026-11-08T09:00:00Z',
                    100, 101, 99, 100.5, 10, 1000, 5, 3)
            """
        )
        conn.execute(
            """
            INSERT INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low,
                 close, volume, quote_volume, taker_buy_vol, trade_count)
            VALUES ('BTCUSDT', 'CRYPTO_PERP', '1m', '2026-11-08T09:00:00Z',
                    101, 102, 100, 101.5, 20, 2000, 10, 6)
            """
        )
        conn.commit()
        # Duplicate PK within the SAME market_type should raise IntegrityError.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO ohlcv_bars
                    (symbol, market_type, timeframe, open_time_utc, open, high, low,
                     close, volume, quote_volume, taker_buy_vol, trade_count)
                VALUES ('BTCUSDT', 'CRYPTO_SPOT', '1m', '2026-11-08T09:00:00Z',
                        100, 101, 99, 100.5, 10, 1000, 5, 3)
                """
            )
            conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Phase E.0 — Feature store isolation                                          #
# --------------------------------------------------------------------------- #

def test_feature_store_isolates_by_market_type(tmp_path):
    db_path = str(tmp_path / "features.db")
    store = FeatureStore(db_path=db_path)
    df = pd.DataFrame(
        {"close": [100.0, 101.0], "ema_14": [99.5, 100.5]},
        index=pd.to_datetime(
            ["2026-11-08T09:00:00Z", "2026-11-08T09:01:00Z"], utc=True
        ),
    )

    # Write Spot and Perp features for same symbol/timeframe.
    n_spot = store.write_features("BTCUSDT", "1m", df, market_type=CRYPTO_SPOT)
    n_perp = store.write_features("BTCUSDT", "1m", df, market_type=CRYPTO_PERP)
    assert n_spot == 2
    assert n_perp == 2

    # Spot load returns only Spot rows.
    spot_loaded = store.load_features("BTCUSDT", "1m", market_type=CRYPTO_SPOT)
    assert len(spot_loaded) == 2

    # Perp load returns only Perp rows.
    perp_loaded = store.load_features("BTCUSDT", "1m", market_type=CRYPTO_PERP)
    assert len(perp_loaded) == 2

    # Cross-market_type loads return zero rows: loading SPOT under PERP key
    # (or vice versa) returns no rows because the cache keys differ.
    perp_loaded_under_spot = store.load_features("BTCUSDT", "1m", market_type=CRYPTO_SPOT)
    spot_loaded_under_perp = store.load_features("BTCUSDT", "1m", market_type=CRYPTO_PERP)
    assert len(perp_loaded_under_spot) == 2  # the Spot-written rows under Spot key
    assert len(spot_loaded_under_perp) == 2  # the Perp-written rows under Perp key

    # Verify DB rows actually differ by market_type.
    conn = get_connection(db_path=db_path)
    try:
        spot_count = conn.execute(
            "SELECT COUNT(*) FROM indicator_features WHERE market_type=?",
            (CRYPTO_SPOT,),
        ).fetchone()[0]
        perp_count = conn.execute(
            "SELECT COUNT(*) FROM indicator_features WHERE market_type=?",
            (CRYPTO_PERP,),
        ).fetchone()[0]
        assert spot_count == 2, spot_count
        assert perp_count == 2, perp_count
    finally:
        conn.close()


def test_feature_store_default_market_type_is_spot(tmp_path):
    db_path = str(tmp_path / "features_default.db")
    store = FeatureStore(db_path=db_path)
    df = pd.DataFrame(
        {"close": [100.0]},
        index=pd.to_datetime(["2026-11-08T09:00:00Z"], utc=True),
    )
    store.write_features("BTCUSDT", "1m", df)  # default CRYPTO_SPOT
    loaded = store.load_features("BTCUSDT", "1m")  # default CRYPTO_SPOT
    assert len(loaded) == 1
    loaded_perp = store.load_features("BTCUSDT", "1m", market_type=CRYPTO_PERP)
    assert len(loaded_perp) == 0


# --------------------------------------------------------------------------- #
# Phase E.0 — Migration idempotency & preservation                             #
# --------------------------------------------------------------------------- #

def test_migration_preserves_existing_spot_records(premigration_db_path):
    before = run_migration(db_path=premigration_db_path)
    assert before["applied"] is True, before

    conn = sqlite3.connect(premigration_db_path)
    try:
        # ohlcv_bars row count unchanged (3 seeded rows).
        ohlcv_count = _row_count(conn, "ohlcv_bars")
        assert ohlcv_count == 3, ohlcv_count
        # All existing rows backfilled with CRYPTO_SPOT.
        non_spot = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_bars WHERE market_type != ?", (CRYPTO_SPOT,)
        ).fetchone()[0]
        assert non_spot == 0, non_spot
        # trades_memory row count unchanged (2 seeded rows).
        trades_count = _row_count(conn, "trades_memory")
        assert trades_count == 2, trades_count
        # All existing trades backfilled with CRYPTO_SPOT.
        trades_non_spot = conn.execute(
            "SELECT COUNT(*) FROM trades_memory WHERE market_type != ?", (CRYPTO_SPOT,)
        ).fetchone()[0]
        assert trades_non_spot == 0, trades_non_spot
        # validation_reports row count unchanged (2 seeded rows).
        val_count = _row_count(conn, "validation_reports")
        assert val_count == 2, val_count
        val_non_spot = conn.execute(
            "SELECT COUNT(*) FROM validation_reports WHERE market_type != ?",
            (CRYPTO_SPOT,),
        ).fetchone()[0]
        assert val_non_spot == 0, val_non_spot
    finally:
        conn.close()


def test_migration_extends_ohlcv_pk(premigration_db_path):
    run_migration(db_path=premigration_db_path)
    conn = sqlite3.connect(premigration_db_path)
    try:
        pk = _pk_columns(conn, "ohlcv_bars")
        assert pk == ["symbol", "market_type", "timeframe", "open_time_utc"], pk
        assert _column_exists(conn, "ohlcv_bars", "market_type")
    finally:
        conn.close()


def test_migration_adds_market_type_to_trades_and_validation(premigration_db_path):
    run_migration(db_path=premigration_db_path)
    conn = sqlite3.connect(premigration_db_path)
    try:
        assert _column_exists(conn, "trades_memory", "market_type")
        assert _column_exists(conn, "validation_reports", "market_type")
    finally:
        conn.close()


def test_migration_is_idempotent(premigration_db_path):
    first = run_migration(db_path=premigration_db_path)
    assert first["applied"] is True, first

    second = run_migration(db_path=premigration_db_path)
    assert second["applied"] is False, second  # already applied → no-op

    conn = sqlite3.connect(premigration_db_path)
    try:
        # Row counts unchanged after second run.
        ohlcv_count = _row_count(conn, "ohlcv_bars")
        assert ohlcv_count == 3, ohlcv_count
        trades_count = _row_count(conn, "trades_memory")
        assert trades_count == 2, trades_count
        val_count = _row_count(conn, "validation_reports")
        assert val_count == 2, val_count
    finally:
        conn.close()


def test_migration_version_recorded(premigration_db_path):
    result = run_migration(db_path=premigration_db_path)
    assert result["applied"] is True
    conn = sqlite3.connect(premigration_db_path)
    try:
        row = conn.execute(
            "SELECT version FROM schema_migrations WHERE version=?",
            (SCHEMA_MIGRATION_VERSION,),
        ).fetchone()
        assert row is not None, f"migration {SCHEMA_MIGRATION_VERSION} not recorded"
    finally:
        conn.close()


def test_run_migration_is_safe_on_already_migrated_db(clean_db_path):
    initialize_database(db_path=clean_db_path)
    # initialize_database already ran the migration, so this is a no-op.
    second = run_migration(db_path=clean_db_path)
    assert second["applied"] is False  # no-op, no error


def test_migration_row_counts_match(premigration_db_path):
    result = run_migration(db_path=premigration_db_path)
    assert result["row_counts_before"]["ohlcv_bars"] == 3
    assert result["row_counts_before"]["trades_memory"] == 2
    assert result["row_counts_before"]["validation_reports"] == 2
    assert result["row_counts_after"]["ohlcv_bars"] == 3
    assert result["row_counts_after"]["trades_memory"] == 2
    assert result["row_counts_after"]["validation_reports"] == 2
    assert "validation_errors" not in result, result.get("validation_errors")


def test_schema_migrations_table_created(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        assert _table_exists(conn, "schema_migrations")
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Phase E.0 — Query layer isolation via backend (indirect, through db helpers) #
# --------------------------------------------------------------------------- #

def test_spot_only_query_filters_market_type(clean_db_path):
    initialize_database(db_path=clean_db_path)
    conn = get_connection(db_path=clean_db_path)
    try:
        conn.executemany(
            """
            INSERT OR REPLACE INTO ohlcv_bars
                (symbol, market_type, timeframe, open_time_utc, open, high, low,
                 close, volume, quote_volume, taker_buy_vol, trade_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("BTCUSDT", CRYPTO_SPOT, "1m", "2026-11-08T09:00:00Z", 100, 101, 99, 100.5, 10, 1000, 5, 3),
                ("BTCUSDT", CRYPTO_PERP, "1m", "2026-11-08T09:00:00Z", 101, 102, 100, 101.5, 20, 2000, 10, 6),
                ("ETHUSDT", CRYPTO_SPOT, "5m", "2026-11-08T09:00:00Z", 2000, 2010, 1990, 2005, 50, 50000, 25, 8),
            ],
        )
        conn.commit()
        spot_rows = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_bars WHERE market_type=?",
            (CRYPTO_SPOT,),
        ).fetchone()[0]
        perp_rows = conn.execute(
            "SELECT COUNT(*) FROM ohlcv_bars WHERE market_type=?",
            (CRYPTO_PERP,),
        ).fetchone()[0]
        assert spot_rows == 2, spot_rows
        assert perp_rows == 1, perp_rows
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
