"""risk/risk_manager.py — Universal Risk & Position Sizing (Layer 2C).

Enforces non-negotiable capital and risk rules across all strategies regardless
of indicator type. Reads fee/slippage schedules and risk constants from
``config.py`` (single source of truth).

Responsibilities (PRD Phase 3 / master_architecture Section 2):
  • Position sizing from account equity & max risk % per trade
  • ATR-based stop-loss buffer placement
  • Slippage & commission cost deduction per leg
  • Daily loss circuit breaker (halt after N% daily loss)
  • Max consecutive-loss circuit breaker (halt after N straight losses)
  • Max drawdown kill-switch
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trading_engine.config import (
    ATR_STOP_BUFFER_MULTIPLIER,
    BINANCE_SPOT_TAKER_BP,
    BINANCE_SPOT_MAKER_BP,
    DAILY_LOSS_CIRCUIT_BREAKER_PCT,
    DEFAULT_SLIPPAGE_BP,
    MAX_CONSECUTIVE_LOSSES,
    MAX_RISK_PER_TRADE_PCT,
    MIN_RISK_REWARD_RATIO,
)


@dataclass
class RiskCheck:
    """Result of a risk validation pass/fail."""

    allowed: bool
    reason: str
    position_size: float = 0.0
    risk_amount: float = 0.0
    stop_loss: float = 0.0
    slippage_cost: float = 0.0
    commission_cost: float = 0.0
    halted: bool = False
    halt_reason: str = ""


@dataclass
class DailyRiskState:
    """Running daily risk tally (reset at session boundary)."""

    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    equity_peak: float = 0.0
    max_drawdown_pct: float = 0.0
    trades_today: int = 0
    halted: bool = False
    halt_reason: str = ""

    def record_trade_pnl(self, pnl: float, equity: float) -> None:
        """Update daily PnL, consecutive-loss streak, and drawdown."""
        self.trades_today += 1
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if equity > self.equity_peak:
            self.equity_peak = equity
        dd = (self.equity_peak - equity) / self.equity_peak * 100.0 if self.equity_peak else 0.0
        self.max_drawdown_pct = max(self.max_drawdown_pct, dd)


class RiskManager:
    """Universal risk governance for every strategy."""

    def __init__(
        self,
        account_equity: float,
        *,
        max_risk_per_trade_pct: float = MAX_RISK_PER_TRADE_PCT,
        daily_loss_circuit_breaker_pct: float = DAILY_LOSS_CIRCUIT_BREAKER_PCT,
        max_consecutive_losses: int = MAX_CONSECUTIVE_LOSSES,
        atr_stop_buffer_multiplier: float = ATR_STOP_BUFFER_MULTIPLIER,
        min_risk_reward_ratio: float = MIN_RISK_REWARD_RATIO,
        default_slippage_bp: float = DEFAULT_SLIPPAGE_BP,
        taker_bp: float = BINANCE_SPOT_TAKER_BP,
        maker_bp: float = BINANCE_SPOT_MAKER_BP,
    ) -> None:
        self.account_equity = account_equity
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.daily_loss_circuit_breaker_pct = daily_loss_circuit_breaker_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.atr_stop_buffer_multiplier = atr_stop_buffer_multiplier
        self.min_risk_reward_ratio = min_risk_reward_ratio
        self.default_slippage_bp = default_slippage_bp
        self.taker_bp = taker_bp
        self.maker_bp = maker_bp

        self.daily = DailyRiskState()
        self._total_commission_paid = 0.0
        self._total_slippage_paid = 0.0

    # ------------------------------------------------------------------ #
    # Position sizing                                                     #
    # ------------------------------------------------------------------ #
    def size_position(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str = "LONG",
    ) -> tuple[float, float, float]:
        """Return ``(position_size, risk_amount, risk_per_share)``.

        Risk per share = |entry - stop|. Position size caps risk at
        ``max_risk_per_trade_pct`` of account equity.
        """
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            return 0.0, 0.0, 0.0

        max_risk_dollars = self.account_equity * (self.max_risk_per_trade_pct / 100.0)
        position_size = max_risk_dollars / risk_per_share
        risk_amount = position_size * risk_per_share
        return position_size, risk_amount, risk_per_share

    def atr_stop(
        self,
        entry_price: float,
        atr: float,
        direction: str = "LONG",
    ) -> float:
        """ATR-buffered stop price.

        LONG: entry - (ATR_STOP_BUFFER_MULTIPLIER * ATR)
        SHORT: entry + (ATR_STOP_BUFFER_MULTIPLIER * ATR)
        """
        buffer = self.atr_stop_buffer_multiplier * atr
        if direction == "LONG":
            return entry_price - buffer
        return entry_price + buffer

    # ------------------------------------------------------------------ #
    # Trade validation (circuit breakers + R:R)                          #
    # ------------------------------------------------------------------ #
    def can_open_trade(self, direction: str = "LONG") -> RiskCheck:
        """Decide whether a new trade may be opened right now.

        Checks (in order): daily loss circuit breaker, consecutive-loss
        breaker, max drawdown kill-switch, minimum R:R feasibility.
        """
        # Daily loss circuit breaker
        if self.daily.daily_pnl <= -abs(self.daily_loss_circuit_breaker_pct / 100.0 * self.account_equity):
            return RiskCheck(False, "DAILY_LOSS_CIRCUIT_BREAKER", halted=True)

        # Consecutive-loss circuit breaker
        if self.daily.consecutive_losses >= self.max_consecutive_losses:
            return RiskCheck(False, "MAX_CONSECUTIVE_LOSSES", halted=True)

        # Max drawdown kill-switch
        if self.daily.max_drawdown_pct >= self.daily_loss_circuit_breaker_pct:
            return RiskCheck(False, "MAX_DRAWDOWN_KILL_SWITCH", halted=True)

        return RiskCheck(True, "OK")

    def validate_rr(self, entry_price: float, stop_loss: float,
                    target_1: float, direction: str = "LONG") -> bool:
        """True if the setup meets MIN_RISK_REWARD_RATIO."""
        risk = abs(entry_price - stop_loss)
        if risk <= 0:
            return False
        reward = abs(target_1 - entry_price)
        return (reward / risk) >= self.min_risk_reward_ratio

    # ------------------------------------------------------------------ #
    # Execution costs                                                     #
    # ------------------------------------------------------------------ #
    def slippage_cost(self, notional: float, bp: float | None = None) -> float:
        bp = self.default_slippage_bp if bp is None else bp
        return notional * (bp / 10000.0)

    def commission_cost(self, notional: float, taker: bool = True) -> float:
        bp = self.taker_bp if taker else self.maker_bp
        return notional * (bp / 10000.0)

    def record_costs(self, slippage: float, commission: float) -> None:
        self._total_slippage_paid += slippage
        self._total_commission_paid += commission

    # ------------------------------------------------------------------ #
    # Trade outcome bookkeeping                                           #
    # ------------------------------------------------------------------ #
    def close_trade(self, net_pnl: float, equity: float) -> None:
        """Record a closed trade's PnL into daily risk state."""
        self.daily.record_trade_pnl(net_pnl, equity)
        if self.daily.daily_pnl <= -abs(self.daily_loss_circuit_breaker_pct / 100.0 * self.account_equity):
            self.daily.halted = True
            self.daily.halt_reason = "DAILY_LOSS_CIRCUIT_BREAKER"
        elif self.daily.consecutive_losses >= self.max_consecutive_losses:
            self.daily.halted = True
            self.daily.halt_reason = "MAX_CONSECUTIVE_LOSSES"
        elif self.daily.max_drawdown_pct >= self.daily_loss_circuit_breaker_pct:
            self.daily.halted = True
            self.daily.halt_reason = "MAX_DRAWDOWN_KILL_SWITCH"

    @property
    def is_halted(self) -> bool:
        return self.daily.halted

    @property
    def halt_reason(self) -> str:
        return self.daily.halt_reason

    @property
    def totals(self) -> dict[str, float]:
        return {
            "account_equity": self.account_equity,
            "daily_pnl": self.daily.daily_pnl,
            "max_drawdown_pct": self.daily.max_drawdown_pct,
            "consecutive_losses": float(self.daily.consecutive_losses),
            "total_slippage_paid": self._total_slippage_paid,
            "total_commission_paid": self._total_commission_paid,
        }
