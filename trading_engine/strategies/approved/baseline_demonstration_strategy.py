"""strategies/approved/baseline_demonstration_strategy.py — Baseline V1 Demonstration Strategy.

Paradigm: Dual Trend & Pullback Momentum (Technical).
Indicators: EMA 20, EMA 50, HMA 20, Donchian Channels 20, ATR 14.
Zero look-ahead: evaluate() reads only features up to current_idx (t <= T).

Conforms strictly to Contract A (database_and_data_contracts.md Section 2).
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from trading_engine.indicators.technical import (
    atr as calc_atr,
    donchian_channels as calc_donchian,
    ema as calc_ema,
    hma as calc_hma,
)
from trading_engine.strategies.base_strategy import BaseStrategy


class BaselineDemonstrationStrategy(BaseStrategy):
    """Institutional baseline demonstration strategy.

    Serves as a robust benchmark and functional placeholder ahead of custom
    strategy uploads. Implements dual trend / pullback logic with ATR stop
    buffers and validated Risk-to-Reward targets.

    Trend Filters:
      • Bullish trend: EMA fast > EMA slow OR Close > EMA slow
      • Bearish trend: EMA fast < EMA slow OR Close < EMA slow

    Entry Triggers:
      • LONG: Bullish trend AND ATR > 0 AND (Cross above HMA 20 OR Break above Donchian Upper OR Pullback bounce off EMA fast)
      • SHORT: Bearish trend AND ATR > 0 AND (Cross below HMA 20 OR Break below Donchian Lower OR Pullback rejection off EMA fast)

    Risk & Exits:
      • Stop Loss: Entry - (1.5 * ATR) [LONG] / Entry + (1.5 * ATR) [SHORT]
      • Target 1: Entry + (1.5 * Risk) [LONG] / Entry - (1.5 * Risk) [SHORT] (R:R = 1.5)
      • Target 2: Entry + (3.0 * Risk) [LONG] / Entry - (3.0 * Risk) [SHORT] (R:R = 3.0)
    """

    strategy_id: str = "BASELINE_DEMO_V1"
    parent_strategy_id: str | None = None
    paradigm_tags: list[str] = ["TECHNICAL", "TREND", "PULLBACK", "BASELINE"]

    default_params: dict[str, Any] = {
        "ema_fast_len": 20,
        "ema_slow_len": 50,
        "hma_len": 20,
        "donchian_len": 20,
        "atr_len": 14,
        "sl_atr_mult": 1.5,
        "tp_rr_ratio": 1.5,
        "tp2_rr_ratio": 3.0,
    }

    def evaluate(self, df_features: Any, current_idx: int) -> dict[str, Any] | None:
        """Evaluate features up to current_idx with zero look-ahead."""
        if current_idx < 1 or len(df_features) <= current_idx:
            return None

        row = df_features.iloc[current_idx]
        prev_row = df_features.iloc[current_idx - 1]

        close = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])

        prev_close = float(prev_row["close"])
        prev_high = float(prev_row["high"])
        prev_low = float(prev_row["low"])

        # Historical slice up to current bar (strictly t <= T)
        hist_slice = df_features.iloc[: current_idx + 1]

        fast_len = int(self.params.get("ema_fast_len", 20))
        slow_len = int(self.params.get("ema_slow_len", 50))
        hma_len = int(self.params.get("hma_len", 20))
        dc_len = int(self.params.get("donchian_len", 20))
        atr_len = int(self.params.get("atr_len", 14))

        # 1. EMA Fast
        fast_col = f"ema_{fast_len}"
        if fast_col in row and not pd.isna(row[fast_col]):
            ema_fast = float(row[fast_col])
            prev_ema_fast = float(prev_row[fast_col]) if fast_col in prev_row and not pd.isna(prev_row[fast_col]) else ema_fast
        elif "ema_20" in row and not pd.isna(row["ema_20"]) and fast_len == 20:
            ema_fast = float(row["ema_20"])
            prev_ema_fast = float(prev_row["ema_20"]) if "ema_20" in prev_row and not pd.isna(prev_row["ema_20"]) else ema_fast
        else:
            if len(hist_slice) < fast_len:
                return None
            ema_s = calc_ema(hist_slice["close"], length=fast_len)
            ema_fast = float(ema_s.iloc[-1])
            prev_ema_fast = float(ema_s.iloc[-2]) if len(ema_s) >= 2 else ema_fast

        # 2. EMA Slow
        slow_col = f"ema_{slow_len}"
        if slow_col in row and not pd.isna(row[slow_col]):
            ema_slow = float(row[slow_col])
        elif "ema_50" in row and not pd.isna(row["ema_50"]) and slow_len == 50:
            ema_slow = float(row["ema_50"])
        else:
            if len(hist_slice) < slow_len:
                return None
            ema_slow = float(calc_ema(hist_slice["close"], length=slow_len).iloc[-1])

        # 3. HMA
        hma_col = f"hma_{hma_len}"
        if hma_col in row and not pd.isna(row[hma_col]):
            hma_val = float(row[hma_col])
            prev_hma_val = float(prev_row[hma_col]) if hma_col in prev_row and not pd.isna(prev_row[hma_col]) else hma_val
        elif "hma_20" in row and not pd.isna(row["hma_20"]) and hma_len == 20:
            hma_val = float(row["hma_20"])
            prev_hma_val = float(prev_row["hma_20"]) if "hma_20" in prev_row and not pd.isna(prev_row["hma_20"]) else hma_val
        else:
            if len(hist_slice) < hma_len:
                return None
            hma_s = calc_hma(hist_slice["close"], length=hma_len)
            hma_val = float(hma_s.iloc[-1])
            prev_hma_val = float(hma_s.iloc[-2]) if len(hma_s) >= 2 else hma_val

        # 4. Donchian Channels
        dc_upper_col = f"donchian_upper_{dc_len}"
        dc_lower_col = f"donchian_lower_{dc_len}"
        if dc_upper_col in row and not pd.isna(row[dc_upper_col]):
            dc_upper = float(row[dc_upper_col])
            dc_lower = float(row[dc_lower_col])
            prev_dc_upper = float(prev_row[dc_upper_col]) if dc_upper_col in prev_row and not pd.isna(prev_row[dc_upper_col]) else dc_upper
            prev_dc_lower = float(prev_row[dc_lower_col]) if dc_lower_col in prev_row and not pd.isna(prev_row[dc_lower_col]) else dc_lower
        elif "donchian_upper_20" in row and not pd.isna(row["donchian_upper_20"]) and dc_len == 20:
            dc_upper = float(row["donchian_upper_20"])
            dc_lower = float(row["donchian_lower_20"])
            prev_dc_upper = float(prev_row["donchian_upper_20"]) if "donchian_upper_20" in prev_row and not pd.isna(prev_row["donchian_upper_20"]) else dc_upper
            prev_dc_lower = float(prev_row["donchian_lower_20"]) if "donchian_lower_20" in prev_row and not pd.isna(prev_row["donchian_lower_20"]) else dc_lower
        else:
            if len(hist_slice) < dc_len:
                return None
            dc_res = calc_donchian(hist_slice["high"], hist_slice["low"], length=dc_len)
            dc_upper = float(dc_res["upper"].iloc[-1])
            dc_lower = float(dc_res["lower"].iloc[-1])
            prev_dc_upper = float(dc_res["upper"].iloc[-2]) if len(dc_res["upper"]) >= 2 else dc_upper
            prev_dc_lower = float(dc_res["lower"].iloc[-2]) if len(dc_res["lower"]) >= 2 else dc_lower

        # 5. ATR
        atr_col = f"atr_{atr_len}"
        if atr_col in row and not pd.isna(row[atr_col]):
            atr_val = float(row[atr_col])
        elif "atr_14" in row and not pd.isna(row["atr_14"]) and atr_len == 14:
            atr_val = float(row["atr_14"])
        else:
            if len(hist_slice) < atr_len:
                return None
            atr_val = float(calc_atr(hist_slice["high"], hist_slice["low"], hist_slice["close"], length=atr_len).iloc[-1])

        # Validate non-NaN
        for v in (ema_fast, ema_slow, hma_val, dc_upper, dc_lower, atr_val):
            if math.isnan(v):
                return None

        if atr_val <= 0:
            return None

        # --- Dual Trend / Pullback Evaluation ---
        bull_trend = (ema_fast > ema_slow) or (close > ema_slow)
        bear_trend = (ema_fast < ema_slow) or (close < ema_slow)

        # Triggers LONG
        long_hma_cross = (prev_close <= prev_hma_val) and (close > hma_val)
        long_dc_breakout = (prev_high <= prev_dc_upper and high > prev_dc_upper) or (close > prev_dc_upper)
        long_pullback_bounce = (prev_close <= prev_ema_fast) and (close > ema_fast)
        trigger_long = long_hma_cross or long_dc_breakout or long_pullback_bounce

        # Triggers SHORT
        short_hma_cross = (prev_close >= prev_hma_val) and (close < hma_val)
        short_dc_breakout = (prev_low >= prev_dc_lower and low < prev_dc_lower) or (close < prev_dc_lower)
        short_pullback_rejection = (prev_close >= prev_ema_fast) and (close < ema_fast)
        trigger_short = short_hma_cross or short_dc_breakout or short_pullback_rejection

        direction: str | None = None
        active_signals: list[str] = []

        if bull_trend and trigger_long:
            direction = "LONG"
            active_signals.append("BULLISH_TREND")
            if long_hma_cross:
                active_signals.append("HMA_CROSS_ABOVE")
            if long_dc_breakout:
                active_signals.append("DONCHIAN_BREAKOUT_UP")
            if long_pullback_bounce:
                active_signals.append("EMA_PULLBACK_BOUNCE")
        elif bear_trend and trigger_short:
            direction = "SHORT"
            active_signals.append("BEARISH_TREND")
            if short_hma_cross:
                active_signals.append("HMA_CROSS_BELOW")
            if short_dc_breakout:
                active_signals.append("DONCHIAN_BREAKOUT_DOWN")
            if short_pullback_rejection:
                active_signals.append("EMA_PULLBACK_REJECTION")

        if direction is None:
            return None

        sl_mult = float(self.params.get("sl_atr_mult", 1.5))
        tp_mult = float(self.params.get("tp_rr_ratio", 1.5))
        tp2_mult = float(self.params.get("tp2_rr_ratio", 3.0))

        risk_dist = sl_mult * atr_val
        if risk_dist <= 0:
            return None

        if direction == "LONG":
            entry_price = close
            stop_loss = entry_price - risk_dist
            if stop_loss <= 0:
                stop_loss = entry_price * 0.5
                risk_dist = entry_price - stop_loss
            target_1 = entry_price + (risk_dist * tp_mult)
            target_2 = entry_price + (risk_dist * tp2_mult)
        else:
            entry_price = close
            stop_loss = entry_price + risk_dist
            target_1 = entry_price - (risk_dist * tp_mult)
            target_2 = entry_price - (risk_dist * tp2_mult)
            if target_1 <= 0:
                target_1 = entry_price * 0.5
            if target_2 <= 0:
                target_2 = entry_price * 0.25

        regime_snapshot = {
            "volatility_regime": "NORMAL_ATR" if atr_val > 0 else "LOW_ATR",
            "trend_regime": "BULLISH" if direction == "LONG" else "BEARISH",
            "atr": atr_val,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "hma": hma_val,
            "donchian_upper": dc_upper,
            "donchian_lower": dc_lower,
        }

        return self.build_signal(
            row=row,
            direction=direction,
            entry_price=entry_price,
            stop_loss_raw=stop_loss,
            target_1_raw=target_1,
            target_2_raw=target_2,
            active_signals=active_signals,
            regime_snapshot=regime_snapshot,
        )
