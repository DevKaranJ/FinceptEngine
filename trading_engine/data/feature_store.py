"""data/feature_store.py — SQLite + Parquet feature cache (zero look-ahead).

Caches and aligns computed indicator series across multiple timeframes
(1m, 5m, 15m, 1h, 1d) in SQLite / Parquet so Backtesting, Paper Trading, and
Evaluation read identical features with zero look-ahead bias.

Responsibilities (PRD Phase 2 / master_architecture Section 2):
  • Persist computed indicator feature frames per (symbol, timeframe).
  • Load a feature frame up to and including a given timestamp T (t <= T),
    guaranteeing zero look-ahead for backtest/paper evaluation.
  • Optional Parquet export/import for offline feature caches.

Declared dependencies: ``pandas``, ``numpy``, ``pyarrow`` (optional),
``sqlite3`` (stdlib).
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

import numpy as np
import pandas as pd

from ..config import DB_PATH, DB_WAL_MODE, DB_BUSY_TIMEOUT_MS
from ..memory.db import get_connection, initialize_database, log_activity

# Try pyarrow for Parquet support; degrade gracefully if unavailable.
try:  # pragma: no cover - optional dependency
    import pyarrow as pa
    import pyarrow.parquet as pq

    _HAS_PYARROW = True
except Exception:  # pragma: no cover - optional dependency
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    _HAS_PYARROW = False

__all__ = [
    "FeatureStore",
    "get_feature_store",
    "zero_look_ahead_slice",
]


def zero_look_ahead_slice(df: pd.DataFrame, timestamp: Any) -> pd.DataFrame:
    """Return rows of ``df`` with index <= ``timestamp`` (t <= T).

    Guarantees zero look-ahead: only rows at or before ``timestamp`` are
    returned, regardless of how far the DataFrame extends into the future.
    """
    if df.empty:
        return df
    ts = pd.Timestamp(timestamp)
    if df.index.tz is None and ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    elif df.index.tz is not None and ts.tzinfo is None:
        ts = ts.tz_localize(df.index.tz)
    return df.loc[df.index <= ts].copy()


class FeatureStore:
    """Persistent feature cache for indicator series across symbols/timeframes.

    Schema (table ``indicator_features``):
        symbol TEXT, market_type TEXT, timeframe TEXT, open_time_utc TEXT,
        feature_json TEXT,
        PRIMARY KEY (symbol, market_type, timeframe, open_time_utc)

    Phase E.0 — market-type isolation: every cache key and query includes
    ``market_type`` so Spot and Futures features are never aliased.
    """

    FEATURE_TABLE = "indicator_features"

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        initialize_database(db_path=self.db_path)
        self._ensure_feature_table()

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #
    def _ensure_feature_table(self) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.FEATURE_TABLE} (
                    symbol          TEXT NOT NULL,
                    market_type     TEXT NOT NULL,
                    timeframe       TEXT NOT NULL,
                    open_time_utc   TEXT NOT NULL,
                    feature_json    TEXT NOT NULL,
                    PRIMARY KEY (symbol, market_type, timeframe, open_time_utc)
                );
                """
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_features_symbol_tf_time "
                f"ON {self.FEATURE_TABLE}(symbol, timeframe, open_time_utc);"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_features_market_type "
                f"ON {self.FEATURE_TABLE}(market_type);"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_features_market_symbol_tf_time "
                f"ON {self.FEATURE_TABLE}(market_type, symbol, timeframe, open_time_utc);"
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def write_features(self, symbol: str, timeframe: str,
                       df: pd.DataFrame,
                       market_type: str = "CRYPTO_SPOT") -> int:
        """Persist a feature DataFrame (index = UTC timestamps) to SQLite.

        Each row is stored as a JSON blob of feature columns so any number of
        indicator columns can be cached without a fixed schema. Returns the
        number of rows written.

        Phase E.0: ``market_type`` is part of the cache key (PK) so Spot and
        Futures features for the same symbol/timeframe are never aliased.
        Defaults to ``CRYPTO_SPOT`` for backward compatibility with existing
        Spot-only callers.
        """
        if df.empty:
            return 0
        df = df.sort_index()
        rows = []
        for ts, row in df.iterrows():
            open_time_utc = pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
            feature_json = row.to_json()
            rows.append((symbol, market_type, timeframe, open_time_utc, feature_json))

        conn = get_connection(self.db_path)
        try:
            conn.executemany(
                f"""
                INSERT OR REPLACE INTO {self.FEATURE_TABLE}
                    (symbol, market_type, timeframe, open_time_utc, feature_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            log_activity(
                "FEATURE_STORE", "WRITE_FEATURES",
                f"{symbol} {market_type} {timeframe}: {len(rows)} feature rows cached",
                {"symbol": symbol, "market_type": market_type,
                 "timeframe": timeframe, "count": len(rows)},
                db_path=self.db_path,
            )
            return len(rows)
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Read (zero look-ahead)
    # ------------------------------------------------------------------ #
    def load_features(self, symbol: str, timeframe: str,
                      timestamp: Any = None,
                      start_time: Any = None,
                      market_type: str = "CRYPTO_SPOT") -> pd.DataFrame:
        """Load cached features up to ``timestamp`` (zero look-ahead).

        If ``timestamp`` is None, returns all cached features. If
        ``start_time`` is given, returns features in [start_time, timestamp].

        Phase E.0: queries are filtered by ``market_type`` so Spot queries
        never return Futures features and vice versa. Defaults to
        ``CRYPTO_SPOT`` for backward compatibility with existing Spot-only
        callers.
        """
        conn = get_connection(self.db_path)
        try:
            query = f"""
                SELECT open_time_utc, feature_json
                FROM {self.FEATURE_TABLE}
                WHERE symbol = ? AND market_type = ? AND timeframe = ?
            """
            params: list[Any] = [symbol, market_type, timeframe]
            if timestamp is not None:
                query += " AND open_time_utc <= ?"
                params.append(pd.Timestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%SZ"))
            if start_time is not None:
                query += " AND open_time_utc >= ?"
                params.append(pd.Timestamp(start_time).strftime("%Y-%m-%dT%H:%M:%SZ"))
            query += " ORDER BY open_time_utc ASC"

            cur = conn.execute(query, params)
            rows = cur.fetchall()
        finally:
            conn.close()

        if not rows:
            return pd.DataFrame()

        records = []
        for open_time_utc, feature_json in rows:
            rec = {"open_time_utc": open_time_utc}
            try:
                import json
                rec.update(json.loads(feature_json))
            except Exception:  # pragma: no cover - defensive
                pass
            records.append(rec)

        df = pd.DataFrame(records)
        df["open_time_utc"] = pd.to_datetime(df["open_time_utc"], utc=True)
        df = df.set_index("open_time_utc").sort_index()
        return df

    # ------------------------------------------------------------------ #
    # Parquet export / import (optional)
    # ------------------------------------------------------------------ #
    def export_to_parquet(self, symbol: str, timeframe: str, path: str,
                          market_type: str = "CRYPTO_SPOT") -> None:
        """Export cached features for a (symbol, timeframe, market_type) to a Parquet file."""
        if not _HAS_PYARROW:
            raise RuntimeError("pyarrow is required for Parquet export")
        df = self.load_features(symbol, timeframe, market_type=market_type)
        if df.empty:
            return
        table = pa.Table.from_pandas(df.reset_index())
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        pq.write_table(table, path)

    def import_from_parquet(self, symbol: str, timeframe: str, path: str,
                            market_type: str = "CRYPTO_SPOT") -> int:
        """Import features from a Parquet file into the SQLite cache."""
        if not _HAS_PYARROW:
            raise RuntimeError("pyarrow is required for Parquet import")
        table = pq.read_table(path)
        df = table.to_pandas()
        if "open_time_utc" in df.columns:
            df["open_time_utc"] = pd.to_datetime(df["open_time_utc"], utc=True)
            df = df.set_index("open_time_utc")
        return self.write_features(symbol, timeframe, df, market_type=market_type)


_feature_store: FeatureStore | None = None


def get_feature_store(db_path: str = DB_PATH) -> FeatureStore:
    """Module-level singleton FeatureStore."""
    global _feature_store
    if _feature_store is None or _feature_store.db_path != db_path:
        _feature_store = FeatureStore(db_path=db_path)
    return _feature_store
