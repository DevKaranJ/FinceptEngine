"""trading_engine.strategies.approved — Active validated baseline strategies (V1)."""

from trading_engine.strategies.approved.baseline_demonstration_strategy import (
    BaselineDemonstrationStrategy,
)
from trading_engine.strategies.approved.ema_breakout_v1 import EmaBreakoutV1
from trading_engine.strategies.approved.vwap_fvg_v1 import VwapFvgV1

__all__ = [
    "BaselineDemonstrationStrategy",
    "EmaBreakoutV1",
    "VwapFvgV1",
]
