"""strategies/approved/vwap_fvg_v1.py — Baseline V1: VWAP + Fair Value Gap (Orderflow + Structure).

Paradigm: Hybrid Orderflow + Price Structure (Mean Reversion at value).
Signals used:
  • above_vwap           — price above session VWAP (long bias)
  • price_in_value_area  — price inside session Value Area (VAL..VAH)
  • fvg_retest_bull      — price retraces into an unfilled bullish FVG (entry trigger)
  • ob_test_bull         — price tests an unmitigated bullish Order Block (confirmation)

Risk/stop/target:
  • stop  = max(entry - ATR_STOP_BUFFER_MULTIPLIER * ATR, FVG bottom)
  • target = entry + risk * MIN_RISK_REWARD_RATIO
"""

from __future__ import annotations

from typing import Any

from trading_engine.signals.orderflow_signals import above_vwap, price_in_value_area
from trading_engine.signals.structure_signals import fvg_retest_bull, ob_test_bull

from trading_engine.strategies.base_strategy import BaseStrategy


class VwapFvgV1(BaseStrategy):
    """VWAP + FVG mean-reversion long strategy.

    Entry (LONG only):
      • close >= VWAP (above value)
      • close inside session Value Area (VAL <= close <= VAH)
      • price retraces into an unfilled bullish FVG (trigger)
      • price also tests an unmitigated bullish Order Block (confirmation)

    Stop: entry - ATR_STOP_BUFFER_MULTIPLIER * ATR(14), floored at FVG bottom.
    Target 1: entry + risk * MIN_RISK_REWARD_RATIO
    Target 2: entry + risk * 2.0 * MIN_RISK_REWARD_RATIO
    """

    strategy_id = "VWAP_FVG_V1"
    parent_strategy_id = None
    paradigm_tags = ["ORDERFLOW", "STRUCTURE", "MEAN_REVERSION"]

    default_params = {
        "atr_len": 14,
        "atr_mult_threshold": 1.15,
        "sl_atr_mult": 1.5,
        "tp_rr_ratio": 1.5,
        "tp2_rr_ratio": 3.0,
    }

    def evaluate(self, df_features: Any, current_idx: int) -> dict[str, Any] | None:
        row = df_features.iloc[current_idx]

        close = float(row["close"])
        atr = float(row[f"atr_{self.params['atr_len']}"])

        # --- Filter Gate ---
        if not above_vwap(row, close_col="close", vwap_col="vwap"):
            return None
        if not price_in_value_area(row, close_col="close", vah_col="vah", val_col="val"):
            return None

        # --- Entry Trigger: bullish FVG retest ---
        if not fvg_retest_bull(row, close_col="close",
                               fvg_bull_top_col="fvg_bull_top",
                               fvg_bull_bottom_col="fvg_bull_bottom",
                               fvg_bull_active_col="fvg_bull_active"):
            return None

        # --- Confirmation: bullish Order Block test ---
        if not ob_test_bull(row, close_col="close",
                            ob_bull_top_col="ob_bull_top",
                            ob_bull_bottom_col="ob_bull_bottom",
                            ob_bull_active_col="ob_bull_active"):
            return None

        # --- Risk / target levels ---
        risk = self.params["sl_atr_mult"] * atr
        fvg_bottom = float(row["fvg_bull_bottom"])
        stop_loss = min(close - risk, fvg_bottom)
        target_1 = close + (risk * self.params["tp_rr_ratio"])
        target_2 = close + (risk * self.params["tp2_rr_ratio"])

        regime_snapshot = {
            "volatility_regime": "NORMAL_ATR",
            "atr": atr,
            "vwap": float(row["vwap"]),
            "vah": float(row["vah"]),
            "val": float(row["val"]),
            "trend_regime": "MEAN_REVERSION",
        }

        return self.build_signal(
            row=row,
            direction="LONG",
            entry_price=close,
            stop_loss_raw=stop_loss,
            target_1_raw=target_1,
            target_2_raw=target_2,
            active_signals=["ABOVE_VWAP", "PRICE_IN_VALUE_AREA",
                            "FVG_RETEST_BULL", "OB_TEST_BULL"],
            regime_snapshot=regime_snapshot,
        )
