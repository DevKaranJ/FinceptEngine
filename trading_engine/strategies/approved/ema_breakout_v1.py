"""strategies/approved/ema_breakout_v1.py — Baseline V1: EMA Breakout (Technical).

Paradigm: Classical Technical Analysis (Trend + Volatility filter).
Signals used (from signals/technical_signals.py):
  • ema_fast_cross_above  — entry trigger (fast EMA crosses above slow EMA)
  • is_ema_bull_trend     — bullish trend alignment filter
  • atr_above_threshold   — volatility expansion filter (avoid low-ATR chop)
  • price_above_hma       — Hull MA bias filter

Risk/stop/target (from config.py):
  • stop  = entry - ATR_STOP_BUFFER_MULTIPLIER * ATR
  • target = entry + (risk * MIN_RISK_REWARD_RATIO)
"""

from __future__ import annotations

from typing import Any

from trading_engine.signals.technical_signals import (
    ema_fast_cross_above,
    is_ema_bull_trend,
    price_above_hma,
)

from trading_engine.strategies.base_strategy import BaseStrategy


class EmaBreakoutV1(BaseStrategy):
    """EMA breakout long strategy with ATR volatility and HMA bias filters.

    Entry (LONG only):
      • fast EMA crosses above slow EMA (trigger)
      • close > fast EMA > slow EMA (bullish trend alignment)
      • ATR expanding vs its SMA (volatility filter)
      • price above HMA (bullish bias)

    Stop: entry - ATR_STOP_BUFFER_MULTIPLIER * ATR(14)
    Target 1: entry + risk * MIN_RISK_REWARD_RATIO
    Target 2: entry + risk * 2.0 * MIN_RISK_REWARD_RATIO
    """

    strategy_id = "EMA_BREAKOUT_V1"
    parent_strategy_id = None
    paradigm_tags = ["TECHNICAL", "TREND", "VOLATILITY_FILTER"]

    default_params = {
        "ema_fast_len": 20,
        "ema_slow_len": 50,
        "atr_len": 14,
        "atr_mult_threshold": 1.15,
        "hma_len": 20,
        "sl_atr_mult": 1.5,
        "tp_rr_ratio": 1.5,
        "tp2_rr_ratio": 3.0,
    }

    def evaluate(self, df_features: Any, current_idx: int) -> dict[str, Any] | None:
        row = df_features.iloc[current_idx]

        # --- Pull pre-computed feature columns (zero look-ahead, current bar only) ---
        close = float(row["close"])
        atr = float(row[f"atr_{self.params['atr_len']}"])

        ema_fast_col = f"ema_{self.params['ema_fast_len']}"
        ema_slow_col = f"ema_{self.params['ema_slow_len']}"
        hma_col = f"hma_{self.params['hma_len']}"

        # --- Filter Gate: ATR volatility expansion (zero look-ahead: SMA over
        #     atr_14 up to and including current bar). ---
        atr_series = df_features[f"atr_{self.params['atr_len']}"].iloc[: current_idx + 1]
        atr_sma = float(atr_series.rolling(window=self.params["atr_len"], min_periods=1).mean().iloc[-1])
        atr_expanding = atr > atr_sma * self.params["atr_mult_threshold"]
        if not atr_expanding:
            return None

        if not is_ema_bull_trend(row, close_col="close",
                                 ema_fast_col=ema_fast_col,
                                 ema_slow_col=ema_slow_col):
            return None
        if not price_above_hma(row, hma_col=hma_col, close_col="close"):
            return None

        # --- Entry Trigger: EMA fast crosses above EMA slow ---
        prev_row = df_features.iloc[current_idx - 1] if current_idx > 0 else None
        if not ema_fast_cross_above(row, ema_fast_col=ema_fast_col,
                                    ema_slow_col=ema_slow_col, prev_row=prev_row):
            return None

        # --- Risk / target levels ---
        risk = self.params["sl_atr_mult"] * atr
        stop_loss = close - risk
        target_1 = close + (risk * self.params["tp_rr_ratio"])
        target_2 = close + (risk * self.params["tp2_rr_ratio"])

        regime_snapshot = {
            "volatility_regime": "EXPANDING_ATR",
            "atr": atr,
            "atr_sma": atr_sma,
            "trend_regime": "BULLISH",
            "hma_len": self.params["hma_len"],
        }

        return self.build_signal(
            row=row,
            direction="LONG",
            entry_price=close,
            stop_loss_raw=stop_loss,
            target_1_raw=target_1,
            target_2_raw=target_2,
            active_signals=["EMA_FAST_CROSS_ABOVE", "EMA_BULL_TREND",
                            "ATR_ABOVE_THRESHOLD", "PRICE_ABOVE_HMA"],
            regime_snapshot=regime_snapshot,
        )
