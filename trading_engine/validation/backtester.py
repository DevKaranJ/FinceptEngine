"""validation/backtester.py — Historical Event-Driven Backtester (Layer 4A).

Replays historical OHLCV bars through a ``BaseStrategy`` in chronological order
(tick-by-tick), records fills to ``trades_memory`` via ``TradeLogger``, and
returns structured trade-log dicts consumed by ``evaluation/analyzer.py`` and
``validation/gatekeeper.py``.

Responsibilities (PRD Phase 4):
  • Run a strategy's ``evaluate()`` bar-by-bar over a feature DataFrame.
  • Simulate stop-loss / take-profit / time exits using only current-bar OHLC
    (zero look-ahead: ``t <= T``).
  • Deduct slippage + commission per leg via ``RiskManager`` cost schedules.
  • Persist every closed trade to SQLite (``trades_memory``) with MAE/MFE,
    regime snapshot, active signals, exit reason.
  • Return a list of closed-trade dicts plus an equity curve for the analyzer.

Determinism: same strategy + same data + same params → same result every run.
No randomness, no future leakage.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from trading_engine.config import (
    DB_PATH,
    DEFAULT_SLIPPAGE_BP,
)
from trading_engine.data.clock import iso_now_utc
from trading_engine.execution.paper_simulator import (
    FillResult,
    PaperPosition,
    PaperSimulator,
)
from trading_engine.memory.trade_logger import TradeLogger
from trading_engine.risk.risk_manager import RiskManager
from trading_engine.strategies.base_strategy import BaseStrategy


@dataclass
class BacktestResult:
    """Outcome of a single backtest run."""

    strategy_id: str
    symbol: str
    timeframe: str
    execution_mode: str = "BACKTEST"

    # Closed trades (dicts with net_pnl, r_multiple, mae/mfe, exit_reason, etc.)
    closed_trades: list[dict[str, Any]] = field(default_factory=list)
    # Equity snapshots (timestamp_utc, equity) — one per processed bar.
    equity_curve: list[tuple[str, float]] = field(default_factory=list)

    # Summary metrics (populated by ``.summary()``).
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    total_net_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    expectancy_r: float = 0.0
    account_equity: float = 0.0
    total_slippage_paid: float = 0.0
    total_commission_paid: float = 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "execution_mode": self.execution_mode,
            "total_trades": self.total_trades,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "win_rate_pct": self.win_rate_pct,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "total_net_pnl": self.total_net_pnl,
            "max_drawdown_pct": self.max_drawdown_pct,
            "expectancy_r": self.expectancy_r,
            "account_equity": self.account_equity,
            "total_slippage_paid": self.total_slippage_paid,
            "total_commission_paid": self.total_commission_paid,
        }


class Backtester:
    """Replay historical bars through a strategy and record trade logs.

    The backtester mirrors ``PaperSimulator`` semantics (entry at current bar
    close, exits evaluated on current bar high/low/close) but is re-entrant
    and returns results instead of mutating a long-lived simulator. Each
    ``run()`` opens its own ``TradeLogger`` / ``RiskManager`` so runs are
    isolated and deterministic.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        *,
        account_equity: float = 10000.0,
        slippage_bp: float = DEFAULT_SLIPPAGE_BP,
        db_path: str = DB_PATH,
        execution_mode: str = "BACKTEST",
    ) -> None:
        self.strategy = strategy
        self.account_equity = account_equity
        self.slippage_bp = slippage_bp
        self.db_path = db_path
        self.execution_mode = execution_mode

        # Fresh risk + logger per run so repeated calls are deterministic.
        self.risk = RiskManager(account_equity=account_equity)
        self.logger = TradeLogger(db_path=db_path)

        self.positions: dict[str, PaperPosition] = {}
        self.closed_trades: list[dict[str, Any]] = []
        self.equity_curve: list[tuple[str, float]] = []

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def run(
        self,
        df_features: Any,
        *,
        start_idx: int = 0,
        end_idx: int | None = None,
    ) -> BacktestResult:
        """Replay ``df_features`` from ``start_idx`` to ``end_idx`` (exclusive).

        Args:
            df_features: Feature DataFrame (one row per bar). Only bars up to
                the current index are visible to the strategy (zero look-ahead).
            start_idx: First bar index to process (inclusive).
            end_idx: Last bar index to process (exclusive). Defaults to
                ``len(df_features)``.

        Returns:
            A populated ``BacktestResult``.
        """
        if end_idx is None:
            end_idx = len(df_features)
        if start_idx < 0 or end_idx > len(df_features) or start_idx >= end_idx:
            raise ValueError(
                f"Invalid range [{start_idx}, {end_idx}) for df of length "
                f"{len(df_features)}"
            )

        self._reset_state()

        strategy_id = self.strategy.strategy_id
        symbol = ""
        timeframe = ""

        for i in range(start_idx, end_idx):
            row = df_features.iloc[i]
            current_time_utc = self._bar_timestamp(row)

            symbol = str(getattr(row, "symbol", "") or symbol or "UNKNOWN")
            timeframe = str(getattr(row, "timeframe", "") or timeframe or "1m")

            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])

            # 1. Update MAE/MFE for open positions (current bar only, t <= T).
            for pos in self.positions.values():
                pos.update_excursion(high, low)

            # 2. Check exits for every open position.
            for trade_id in list(self.positions.keys()):
                pos = self.positions[trade_id]
                result = self._check_exits(pos, high, low, close, current_time_utc)
                if result.action != "HOLD":
                    self._finalize_close(pos, result)
                    del self.positions[trade_id]

            # 3. Evaluate strategy for a new signal (if not halted).
            if not self.risk.is_halted:
                signal = self.strategy.evaluate(df_features, i)
                if signal is not None:
                    result = self._open_position(signal, row, close, current_time_utc)
                    if result is not None:
                        self.positions[result.trade_id] = (
                            self._position_from_signal(signal, result, row)
                        )

            # 4. Record equity snapshot (cash + unrealized at close).
            self._record_equity(close, current_time_utc)

        # Close any positions still open at the end of the range at the last
        # bar's close (flat close — no look-ahead beyond the final bar).
        if self.positions and end_idx > 0:
            last_row = df_features.iloc[end_idx - 1]
            last_close = float(last_row["close"])
            last_time = self._bar_timestamp(last_row)
            for trade_id in list(self.positions.keys()):
                pos = self.positions[trade_id]
                result = self._build_close_result(
                    pos, last_close, "TIME_EXIT",
                    float(last_row["high"]), float(last_row["low"]), last_close,
                    last_time,
                )
                self._finalize_close(pos, result)
                del self.positions[trade_id]

        return self._build_result(strategy_id, symbol, timeframe)

    # ------------------------------------------------------------------ #
    # Internal: position lifecycle                                       #
    # ------------------------------------------------------------------ #
    def _reset_state(self) -> None:
        self.risk = RiskManager(account_equity=self.account_equity)
        self.logger = TradeLogger(db_path=self.db_path)
        self.positions = {}
        self.closed_trades = []
        self.equity_curve = []

    def _bar_timestamp(self, row: Any) -> str:
        ts = getattr(row, "name", None) or getattr(row, "timestamp_utc", None)
        if ts is None:
            return iso_now_utc()
        if isinstance(ts, str):
            return ts
        try:
            return ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        except AttributeError:
            return str(ts)

    def _open_position(
        self,
        signal: dict[str, Any],
        row: Any,
        close: float,
        current_time_utc: str,
    ) -> FillResult | None:
        direction = signal["direction"]
        entry_price = float(signal["entry_price"])
        stop_loss = float(signal["stop_loss_raw"])
        target_1 = float(signal["target_1_raw"])
        target_2 = float(signal["target_2_raw"])

        check = self.risk.can_open_trade(direction)
        if not check.allowed:
            return None
        if not self.risk.validate_rr(entry_price, stop_loss, target_1, direction):
            return None

        position_size, _, _ = self.risk.size_position(
            entry_price, stop_loss, direction
        )
        if position_size <= 0:
            return None

        # Entry slippage + commission.
        notional = entry_price * position_size
        slippage = self.risk.slippage_cost(notional, self.slippage_bp)
        commission = self.risk.commission_cost(notional)
        self.risk.record_costs(slippage, commission)
        self.account_equity -= slippage + commission

        trade_id = self.logger.open_trade(
            strategy_id=signal["strategy_id"],
            execution_mode=self.execution_mode,
            symbol=signal["symbol"],
            timeframe=signal["timeframe"],
            direction=direction,
            entry_time_utc=current_time_utc,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1_price=target_1,
            target_2_price=target_2,
            position_size=position_size,
            regime_snapshot=signal.get("regime_snapshot", {}),
            active_signals=signal.get("active_signals", []),
            notes=f"Backtest open via {signal['strategy_id']}",
        )

        return FillResult(
            trade_id=trade_id, action="OPENED",
            net_pnl=-(slippage + commission),
            r_multiple=0.0,
            exit_reason="",
            exit_price=entry_price,
            exit_time_utc=current_time_utc,
        )

    def _position_from_signal(
        self,
        signal: dict[str, Any],
        fill: FillResult,
        row: Any,
    ) -> PaperPosition:
        return PaperPosition(
            trade_id=fill.trade_id,
            strategy_id=signal["strategy_id"],
            symbol=signal["symbol"],
            timeframe=signal["timeframe"],
            direction=signal["direction"],
            entry_price=float(signal["entry_price"]),
            stop_loss=float(signal["stop_loss_raw"]),
            target_1=float(signal["target_1_raw"]),
            target_2=float(signal["target_2_raw"]),
            position_size=self.risk.size_position(
                float(signal["entry_price"]),
                float(signal["stop_loss_raw"]),
                signal["direction"],
            )[0],
            entry_time_utc=fill.exit_time_utc,
            active_signals=list(signal.get("active_signals", [])),
            regime_snapshot=dict(signal.get("regime_snapshot", {})),
        )

    def _check_exits(
        self,
        pos: PaperPosition,
        high: float,
        low: float,
        close: float,
        current_time_utc: str,
    ) -> FillResult:
        if pos.direction == "LONG":
            if low <= pos.stop_loss:
                return self._build_close_result(pos, pos.stop_loss, "STOP_LOSS",
                                                high, low, close, current_time_utc)
            if high >= pos.target_2:
                return self._build_close_result(pos, pos.target_2, "TAKE_PROFIT",
                                                high, low, close, current_time_utc)
            if high >= pos.target_1:
                return self._build_close_result(pos, pos.target_1, "TAKE_PROFIT",
                                                high, low, close, current_time_utc)
        else:  # SHORT
            if high >= pos.stop_loss:
                return self._build_close_result(pos, pos.stop_loss, "STOP_LOSS",
                                                high, low, close, current_time_utc)
            if low <= pos.target_2:
                return self._build_close_result(pos, pos.target_2, "TAKE_PROFIT",
                                                high, low, close, current_time_utc)
            if low <= pos.target_1:
                return self._build_close_result(pos, pos.target_1, "TAKE_PROFIT",
                                                high, low, close, current_time_utc)
        return FillResult(trade_id=pos.trade_id, action="HOLD",
                          exit_time_utc=current_time_utc)

    def _build_close_result(
        self,
        pos: PaperPosition,
        exit_price: float,
        exit_reason: str,
        high: float,
        low: float,
        close: float,
        current_time_utc: str,
    ) -> FillResult:
        notional = exit_price * pos.position_size
        slippage = self.risk.slippage_cost(notional, self.slippage_bp)
        commission = self.risk.commission_cost(notional)
        self.risk.record_costs(slippage, commission)

        if pos.direction == "LONG":
            gross_pnl = (exit_price - pos.entry_price) * pos.position_size
        else:
            gross_pnl = (pos.entry_price - exit_price) * pos.position_size

        net_pnl = gross_pnl - slippage - commission
        risk = abs(pos.entry_price - pos.stop_loss)
        r_multiple = (
            net_pnl / (risk * pos.position_size) if (risk * pos.position_size) > 0 else 0.0
        )

        self.account_equity += net_pnl

        self.logger.close_trade(
            pos.trade_id,
            exit_time_utc=current_time_utc,
            exit_price=exit_price,
            slippage_cost=slippage,
            commission_cost=commission,
            exit_reason=exit_reason,
        )

        return FillResult(
            trade_id=pos.trade_id, action=f"CLOSED_{exit_reason}",
            net_pnl=net_pnl, r_multiple=r_multiple,
            exit_reason=exit_reason, exit_price=exit_price,
            exit_time_utc=current_time_utc,
        )

    def _finalize_close(self, pos: PaperPosition, result: FillResult) -> None:
        self.closed_trades.append({
            "trade_id": pos.trade_id,
            "strategy_id": pos.strategy_id,
            "symbol": pos.symbol,
            "timeframe": pos.timeframe,
            "direction": pos.direction,
            "net_pnl": result.net_pnl,
            "r_multiple": result.r_multiple,
            "exit_reason": result.exit_reason,
            "exit_price": result.exit_price,
            "entry_price": pos.entry_price,
            "exit_time_utc": result.exit_time_utc,
            "mae_pct": pos.mae_pct,
            "mae_r": pos.mae_r,
            "mfe_pct": pos.mfe_pct,
            "mfe_r": pos.mfe_r,
            "regime_snapshot": pos.regime_snapshot,
            "active_signals": pos.active_signals,
        })

    # ------------------------------------------------------------------ #
    # Equity & result assembly                                           #
    # ------------------------------------------------------------------ #
    def _record_equity(self, price: float, current_time_utc: str) -> None:
        unrealized = 0.0
        for pos in self.positions.values():
            if pos.direction == "LONG":
                unrealized += (price - pos.entry_price) * pos.position_size
            else:
                unrealized += (pos.entry_price - price) * pos.position_size
        self.equity_curve.append((current_time_utc, self.account_equity + unrealized))

    def _build_result(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str,
    ) -> BacktestResult:
        closed = self.closed_trades
        wins = [t for t in closed if t.get("net_pnl", 0) > 0]
        losses = [t for t in closed if t.get("net_pnl", 0) < 0]
        gross_profit = sum(t.get("net_pnl", 0) for t in wins)
        gross_loss = abs(sum(t.get("net_pnl", 0) for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        total_net_pnl = sum(t.get("net_pnl", 0) for t in closed)

        # Max drawdown from equity curve.
        peak = 0.0
        max_dd_pct = 0.0
        for _, equity in self.equity_curve:
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak * 100.0
                if dd > max_dd_pct:
                    max_dd_pct = dd

        # Expectancy in R.
        r_vals = [t.get("r_multiple", 0.0) for t in closed if t.get("r_multiple") is not None]
        expectancy_r = (sum(r_vals) / len(r_vals)) if r_vals else 0.0

        win_rate_pct = (len(wins) / len(closed) * 100.0) if closed else 0.0

        return BacktestResult(
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            execution_mode=self.execution_mode,
            closed_trades=closed,
            equity_curve=self.equity_curve,
            total_trades=len(closed),
            win_count=len(wins),
            loss_count=len(losses),
            win_rate_pct=win_rate_pct,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            total_net_pnl=total_net_pnl,
            max_drawdown_pct=max_dd_pct,
            expectancy_r=expectancy_r,
            account_equity=self.account_equity,
            total_slippage_paid=self.risk.totals["total_slippage_paid"],
            total_commission_paid=self.risk.totals["total_commission_paid"],
        )
