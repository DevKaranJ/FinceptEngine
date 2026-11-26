"""memory/db.py — SQLite WAL-mode schema initialization.

Tables (DATABASE_AND_DATA_CONTRACTS.md Section 1):
  1. ohlcv_bars            — Historical & live candle store
  2. trades_memory         — Data & trade memory (MAE/MFE + regime snapshots)
  3. strategy_registry     — Baseline V1 + candidate V2 version control
  4. validation_reports    — Independent gatekeeper scorecard
  5. system_activity_log   — Live engine & agent audit trail
  6. schema_migrations     — Versioned one-time migration ledger (Phase E.0)

Database file: trading_engine.db (PRAGMA journal_mode=WAL)

Phase E.0 — Market Contracts & Schema Isolation:
  - ohlcv_bars    PRIMARY KEY extended to (symbol, market_type, timeframe, open_time_utc)
  - indicator_features  PRIMARY KEY extended to (symbol, market_type, timeframe, open_time_utc)
  - trades_memory      market_type column added (default CRYPTO_SPOT)
  - validation_reports market_type column added (default CRYPTO_SPOT)
  - Market-type indexes added on ohlcv_bars, indicator_features, trades_memory, validation_reports
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from ..config import DB_PATH, DB_WAL_MODE, DB_BUSY_TIMEOUT_MS
from ..data.clock import iso_now_utc

# ---------------------------------------------------------------------------
# Migration versioning
# ---------------------------------------------------------------------------

SCHEMA_MIGRATION_VERSION = "1.0.0-e0"  # Phase E.0 market-type isolation migration

TABLE_SCHEMA: dict[str, str] = {
    "ohlcv_bars": """
        CREATE TABLE IF NOT EXISTS ohlcv_bars (
            symbol          TEXT NOT NULL,
            market_type     TEXT NOT NULL, -- 'CRYPTO_SPOT', 'CRYPTO_PERP' (Binance only)
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
            PRIMARY KEY (symbol, market_type, timeframe, open_time_utc)
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
            notes                   TEXT,
            market_type             TEXT NOT NULL DEFAULT 'CRYPTO_SPOT'
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
            evaluated_at_utc            TEXT NOT NULL,
            market_type                 TEXT NOT NULL DEFAULT 'CRYPTO_SPOT'
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
    "schema_migrations": """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version           TEXT PRIMARY KEY,
            applied_at_utc    TEXT NOT NULL,
            description       TEXT NOT NULL,
            row_counts_json   TEXT
        );
    """,
}

CREATE_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_tf_time ON ohlcv_bars(symbol, timeframe, open_time_utc);",
    "CREATE INDEX IF NOT EXISTS idx_ohlcv_market_type ON ohlcv_bars(market_type);",
    "CREATE INDEX IF NOT EXISTS idx_ohlcv_market_type_symbol ON ohlcv_bars(market_type, symbol);",
    "CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades_memory(strategy_id);",
    "CREATE INDEX IF NOT EXISTS idx_trades_mode ON trades_memory(execution_mode);",
    "CREATE INDEX IF NOT EXISTS idx_trades_market_type ON trades_memory(market_type);",
    "CREATE INDEX IF NOT EXISTS idx_validation_market_type ON validation_reports(market_type);",
    "CREATE INDEX IF NOT EXISTS idx_activity_component ON system_activity_log(component);",
]


# ---------------------------------------------------------------------------
# Schema migration (Phase E.0 — versioned, one-time)
# ---------------------------------------------------------------------------

def _get_applied_migrations(conn: sqlite3.Connection) -> set[str]:
    """Return the set of migration versions already applied."""
    try:
        cur = conn.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        # schema_migrations table doesn't exist yet → nothing applied
        return set()


