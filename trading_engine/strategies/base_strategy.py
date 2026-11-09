"""strategies/base_strategy.py — Abstract BaseStrategy interface (Layer 2B).

Every strategy (baseline V1 or AI-generated candidate V2) inherits from
``BaseStrategy`` and defines its metadata, tunable parameters (for the
Parameter Sensitivity Heatmap in Phase 4), and an ``evaluate()`` rule that
combines indicator signals into a trade trigger.

Contract (database_and_data_contracts.md Section 2, Contract A):
  evaluate() returns either ``None`` (no trade) or a dict with:
    strategy_id, symbol, timeframe, timestamp_utc, direction,
    entry_price, stop_loss_raw, target_1_raw, target_2_raw,
    active_signals (list[str]), regime_snapshot (dict).

Zero look-ahead: ``evaluate()`` reads only ``df_features.iloc[:current_idx+1]``
and signal wrappers read only the current/previous row — never future bars.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


class BaseStrategy(ABC):
    """Abstract interface all versioned strategy recipes must implement."""

    # ------------------------------------------------------------------ #
    # Strategy metadata (subclasses override these class attributes)      #
    # ------------------------------------------------------------------ #
    strategy_id: str = "BASE_STRATEGY"
    parent_strategy_id: str | None = None
    paradigm_tags: list[str] = []

    # Tunable parameters automatically tested by the Parameter Sensitivity
    # Heatmap in Phase 4 (validation/gatekeeper.py).
    default_params: dict[str, Any] = {}

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        """Merge caller-supplied params over ``default_params``."""
        self.params: dict[str, Any] = dict(self.default_params)
        if params:
            self.params.update(params)

    # ------------------------------------------------------------------ #
    # Core evaluation hook                                                #
    # ------------------------------------------------------------------ #
    @abstractmethod
    def evaluate(self, df_features: Any, current_idx: int) -> dict[str, Any] | None:
        """Inspect features up to ``current_idx`` and return a trade signal or ``None``.

        Args:
            df_features: DataFrame of pre-computed indicator features (one row
                per bar, zero-look-ahead guarantee enforced upstream).
            current_idx: Integer position of the current bar being evaluated.

        Returns:
            A signal dict matching Contract A, or ``None`` when no trade is
            triggered on this bar.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Shared signal builder                                               #
    # ------------------------------------------------------------------ #
    def build_signal(
        self,
        row: Any,
        *,
        direction: str,
        entry_price: float,
        stop_loss_raw: float,
        target_1_raw: float,
        target_2_raw: float | None = None,
        active_signals: list[str] | None = None,
        regime_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble the Contract A signal dictionary.

        All prices are read from ``row`` / the caller (current bar only — no
        future data). ``target_2_raw`` defaults to ``target_1_raw`` when
        omitted so downstream paper/risk code always has two targets.
        """
        active_signals = active_signals or []
        regime_snapshot = regime_snapshot or {}
        ts = self._current_timestamp(row)

        return {
            "strategy_id": self.strategy_id,
            "symbol": str(getattr(row, "symbol", "") or ""),
            "timeframe": str(getattr(row, "timeframe", "") or ""),
            "timestamp_utc": ts,
            "direction": direction,
            "entry_price": float(entry_price),
            "stop_loss_raw": float(stop_loss_raw),
            "target_1_raw": float(target_1_raw),
            "target_2_raw": float(target_2_raw if target_2_raw is not None else target_1_raw),
            "active_signals": list(active_signals),
            "regime_snapshot": dict(regime_snapshot),
        }

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _current_timestamp(row: Any) -> str:
        """Best-effort ISO-8601 UTC timestamp from the feature row."""
        ts = getattr(row, "name", None) or getattr(row, "timestamp_utc", None)
        if ts is None:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if isinstance(ts, str):
            return ts
        # pandas Timestamp / datetime
        try:
            return ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        except AttributeError:
            return str(ts)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"{self.__class__.__name__}({self.strategy_id})"
