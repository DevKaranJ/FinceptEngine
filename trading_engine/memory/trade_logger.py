"""memory/trade_logger.py — Persist trades with MAE/MFE, regime & signal snapshots.

Responsibilities (PRD Phase 3 / master_architecture Section 2, Layer 3):
  • Open a trade record (status=OPEN) in ``trades_memory``.
  • Track real-time MAE/MFE for open positions.
  • Close a trade (exit price, gross/net PnL, R-multiple, MAE/MFE, exit reason).
  • Every trade links to a ``strategy_id`` (V1 baseline or V2 candidate) and an
    ``execution_mode`` (BACKTEST / PAPER_LIVE / MANUAL_LIVE).

Zero look-ahead: MAE/MFE are computed only from bars observed up to the current
bar — never future data. The caller (paper_simulator / backtester) feeds
historical bars in chronological order.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import DB_PATH
from ..memory.db import get_connection, initialize_database, log_activity
from ..data.clock import iso_utc, now_utc


def _new_trade_id() -> str:
    return f"TRD_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


class TradeLogger:
    """Appends and updates trade records in ``trades_memory`` (SQLite WAL)."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        initialize_database(db_path=self.db_path)

    # ------------------------------------------------------------------ #
    # Open / update a trade                                               #
    # ------------------------------------------------------------------ #
    def open_trade(
        self,
        *,
        strategy_id: str,
        execution_mode: str,
        symbol: str,
        timeframe: str,
        direction: str,
        entry_time_utc: str,
        entry_price: float,
        stop_loss: float,
        target_1_price: float,
        target_2_price: float | None,
        position_size: float,
        regime_snapshot: dict[str, Any],
        active_signals: list[str],
        trade_id: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Insert a new OPEN trade record. Returns the ``trade_id``."""
        trade_id = trade_id or _new_trade_id()
        conn = get_connection(db_path=self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO trades_memory
                    (trade_id, strategy_id, execution_mode, symbol, timeframe,
                     direction, status, entry_time_utc, entry_price,
                     stop_loss, target_1_price, target_2_price, position_size,
                     regime_snapshot_json, active_signals_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_id, strategy_id, execution_mode, symbol, timeframe,
                    direction, entry_time_utc, entry_price,
                    stop_loss, target_1_price, target_2_price, position_size,
                    json.dumps(regime_snapshot or {}),
                    json.dumps(list(active_signals or [])),
                    notes,
                ),
            )
            conn.commit()
            log_activity(
                "STRATEGY_ENGINE", "TRADE_OPENED",
                f"{strategy_id} {direction} {symbol} @ {entry_price}",
                {"trade_id": trade_id, "strategy_id": strategy_id,
                 "direction": direction, "entry_price": entry_price},
                db_path=self.db_path,
            )
            return trade_id
        finally:
            conn.close()

    def update_mae_mfe(
        self,
        trade_id: str,
        *,
        current_price: float,
        current_high: float,
        current_low: float,
    ) -> None:
        """Refresh MAE/MFE for an OPEN trade using bars seen so far.

        MAE/MFE are computed from the entry price to the current bar only
        (t <= T) — no future leakage.
        """
        conn = get_connection(db_path=self.db_path)
        try:
            row = conn.execute(
                "SELECT direction, entry_price, stop_loss FROM trades_memory WHERE trade_id=? AND status='OPEN'",
                (trade_id,),
            ).fetchone()
            if row is None:
                return

            direction = row["direction"]
            entry_price = float(row["entry_price"])
            stop_loss = float(row["stop_loss"])
            risk = abs(entry_price - stop_loss)
            if risk <= 0:
                return

            if direction == "LONG":
                mae = (min(current_low, entry_price) - entry_price) / risk
                mfe = (max(current_high, entry_price) - entry_price) / risk
                mae_pct = (min(current_low, entry_price) - entry_price) / entry_price * 100.0
                mfe_pct = (max(current_high, entry_price) - entry_price) / entry_price * 100.0
            else:  # SHORT
                mae = (entry_price - max(current_high, entry_price)) / risk
                mfe = (entry_price - min(current_low, entry_price)) / risk
                mae_pct = (entry_price - max(current_high, entry_price)) / entry_price * 100.0
                mfe_pct = (entry_price - min(current_low, entry_price)) / entry_price * 100.0

            conn.execute(
                """
                UPDATE trades_memory
                SET mae_pct=?, mae_r=?, mfe_pct=?, mfe_r=?
                WHERE trade_id=? AND status='OPEN'
                """,
                (mae_pct, mae, mfe_pct, mfe, trade_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Close a trade                                                       #
    # ------------------------------------------------------------------ #
    def close_trade(
        self,
        trade_id: str,
        *,
        exit_time_utc: str,
        exit_price: float,
        slippage_cost: float = 0.0,
        commission_cost: float = 0.0,
        exit_reason: str = "MANUAL",
    ) -> dict[str, Any] | None:
        """Close an OPEN trade and compute gross/net PnL & R-multiple.

        Returns the finalized trade record dict, or ``None`` if the trade was
        not found / already closed.
        """
        conn = get_connection(db_path=self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM trades_memory WHERE trade_id=? AND status='OPEN'",
                (trade_id,),
            ).fetchone()
            if row is None:
                return None

            entry_price = float(row["entry_price"])
            stop_loss = float(row["stop_loss"])
            position_size = float(row["position_size"])
            direction = row["direction"]
            risk = abs(entry_price - stop_loss)

            if direction == "LONG":
                gross_pnl = (exit_price - entry_price) * position_size
            else:
                gross_pnl = (entry_price - exit_price) * position_size

            net_pnl = gross_pnl - slippage_cost - commission_cost
            r_multiple = (net_pnl / (risk * position_size)) if (risk * position_size) > 0 else 0.0

            conn.execute(
                """
                UPDATE trades_memory
                SET status='CLOSED', exit_time_utc=?, exit_price=?,
                    slippage_cost=?, commission_cost=?, gross_pnl=?, net_pnl=?,
                    r_multiple=?, exit_reason=?
                WHERE trade_id=?
                """,
                (
                    exit_time_utc, exit_price,
                    slippage_cost, commission_cost,
                    gross_pnl, net_pnl,
                    r_multiple, exit_reason,
                    trade_id,
                ),
            )
            conn.commit()

            log_activity(
                "STRATEGY_ENGINE", "TRADE_CLOSED",
                f"{row['strategy_id']} {direction} {row['symbol']} net_pnl={net_pnl:.2f}",
                {"trade_id": trade_id, "strategy_id": row["strategy_id"],
                 "net_pnl": net_pnl, "r_multiple": r_multiple,
                 "exit_reason": exit_reason},
                db_path=self.db_path,
            )

            return self._row_to_dict(conn.execute(
                "SELECT * FROM trades_memory WHERE trade_id=?", (trade_id,)
            ).fetchone())
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Read helpers                                                        #
    # ------------------------------------------------------------------ #
    def get_open_trade(self, trade_id: str) -> dict[str, Any] | None:
        conn = get_connection(db_path=self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM trades_memory WHERE trade_id=? AND status='OPEN'",
                (trade_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def get_trade(self, trade_id: str) -> dict[str, Any] | None:
        conn = get_connection(db_path=self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM trades_memory WHERE trade_id=?", (trade_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_trades(self, strategy_id: str | None = None,
                    execution_mode: str | None = None,
                    status: str | None = None) -> list[dict[str, Any]]:
        conn = get_connection(db_path=self.db_path)
        try:
            query = "SELECT * FROM trades_memory WHERE 1=1"
            params: list[Any] = []
            if strategy_id is not None:
                query += " AND strategy_id=?"; params.append(strategy_id)
            if execution_mode is not None:
                query += " AND execution_mode=?"; params.append(execution_mode)
            if status is not None:
                query += " AND status=?"; params.append(status)
            query += " ORDER BY entry_time_utc DESC"
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Internal                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        for json_key in ("regime_snapshot_json", "active_signals_json"):
            if d.get(json_key):
                try:
                    d[json_key] = json.loads(d[json_key])
                except Exception:
                    pass
        return d
