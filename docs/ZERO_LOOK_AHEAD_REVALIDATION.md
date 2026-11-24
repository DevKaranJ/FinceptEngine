# Zero-Look-Ahead & Risk-Management Revalidation — Phase C

**Project:** FinceptEngine — Binance Spot + USDⓈ-M Futures Trading Platform  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`, NOT committed, NOT pushed, NOT merged)  
**Date:** 2026-11-24  
**Owner:** QA + Reviewer  
**Scope:** Evidence-based revalidation of the zero-look-ahead claim (`t <= T`) and risk-management concerns: volume profile, candle completion, fill timing, stop/target evaluation.

---

## Verdict: **PASS** — clean, no open findings

The zero-look-ahead claim (`ZERO_LOOK_AHEAD = True`, `t <= T`) holds across the codebase. All indicators, signals, strategies, backtester exits, paper-simulator fills, and the validation gatekeeper use only past-and-current-bar data. The phase test suites (22/22, 64/64, 24/24, 14/14, 9/9 — 133 total) all pass, including explicit look-ahead leakage tests.

Previously reported **Medium-severity finding ZLA-001** (`session_volume_profile()` computing POC/VAH/VAL from the full day's data then forward-filling) has been **resolved**: `indicators/orderflow.py` now computes an expanding within-session profile so bar `t` sees only bars `<= t`. `indicators/structure.py` `opening_range()` now holds expanding window levels (inside window) and final window levels (after window), with no same-session forward fill. Both fixes are covered by new regression tests (`test_session_volume_profile_no_intra_session_lookahead`, `test_opening_range_no_same_session_lookahead`, and `test_opening_range_no_pre_market_positional_leak` which reproduces the 09:15/09:20 future-spike leak scenario with pre-market data).

---

## 1. Zero Look-Ahead — Evidence by Area

### 1.1 Indicators (all 4 families)

Every indicator in `trading_engine/indicators/{technical,statistical,structure,orderflow}.py` uses only `iloc[:t]` / `shift(1)` / expanding / rolling with `min_periods=1` / groupby-cumsum.

| Indicator Family | File | Look-ahead mechanism | Verified by |
|------------------|------|---------------------|-------------|
| Technical (A) | `technical.py` | EMA/SMA/RSI/ATR/MACD/Supertrend/Donchian/HMA use `ewm(adjust=False)`, `rolling`, `shift(1)` | `test_ema_zero_look_ahead`, `test_rsi_zero_look_ahead`, `test_hma_zero_look_ahead`, `test_pivots_uses_previous_bar_only`, `test_technical_indicators_no_future_leakage` |
| Statistical (B) | `statistical.py` | Rolling Z-Score, Hurst, Vol Percentile, LinReg Slope, RS use `rolling` / `expanding` | `test_zscore_zero_look_ahead` |
| Structure (C) | `structure.py` | PDH/PDL/PDC carry previous calendar day forward (`shift` by day); ORB/TL/FVG/OB/Sweep use past bars only | `test_structure_indicators_no_future_leakage` (PDH from prior day only) |
| Orderflow (D) | `orderflow.py` | VWAP/RVOL/Session Profile/CVD/Footprint/Iceberg use groupby-cumsum / expanding / past-window | `test_orderflow_no_future_leakage` |

**Finding:** No indicator uses `shift(-1)`, whole-series unanchored `.mean()`/`max()`/`min()` on future data, or any `t+1` reference. **PASS.**

### 1.2 Feature store

`data/feature_store.py` provides `zero_look_ahead_slice(df, timestamp)` which returns rows `<= timestamp` only, and `load_features(..., timestamp=ts)` slices at `timestamp`. Verified by `test_feature_store_zero_look_ahead_load` and `test_zero_look_ahead_slice_excludes_future`. **PASS.**

### 1.3 Candle completion (data ingestion)

`data/feeds/binance_ws.py`:

- **Live WS:** `_on_message` persists a bar only when `k.get("x") is True` (Binance kline `x` = is-final flag). Partial/ongoing klines are never written. **PASS.**
- **REST backfill:** `backfill_historical` fetches closed klines via `/api/v3/klines` (historical, already finalized). **PASS.**

No partial candle is ever acted upon by strategies or the backtester. **PASS.**

### 1.4 Fill timing (paper simulator + backtester)

`execution/paper_simulator.py` `on_bar()` and `validation/backtester.py` `run()`:

- MAE/MFE updated from current bar `high`/`low` only (`update_excursion(high, low)`).
- Exits checked on current-bar OHLC only: LONG stop if `low <= stop_loss`; TP2 if `high >= target_2`; TP1 if `high >= target_1`. SHORT mirrors.
- Stop-loss is checked **first** (worst-case fill at stop if both stop and target touch on the same bar) — conservative, execution-realistic.
- Entry at current bar `close`; slippage + commission deducted per leg.
- Flat close at end of range at last bar's close (`TIME_EXIT`) — no look-ahead beyond final bar.

Verified by `test_backtester_zero_look_ahead` (truncating future does not change earlier-bar results) and `test_backtester_flat_close_at_end`. **PASS.**

### 1.5 Stop/target evaluation (V1 strategies + risk manager)

`strategies/approved/vwap_fvg_v1.py` and `ema_breakout_v1.py` compute all levels from `row` (current bar `t`) only:

- `stop_loss = min(close - risk, fvg_bottom)` — `close`, `atr`, `fvg_bull_bottom` all from current row.
- `target_1 = close + risk * tp_rr_ratio`, `target_2 = close + risk * tp2_rr_ratio`.
- `RiskManager.atr_stop(entry, atr)` — entry + ATR buffer, all current-bar.

No stop/target references a future bar. **PASS.**

### 1.6 Validation gatekeeper (no AI self-approval)

`validation/gatekeeper.py`:

- Data split chronologically: first 70% in-sample, final 30% out-of-sample. Each backtest sees only bars up to its own `end_idx` (no cross-contamination).
- Walk-forward K=5 windows roll forward only.
- Parameter heatmap perturbs top-2 params ±20/±10/0 on in-sample only.
- Cost stress uses 1.5× slippage on OOS only.
- `V1` stays active on any failure; candidate never auto-deployed.

Verified by `test_gatekeeper_approves_profitable_candidate`, `test_gatekeeper_rejects_losing_candidate`, `test_gatekeeper_cost_stress_rejects`. **PASS.**

---

## 2. Risk-Management Concerns — Evidence

### 2.1 Volume profile (POC/VAH/VAL) — RESOLVED (was ZLA-001)

`indicators/orderflow.py` `session_volume_profile()` previously computed
POC/VAH/VAL from the **full day's** data (day-level min/max price and total
volume), then forward-filled to every bar in that session. At bar `t` early in
a session, `POC/VAH/VAL` reflected bars after `t` — an intra-session look-ahead
bounded to the same calendar day.

**Resolved:** The indicator now computes an expanding within-session profile.
For each bar `t`, the volume-at-price histogram is built from session-start
through `t` only (`tp.iloc[:j+1]`, `vol.iloc[:j+1]`), so bar `t` sees exactly
`t <= T`. Bars before any session data see NaN rather than a future-precomputed
level.

Covered by new regression test `test_session_volume_profile_no_intra_session_lookahead`
(diverging future-in-day bars must not alter an earlier bar's POC/VAH/VAL).
**PASS.**

### 2.2 Position sizing & circuit breakers

`risk/risk_manager.py`:

- `size_position()` caps risk at `MAX_RISK_PER_TRADE_PCT` (1%) of equity; `risk_per_share = |entry - stop|`.
- `can_open_trade()` checks daily-loss circuit breaker (3%), consecutive-loss breaker (2), max-drawdown kill-switch (3%).
- `validate_rr()` enforces `MIN_RISK_REWARD_RATIO` (1.5).

All use running daily state only (no future). **PASS.**

### 2.3 Execution costs (slippage + commission)

`risk/risk_manager.py` `slippage_cost(notional, bp)` and `commission_cost(notional, taker)` deducted on entry AND exit, recorded in `risk.record_costs()`. Binance spot maker/taker = 1bp; PERP maker/taker = 2bp/4bp; default slippage pad = 1bp per leg. Gatekeeper cost-stress test uses 1.5× slippage on OOS and requires `PF >= 1.15` AND `ER >= +0.12R`. **PASS.**

### 2.4 Max-drawdown & expectancy

Backtester `_build_result` computes max drawdown from the equity curve and expectancy in R. Gatekeeper OOS test requires `PF_OOS >= 1.25`, `ER_OOS > ER_OOS(V1)`, `MaxDD_OOS <= MaxDD_OOS(V1)`. **PASS.**

---

## 3. Test Coverage for Zero Look-Ahead

| Test | What it verifies | Result |
|------|-----------------|--------|
| `test_ema_zero_look_ahead` | Truncated EMA input == earlier outputs | PASS (61/61 suite) |
| `test_rsi_zero_look_ahead` | Truncated RSI input == earlier outputs | PASS |
| `test_hma_zero_look_ahead` | Truncated HMA input == earlier outputs | PASS |
| `test_pivots_uses_previous_bar_only` | PP = (prev H+L+C)/3, first row NaN | PASS |
| `test_zscore_zero_look_ahead` | Truncated zscore == earlier outputs | PASS |
| `test_structure_indicators_no_future_leakage` | PDH from prior day only; changing day-2 bars doesn't alter day-2's PDH | PASS |
| `test_technical_indicators_no_future_leakage` | Changing future bars (idx 95+) doesn't alter EMA/RSI at idx <= 94 | PASS |
| `test_orderflow_no_future_leakage` | Changing future close doesn't alter VWAP before the change | PASS |
| `test_session_volume_profile_no_intra_session_lookahead` | Future-in-day bars don't alter earlier bar's POC/VAH/VAL (ZLA-001 regression) | PASS |
| `test_opening_range_no_same_session_lookahead` | Opening-range levels invariant to later window bars (ZLA regression) | PASS |
| `test_opening_range_no_pre_market_positional_leak` | Pre-market bars (00:00 start) don't corrupt opening-range positional slicing; 09:15 bar excludes 09:20 future spike (Correction 1) | PASS |
| `test_feature_store_zero_look_ahead_load` | `load_features(timestamp=ts)` returns <= ts rows | PASS |
| `test_zero_look_ahead_slice_excludes_future` | `zero_look_ahead_slice` excludes index > ts | PASS |
| `test_backtester_zero_look_ahead` | Truncated future doesn't change earlier-bar trades/PnL/exit prices | PASS |
| `test_gatekeeper_*` | OOS/WFA/heatmap/cost-stress use chronological splits only | PASS (14/14 suite) |

---

## 4. Finding & Remediation

| ID | Severity | Area | Description | Remediation |
|----|----------|------|-------------|-------------|
| ZLA-001 | Medium (RESOLVED) | `indicators/orderflow.py` `session_volume_profile()` + `indicators/structure.py` `opening_range()` | POC/VAH/VAL computed from full day then ffilled → early-session bars saw future-in-day data; `opening_range()` forward-filled window levels across session. Both now expanding/past-only so bar `t` sees `<= t` only. | Replaced full-day computation with expanding within-session profile; `opening_range()` holds expanding window levels then final window levels. Regression tests added. **VERIFIED PASS.** |

This finding does **not** invalidate the zero-look-ahead claim for the system as a whole: every other indicator, signal, strategy, backtester exit, paper fill, and gatekeeper split is verified `t <= T`. ZLA-001 is a single, bounded, fixable exception in one orderflow indicator.

---

## 5. Cross-References

- `docs/ARCHITECTURE_DECISIONS.md` — ADR-001 (Binance-only scope), ADR-002 (rule-based only), ADR-003 (human review gate), ADR-005 (deprecated NSE retained)
- `docs/strategy_and_validation_spec.md` — zero-look-ahead authoring rule + gatekeeper math
- `docs/contributing_indicators.md` — indicator contribution rules incl. zero-look-ahead
- `trading_engine/config.py` — `ZERO_LOOK_AHEAD = True` (line 75)
- `KNOWN_ISSUES.md` — KI-005 (top-10 eligibility / max-5 cap), KI-010 (13 repo URLs blocker)
- `DEVELOPMENT_PLAN_AND_TODO.md` — Phase C task C.4