def _record_migration(
    conn: sqlite3.Connection,
    version: str,
    description: str,
    row_counts: dict[str, int] | None = None,
) -> None:
    """Record an applied migration in schema_migrations."""
    conn.execute(
        """
        INSERT OR REPLACE INTO schema_migrations
            (version, applied_at_utc, description, row_counts_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            version,
            iso_now_utc(),
            description,
            json.dumps(row_counts or {}),
        ),
    )


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    return any(col[1] == column_name for col in cur.fetchall())


def _pk_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    """Return the primary key column names of a table (in PK order)."""
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    pk_cols = [row[1] for row in cur.fetchall() if row[5] > 0]
    return pk_cols


def _row_count(conn: sqlite3.Connection, table_name: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]


def run_migration(db_path: str = DB_PATH) -> dict[str, Any]:
    """Apply the Phase E.0 market-type isolation migration (versioned, one-time).

    SQLite does not support ALTER TABLE ... MODIFY PRIMARY KEY, so the
    migration rebuilds `ohlcv_bars` and (implicitly via feature store) the
    feature-store schema by creating new tables, copying+backfilling data,
    replacing, recreating indexes, recording the migration version, and
    validating.

    Steps:
      1. Ensure schema_migrations table exists.
      2. If SCHEMA_MIGRATION_VERSION already applied → return idempotent no-op.
      3. Add `market_type` column to `trades_memory` and `validation_reports`
         (defaulting existing rows to CRYPTO_SPOT).
      4. Rebuild `ohlcv_bars` with extended PK (symbol, market_type, timeframe,
         open_time_utc) — copy existing rows with market_type='CRYPTO_SPOT'.
      5. Recreate all indexes.
      6. Record migration version + row counts.
      7. Validate: PK columns correct, market_type present, row counts match,
         no duplicate PK violations.

    Returns a dict summarizing the migration result.
    """
    result: dict[str, Any] = {
        "version": SCHEMA_MIGRATION_VERSION,
        "applied": False,
        "steps": [],
        "row_counts_before": {},
        "row_counts_after": {},
    }

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()

        # 0. Ensure the migration ledger table exists.
        cur.execute(TABLE_SCHEMA["schema_migrations"])
        conn.commit()

        # 1. Idempotency check — skip if already applied.
        applied = _get_applied_migrations(conn)
        if SCHEMA_MIGRATION_VERSION in applied:
            result["applied"] = False
            result["steps"].append(
                f"Migration {SCHEMA_MIGRATION_VERSION} already applied; skipping."
            )
            return result

        # Capture before-row counts.
        for table in ("ohlcv_bars", "trades_memory", "validation_reports"):
            if _table_exists(conn, table):
                result["row_counts_before"][table] = _row_count(conn, table)

        # 2. Add `market_type` to trades_memory (default CRYPTO_SPOT for existing rows).
        if _table_exists(conn, "trades_memory") and not _column_exists(
            conn, "trades_memory", "market_type"
        ):
            cur.execute(
                "ALTER TABLE trades_memory ADD COLUMN market_type "
                "TEXT NOT NULL DEFAULT 'CRYPTO_SPOT'"
            )
            conn.commit()
            result["steps"].append(
                "Added market_type column to trades_memory (default CRYPTO_SPOT)."
            )

        # 3. Add `market_type` to validation_reports (default CRYPTO_SPOT).
        if _table_exists(conn, "validation_reports") and not _column_exists(
            conn, "validation_reports", "market_type"
        ):
            cur.execute(
                "ALTER TABLE validation_reports ADD COLUMN market_type "
                "TEXT NOT NULL DEFAULT 'CRYPTO_SPOT'"
            )
            conn.commit()
            result["steps"].append(
                "Added market_type column to validation_reports (default CRYPTO_SPOT)."
            )

        # 4. Rebuild ohlcv_bars with extended PK including market_type.
        if _table_exists(conn, "ohlcv_bars"):
            before_count = _row_count(conn, "ohlcv_bars")
            old_pk = _pk_columns(conn, "ohlcv_bars")
            needs_rebuild = old_pk != ["symbol", "market_type", "timeframe", "open_time_utc"]

            if needs_rebuild:
                cur.execute(
                    "CREATE TABLE ohlcv_bars_new ("
                    "    symbol          TEXT NOT NULL,"
                    "    market_type     TEXT NOT NULL,"
                    "    timeframe       TEXT NOT NULL,"
                    "    open_time_utc   TEXT NOT NULL,"
                    "    open            REAL NOT NULL,"
                    "    high            REAL NOT NULL,"
                    "    low             REAL NOT NULL,"
                    "    close           REAL NOT NULL,"
                    "    volume          REAL NOT NULL,"
                    "    quote_volume    REAL DEFAULT 0.0,"
                    "    taker_buy_vol   REAL DEFAULT 0.0,"
                    "    trade_count     INTEGER DEFAULT 0,"
                    "    PRIMARY KEY (symbol, market_type, timeframe, open_time_utc)"
                    ")"
                )
                # Copy existing rows, backfilling market_type='CRYPTO_SPOT'.
                cur.execute(
                    """
                    INSERT INTO ohlcv_bars_new
                        (symbol, market_type, timeframe, open_time_utc,
                         open, high, low, close, volume, quote_volume,
                         taker_buy_vol, trade_count)
                    SELECT symbol, 'CRYPTO_SPOT', timeframe, open_time_utc,
                           open, high, low, close, volume, quote_volume,
                           taker_buy_vol, trade_count
                    FROM ohlcv_bars
                    """
                )
                cur.execute("DROP TABLE ohlcv_bars")
                cur.execute(
                    "ALTER TABLE ohlcv_bars_new RENAME TO ohlcv_bars"
                )
                conn.commit()
                result["steps"].append(
                    f"Rebuilt ohlcv_bars with PK (symbol, market_type, timeframe, "
                    f"open_time_utc); copied {before_count} rows with "
                    f"market_type='CRYPTO_SPOT'."
                )
            else:
                result["steps"].append(
                    "ohlcv_bars already has market_type-inclusive PK; skipping rebuild."
                )

        # 5. Recreate all indexes idempotently.
        for index_ddl in CREATE_INDEXES:
            cur.execute(index_ddl)
        conn.commit()
        result["steps"].append("Recreated all indexes (idempotent).")

        # 6. Record migration version + row counts.
        after_counts: dict[str, int] = {}
        for table in ("ohlcv_bars", "trades_memory", "validation_reports"):
            if _table_exists(conn, table):
                after_counts[table] = _row_count(conn, table)
        result["row_counts_after"] = after_counts

        _record_migration(
            conn,
            SCHEMA_MIGRATION_VERSION,
            "Phase E.0: market_type isolation — extended PKs on ohlcv_bars/"
            "indicator_features, added market_type to trades_memory/"
            "validation_reports, recreated indexes.",
            row_counts=after_counts,
        )
        conn.commit()
        result["applied"] = True
        result["steps"].append(
            f"Recorded migration {SCHEMA_MIGRATION_VERSION} in schema_migrations."
        )

        # 7. Validate.
        validation_errors: list[str] = []

        # ohlcv_bars PK must include market_type.
        if _table_exists(conn, "ohlcv_bars"):
            new_pk = _pk_columns(conn, "ohlcv_bars")
            expected_pk = ["symbol", "market_type", "timeframe", "open_time_utc"]
            if new_pk != expected_pk:
                validation_errors.append(
                    f"ohlcv_bars PK is {new_pk}, expected {expected_pk}"
                )
            if not _column_exists(conn, "ohlcv_bars", "market_type"):
                validation_errors.append("ohlcv_bars missing market_type column")

        # trades_memory must have market_type column.
        if _table_exists(conn, "trades_memory"):
            if not _column_exists(conn, "trades_memory", "market_type"):
                validation_errors.append("trades_memory missing market_type column")

        # validation_reports must have market_type column.
        if _table_exists(conn, "validation_reports"):
            if not _column_exists(conn, "validation_reports", "market_type"):
                validation_errors.append("validation_reports missing market_type column")

        # Row counts must match before/after (preservation).
        for table in ("ohlcv_bars", "trades_memory", "validation_reports"):
            before = result["row_counts_before"].get(table)
            after = after_counts.get(table)
            if before is not None and after is not None and before != after:
                validation_errors.append(
                    f"{table} row count changed: {before} -> {after}"
                )

        if validation_errors:
            result["validation_errors"] = validation_errors
            result["steps"].append(
                "VALIDATION FAILED: " + "; ".join(validation_errors)
            )
        else:
            result["steps"].append("Migration validation PASSED.")

    finally:
        conn.close()

    return result


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection in WAL mode with a busy timeout."""
    conn = sqlite3.connect(db_path, timeout=DB_BUSY_TIMEOUT_MS / 1000.0)
    conn.execute(DB_WAL_MODE)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str = DB_PATH) -> None:
    """Create all tables and indexes idempotently, then run any pending migrations.

    Order matters: tables must exist before migration; migrations add columns
    (e.g. market_type) that new indexes depend on — so indexes are created
    AFTER migrations run.
    """
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        for table_name, ddl in TABLE_SCHEMA.items():
            cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()

    # Run pending schema migrations first (adds market_type column etc.).
    run_migration(db_path=db_path)

    # Then create indexes idempotently (now safe: market_type columns exist).
    conn = get_connection(db_path)
    try:
        for index_ddl in CREATE_INDEXES:
            cur = conn.cursor()
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
    "SCHEMA_MIGRATION_VERSION",
    "run_migration",
]
