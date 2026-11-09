"""memory/db.py — SQLite WAL-mode schema initialization.

Tables (DATABASE_AND_DATA_CONTRACTS.md Section 1):
  1. ohlcv_bars            — Historical & live candle store
  2. trades_memory         — Data & trade memory (MAE/MFE + regime snapshots)
  3. strategy_registry     — Baseline V1 + candidate V2 version control
  4. validation_reports    — Independent gatekeeper scorecard
  5. system_activity_log   — Live engine & agent audit trail

Database file: trading_engine.db (PRAGMA journal_mode=WAL)
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..config import DB_PATH, DB_WAL_MODE, DB_BUSY_TIMEOUT_MS
from ..data.clock import iso_now_utc

TABLE_SCHEMA: dict[str, str] = {
    "ohlcv_bars": """
        CREATE TABLE IF NOT EXISTS ohlcv_bars (
            symbol          TEXT NOT NULL,
            market_type     TEXT NOT NULL, -- 'CRYPTO_SPOT', 'CRYPTO_PERP', 'NSE_EQUITY'
            timeframe       TEXT NOT NULL, -- '1m', '5m', '15m', '1h', '1d'
            open_time_utc   TEXT NOT NULL, -- ISO-8601 UTC timestamp
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
    """,
    "trades_memory": """
        CREATE TABLE IF NOT EXISTS trades_memory (
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
    """,
    "strategy_registry": """
        CREATE TABLE IF NOT EXISTS strategy_registry (
            strategy_id         TEXT PRIMARY KEY,
            parent_strategy_id  TEXT,
            file_path           TEXT NOT NULL,
            status              TEXT NOT NULL,
            paradigm_tags_json  TEXT NOT NULL,
            parameters_json     TEXT NOT NULL,
            hypothesis_summary  TEXT,
            created_at_utc      TEXT NOT NULL,
            promoted_at_utc     TEXT
        );
    """,
    "validation_reports": """
        CREATE TABLE IF NOT EXISTS validation_reports (
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
            oos_passed                  INTEGER NOT NULL, -- 1 = PASS, 0 = FAIL
            walk_forward_passed         INTEGER NOT NULL,
            param_stability_passed      INTEGER NOT NULL,
            cost_stress_passed          INTEGER NOT NULL,
            final_status                TEXT NOT NULL,    -- 'APPROVED' or 'REJECTED'
            rejection_reason            TEXT,
            evaluated_at_utc            TEXT NOT NULL
        );
    """,
    "system_activity_log": """
        CREATE TABLE IF NOT EXISTS system_activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            component   TEXT NOT NULL, -- 'DATA_FEED', 'STRATEGY_ENGINE', 'EVALUATION', 'RESEARCH_AGENT', 'GATEKEEPER'
            event_type  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            details_json  TEXT
        );
    """,
}

CREATE_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_time ON ohlcv_bars(symbol, timeframe, open_time_utc);",
    "CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades_memory(strategy_id);",
    "CREATE INDEX IF NOT EXISTS idx_trades_mode ON trades_memory(execution_mode);",
    "CREATE INDEX IF NOT EXISTS idx_activity_component ON system_activity_log(component);",
]


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection in WAL mode with a busy timeout."""
    conn = sqlite3.connect(db_path, timeout=DB_BUSY_TIMEOUT_MS / 1000.0)
    conn.execute(DB_WAL_MODE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str = DB_PATH) -> None:
    """Create all tables and indexes idempotently."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        for table_name, ddl in TABLE_SCHEMA.items():
            cur.execute(ddl)
        for index_ddl in CREATE_INDEXES:
            cur.execute(index_ddl)
        conn.commit()
    finally:
        conn.close()


def log_activity(
    component: str,
    event_type: str,
    summary: str,
    details: dict[str, Any] | None = None,
    db_path: str = DB_PATH,
) -> None:
    """Append an entry to system_activity_log."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO system_activity_log
                (timestamp_utc, component, event_type, summary, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                iso_now_utc(),
                component,
                event_type,
                summary,
                json.dumps(details) if details is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def now_utc_iso() -> str:
    """Current UTC time as ISO-8601 (re-exported convenience alias)."""
    return iso_now_utc()


__all__ = [
    "get_connection",
    "initialize_database",
    "log_activity",
    "now_utc_iso",
    "TABLE_SCHEMA",
    "CREATE_INDEXES",
]
