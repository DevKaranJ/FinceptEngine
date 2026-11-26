# PHASE E — Implementation Blueprint: Binance Spot + USDⓈ-M Futures Platform

**Project:** FinceptEngine — Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Branch:** `audit/planning-finceptengine-transformation` (HEAD = `592144f`; NOT merged to `dev`)  
**Status:** PLANNING ONLY — no implementation authorized  
**Version:** 0.1  
**Date:** 2026-11-24

---

## Scope & Constraints (binding)

| Constraint | Source |
|---|---|
| Binance Spot + USDⓈ-M Futures only | ADR-001 (Accepted) |
| Dynamic scan of top 10 eligible assets by rolling 24h quote volume | ADR-009 (Proposed) |
| Maximum five independent deterministic rule-based strategies | ADR-010 (Proposed) |
| No ML/LLM trading decisions, no RL, no autonomous strategy generation | master_architecture.md Section 5 |
| No automatic real-money order execution; human executes broker orders manually | master_architecture.md Section 5 |
| Spot and Futures data, instruments, order books, fees and risk models isolated | ADR-012 (Proposed) |
| Preserve working code; avoid unnecessary rebuilding | master_architecture.md Section 5 |
| STRICTLY PLANNING ONLY: no source changes, no dependency installs, no commits/push/merges | Task instructions |

**Deliverables:**
1. Existing versus missing components, with implementation status.
2. Review of ADR-001 through ADR-012, including conflicts, dependencies and unresolved risks.
3. Sequential Phase E implementation milestones, with files, dependencies, tests and acceptance criteria.
4. Phase F validation and Phase G live-signal delivery plans.
5. Final readiness report, blockers, external requirements and realistic timeline.

---

## 1. Existing Versus Missing Components (implementation status)

This table is grounded in the full source inspection of `config.py`, `data/feeds/binance_ws.py`, `memory/db.py`, `memory/trade_logger.py`, `indicators/*.py`, `signals/*_signals.py`, `strategies/base_strategy.py`, `strategies/approved/*`, `risk/risk_manager.py`, `execution/paper_simulator.py`, `validation/gatekeeper.py`, `validation/backtester.py`, `evaluation/analyzer.py`, `data/feature_store.py`, `trading_engine/backend/server.py`, `frontend/*`, and `trading_engine/tests/*`.

**Verification rule:** `[IMPLEMENTED]` means code exists and is exercised by the 133-test baseline. `[PARTIAL]` means code exists but is spot-only or lacks futures isolation. `[MISSING]` means no implementation exists — specified-only (ADR-009/010/011/012). `[DEFERRED]` means out of scope for Phase E (documented as a release limitation). Nothing is claimed as implemented unless verified in source.

Legend:
- **[IMPLEMENTED]** — code exists, covered by the 133-test baseline.
- **[PARTIAL]** — code exists but is spot-only or lacks futures isolation.
- **[MISSING]** — no implementation; specified-only (ADR-009/010/011/012).
- **[DEFERRED]** — out of Phase E scope; documented as a release limitation.

### Core Layer 0 — Config & Clock

| Component | File | Status | Notes |
|---|---|---|---|
| Binance Spot REST base URL (`api.binance.com/api/v3`) | `config.py:39` | [IMPLEMENTED] | Spot endpoints only |
| Binance Spot WS base URL (`stream.binance.com:9443/ws`) | `config.py:38` | [IMPLEMENTED] | Spot WS only |
| Binance USDM Futures REST base URL (`fapi.binance.com/fapi/v1`) | `config.py` | [MISSING] | Not defined |
| Binance USDM Futures WS base URL (`fstream.binance.com/ws`) | `config.py` | [MISSING] | Not defined |
| Kline intervals (1m, 5m, 15m, 1h, 1d) | `config.py:40` | [IMPLEMENTED] | Spot intervals |
| Spot fee schedule: maker/taker BP | `config.py:46-47` | [IMPLEMENTED] | `BINANCE_SPOT_MAKER_BP=1`, `BINANCE_SPOT_TAKER_BP=1` |
| Futures fee schedule: maker/taker BP | `config.py:48-49` | [IMPLEMENTED] | **Already present** `BINANCE_PERP_MAKER_BP=2`, `BINANCE_PERP_TAKER_BP=4` |
| Funding rate constants | `config.py` | [MISSING] | Not defined |
| Default slippage BP | `config.py:52` | [IMPLEMENTED] | `DEFAULT_SLIPPAGE_BP=1` |
| `CRYPTO_TRADEABLE_PAIRS` (hardcoded 3 pairs) | `config.py:25` | [PARTIAL] | Hardcoded BTCUSDT, ETHUSDT, SOLUSDT; not dynamic |
| Spot/Futures separate asset universes | — | [MISSING] | No independent Spot vs Futures universe selection |
| Crypto session (24/7) helpers | `data/clock.py` | [IMPLEMENTED] | UTC crypto session; daily reset boundary |
| Market session (MarketSession class) | `data/clock.py` | [PARTIAL] | Retains deprecated NSE IST constants (import-compat only) |

### Layer 1 — Data Feeds

| Component | File | Status | Notes |
|---|---|---|---|
| Binance Spot WS klines + aggTrade | `data/feeds/binance_ws.py` | [PARTIAL] | Spot-only WS connector; no USDⓈ-M perp WS |
| Spot REST backfill klines (`/api/v3/klines`) | `data/feeds/binance_ws.py` | [IMPLEMENTED] | Spot historical OHLCV backfill |
| Spot 24h ticker (`/api/v3/ticker/24hr`) | — | [MISSING] | No scanner implementation exists |
| USDⓈ-M Futures WS connector | `data/feeds/binance_futures_ws.py` | [MISSING] | Not implemented (ADR-011) |
| Futures klines backfill (`/fapi/v1/klines`) | — | [MISSING] | Not implemented |
| Futures mark price stream | — | [MISSING] | Not implemented |
| Futures funding rate stream | — | [MISSING] | Not implemented |
| Futures instrument metadata (exchangeInfo) | — | [MISSING] | Not implemented |
| Spot/Futures topic normalization | `data/feeds/binance_ws.py` | [IMPLEMENTED] | Spot `_normalize_bar` hardcodes `market_type="CRYPTO_SPOT"` |
| WS reconnect / stale / duplicate / out-of-order handling | `data/feeds/binance_ws.py` | [MISSING] | No reliability handling exists |
| Order-book depth streams (Spot) | — | [DEFERRED] | No order-book acquisition anywhere |
| Order-book depth streams (Futures) | — | [DEFERRED] | No order-book acquisition anywhere |

### Layer 1B — Indicators

| Component | File | Status | Notes |
|---|---|---|---|
| Family A (technical): EMA, SMA, RSI, ATR, Bollinger, MACD, Supertrend, Pivots, HMA | `indicators/technical.py` | [IMPLEMENTED] | Zero look-ahead (`shift(1)`) |
| Family B (statistical): Z-Score, Hurst, Vol Percentile, Reg Slope, RS | `indicators/statistical.py` | [IMPLEMENTED] | Zero look-ahead |
| Family C (structure): PDH/PDL/PDC, ORB, Trendlines, FVG, Order Blocks, Liquidity Sweeps | `indicators/structure.py` | [IMPLEMENTED] | Zero look-ahead |
| Family D (orderflow): VWAP, RVOL, Volume Profile POC/VAH/VAL, CVD, Footprint, Iceberg | `indicators/orderflow.py` | [IMPLEMENTED] | Zero look-ahead |

### Layer 2A — Signals

| Component | File | Status | Notes |
|---|---|---|---|
| `signals/technical_signals.py` | `signals/technical_signals.py` | [IMPLEMENTED] | Reusable True/False conditions |
| `signals/statistical_signals.py` | `signals/statistical_signals.py` | [IMPLEMENTED] | Reusable True/False conditions |
| `signals/structure_signals.py` | `signals/structure_signals.py` | [IMPLEMENTED] | Reusable True/False conditions |
| `signals/orderflow_signals.py` | `signals/orderflow_signals.py` | [IMPLEMENTED] | Reusable True/False conditions |

### Layer 2B — Strategies

| Component | File | Status | Notes |
|---|---|---|---|
| `BaseStrategy` abstract interface | `strategies/base_strategy.py` | [IMPLEMENTED] | `evaluate()` contract; zero look-ahead |
| V1 Baseline: EMA Breakout | `strategies/approved/ema_breakout_v1.py` | [IMPLEMENTED] | LONG only |
| V1 Baseline: VWAP + FVG | `strategies/approved/vwap_fvg_v1.py` | [IMPLEMENTED] | LONG only |
| V2 candidate directory | `strategies/candidates/` | [EMPTY] | Empty (no candidates yet) |
| Spot/Futures strategy compatibility flag | — | [MISSING] | No per-strategy market_type scoping |
| Long/short capability flag per strategy | — | [MISSING] | No per-strategy direction capability declaration |
| Max-5 strategy cap enforcement | — | [MISSING] | Not implemented (ADR-010) |

### Layer 3 — Memory / Trade Logging

| Component | File | Status | Notes |
|---|---|---|---|
| SQLite WAL schema (5 tables) | `memory/db.py` | [IMPLEMENTED] | `ohlcv_bars` has `market_type` column |
| `ohlcv_bars` PRIMARY KEY | `memory/db.py:37` | [PARTIAL] | PK = `(symbol, timeframe, open_time_utc)` — **market_type NOT in PK**; uniqueness constraint gap |
| `ohlcv_bars` index on market_type | `memory/db.py:119` | [MISSING] | `idx_ohlcv_symbol_tf_time` does not include market_type |
| `trades_memory` market_type column | `memory/trade_logger.py` / `memory/db.py:40` | [MISSING] | **No market_type column** in trades_memory |
| `validation_reports` market_type column | `memory/db.py:85` | [MISSING] | **No market_type column** in validation_reports |
| Trade open/close with MAE/MFE | `memory/trade_logger.py` | [IMPLEMENTED] | `execution_mode` (BACKTEST/PAPER_LIVE/MANUAL_LIVE) |
| Spot/futures isolation enforced at query layer | `memory/db.py` | [PARTIAL] | Column exists but no query-layer enforcement |

### Layer 4 — Feature Store

| Component | File | Status | Notes |
|---|---|---|---|
| SQLite + Parquet feature cache | `data/feature_store.py` | [IMPLEMENTED] | `t <= T` zero look-ahead; per (symbol, timeframe) |
| `indicator_features` PRIMARY KEY | `data/feature_store.py:92` | [PARTIAL] | PK = `(symbol, timeframe, open_time_utc)` — **market_type NOT in PK** |
| `indicator_features` cache key includes market_type | `data/feature_store.py` | [MISSING] | Cache key does not include market_type |
| Parquet export/import (optional pyarrow) | `data/feature_store.py` | [IMPLEMENTED] | Graceful degradation |

### Layer 4B — Evaluation

| Component | File | Status | Notes |
|---|---|---|---|
| Evaluation Engine + Weakness Detection | `evaluation/analyzer.py` | [IMPLEMENTED] | PF, Win Rate, Expectancy, regime breakdown |

### Layer 5 — Risk

| Component | File | Status | Notes |
|---|---|---|---|
| Position sizing (risk % of equity) | `risk/risk_manager.py` | [IMPLEMENTED] | Spot-oriented (no leverage/margin) |
| Circuit breakers (daily loss, consecutive loss, drawdown) | `risk/risk_manager.py` | [IMPLEMENTED] | |
| Execution costs (spot maker/taker BP) | `risk/risk_manager.py` | [IMPLEMENTED] | Spot fee schedule |
| Leverage support | `risk/risk_manager.py` | [MISSING] | Not implemented |
| Initial margin / maintenance margin | `risk/risk_manager.py` | [MISSING] | Not implemented |
| Liquidation price / liquidation handling | `risk/risk_manager.py` | [MISSING] | Not implemented |
| Funding rate cost | `risk/risk_manager.py` | [MISSING] | Not implemented |
| Mark-price vs last-price handling | `risk/risk_manager.py` | [MISSING] | Not implemented |

### Layer 6 — Validation Gatekeeper

| Component | File | Status | Notes |
|---|---|---|---|
| OOS Split 70/30 | `validation/gatekeeper.py` | [IMPLEMENTED] | All 4 tests deterministic |
| Rolling Walk-Forward (K=5) | `validation/gatekeeper.py` | [IMPLEMENTED] | |
| Parameter Sensitivity Heatmap (5x5) | `validation/gatekeeper.py` | [IMPLEMENTED] | |
| Execution Cost & Slippage Stress (1.5x) | `validation/gatekeeper.py` | [IMPLEMENTED] | |
| `market_type` in validation report | `validation/gatekeeper.py` | [MISSING] | `ValidationReport` has no market_type field |
| Report persisted to `validation_reports` | `validation/gatekeeper.py` | [IMPLEMENTED] | Table has no market_type column |

### Layer 7 — Execution (Paper)

| Component | File | Status | Notes |
|---|---|---|---|
| Paper trade lifecycle | `execution/paper_simulator.py` | [IMPLEMENTED] | MAE/MFE tracking |
| Futures-aware paper simulation (leverage/margin/liquidation/funding) | `execution/paper_simulator.py` | [MISSING] | Spot-only position sizing and PnL |
| Human manual order ticket | `backend/server.py` `POST /api/trades/manual` | [IMPLEMENTED] | Manual (human executes broker orders) |
| Auto real-money execution | — | [ABSENT BY DESIGN] | Not supported; human-only |

### Layer 8 — Backend + Frontend

| Component | File | Status | Notes |
|---|---|---|---|
| FastAPI app + REST routes | `trading_engine/backend/server.py` | [IMPLEMENTED] | Spot snapshot default |
| `/api/market/snapshot` market_type param | `server.py:304` | [PARTIAL] | Hardcodes `market_type = "CRYPTO_SPOT"`; no futures slice served. API backward compatibility: existing default behavior remains `CRYPTO_SPOT`; futures data returned only when explicitly requested via supported `market_type` parameter |
| WebSocket hub `/ws/live` | `trading_engine/backend/server.py` | [IMPLEMENTED] | Spot streams |
| Frontend (TradingView Lightweight Charts) | `frontend/` | [IMPLEMENTED] | Phase 6 |
| `/api/validation/reports` scorecard | `trading_engine/backend/server.py` | [IMPLEMENTED] | |

### Layer 9 — Tests

| Test file | Status | Coverage |
|---|---|---|
| `tests/test_phase1_data_db.py` | [IMPLEMENTED] | 22/22 pass |
| `tests/test_phase2_indicators_signals.py` | [IMPLEMENTED] | 64/64 pass |
| `tests/test_phase3_execution_memory.py` | [IMPLEMENTED] | 24/24 pass |
| `tests/test_phase4_eval_validation.py` | [IMPLEMENTED] | 14/14 pass |
| `tests/test_phase6_backend_ui.py` | [IMPLEMENTED] | 9/9 pass |
| Phase E isolation / replay / futures risk / live-reliability tests | — | [MISSING] |
| **Total baseline** | **133 tests** | **All pass** |

---

### Missing Components Summary (to be addressed in Phase E)

| # | Missing component | Required ADR | Priority |
|---|---|---|---|
| M1 | Separate Spot & USDⓈ-M Futures asset universes with independent volume rankings | ADR-009 | High |
| M2 | Max-5 independent strategy cap enforcement | ADR-010 | High |
| M3 | USDⓈ-M Futures WS connector (klines, mark price, funding) | ADR-011 | High |
| M4 | Spot/Futures DB & feature-store isolation (market_type in PK, indexes, query filters) | ADR-012 | High |
| M5 | Futures risk: leverage, initial/maintenance margin, liquidation, funding, mark-price | ADR-012 | High |
| M6 | Futures paper simulation (leverage/margin/liquidation/funding/mark-price) | ADR-005/012 | High |
| M7 | Live-feed reliability: reconnects, stale-data, duplicates, out-of-order, incomplete candles | ADR-011 | High |
| M8 | Spot/Futures strategy compatibility & long/short capability | ADR-001/010 | Medium |
| M9 | Order-book data acquisition (deferred — release limitation) | ADR-012 | Deferred |
| M10 | Phase E tests: isolation, historical replay, futures risk, live-data reliability | — | High |

---

## 2. Review of ADR-001 through ADR-012

This review distinguishes **Accepted** (ADR-001–008) from **Proposed / specified-not-implemented** (ADR-009–012). No proposed ADR is described as implemented anywhere in this document.

### ADR-001 — Binance Spot + USDⓈ-M Futures only (remove NSE/Equities scope)
**Status:** Accepted

**Context:** The codebase previously targeted both Crypto (Binance Spot + USDⓈ-M Perpetuals) and NSE Equities (IST sessions, 09:15–15:30, Mon–Fri). The transformation narrows scope to Binance Spot + USDⓈ-M Futures only.

**Current implementation state:** `config.py` retains deprecated NSE constants (`NSE_SESSION_IST_START`, `NSE_SESSION_IST_END`, `NSE_SESSION_IST_WINDOW`, `NSE_TRADING_DAYS`) marked DEPRECATED, retained only so `data/clock.py` and Phase 1 tests import cleanly. `data/clock.py` still imports and references these NSE constants in its `MarketSession` class. `config.py:25` defines `CRYPTO_TRADEABLE_PAIRS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")` (3 pairs, hardcoded).

**Phase E implication:** NSE references must remain for import compatibility (surgical diffs only — do not remove). New futures code must not reference NSE constants.

### ADR-002 — Rule-based strategies only; no ML/LLM/RL autonomous decisions
**Status:** Accepted

**Current implementation state:** All indicators are pure math functions; all signals are reusable True/False conditions; all strategies inherit `BaseStrategy.evaluate()` returning a deterministic trade dict. `strategies/candidates/` is empty (no V2 candidates yet).

**Phase E implication:** Any new strategy added in Phase E must be rule-based and deterministic. No ML/LLM/RL code may be introduced.

### ADR-003 — Zero look-ahead protection (t <= T)
**Status:** Accepted

**Current implementation state:** Enforced across indicators (`shift(1)`), feature store (`t <= T`), trade logger (MAE/MFE from observed bars only), evaluation (metrics from closed trades only), backend snapshot (stored historical bars only).

**Phase E implication:** The futures WS connector and feature store must preserve `t <= T`. Rolling 24h quote volume scan must use only completed 24h windows, never in-progress/future bars.

### ADR-004 — SQLite WAL mode; pyarrow/Parquet feature cache
**Status:** Accepted

**Current implementation state:** `memory/db.py` uses SQLite WAL. `data/feature_store.py` supports SQLite + optional Parquet export/import.

**Phase E implication:** Futures data must share the same WAL DB with `market_type` column separating spot vs perp rows.

### ADR-005 — Paper trade first; human executes real orders manually
**Status:** Accepted

**Current implementation state:** `execution/paper_simulator.py` handles paper lifecycle. `backend/server.py` `POST /api/trades/manual` logs human-executed trades. No auto real-money execution exists.

**Phase E implication:** Paper simulator must support both spot and futures positions. Manual order ticket must record `market_type`.

### ADR-006 — Independent Validation Gatekeeper; V1 stays active on failure
**Status:** Accepted

**Current implementation state:** `validation/gatekeeper.py` runs 4 deterministic tests (OOS 70/30, walk-forward K=5, parameter heatmap 5x5, cost stress 1.5x). Report persisted to `validation_reports`. V2 candidate promotion requires all 4 PASS.

**Phase E implication:** Futures strategies must pass the same gatekeeper before promotion.

### ADR-007 — Multi-paradigm Lego indicator/signal library
**Status:** Accepted

**Current implementation state:** Four indicator families (technical, statistical, structure, orderflow) and four matching signal modules. All zero look-ahead.

**Phase E implication:** Reusable; no new indicator families required for Phase E unless a new strategy demands them.

### ADR-008 — Phased roadmap (Phases 1–6 complete; Phase E = futures/top-10/isolation)
**Status:** Accepted

**Current implementation state:** Phases 1–6 implemented and tested (133 tests pass). Phase E is the next phase (this blueprint).

**Phase E implication:** Phase E builds on Phases 1–6 without rebuilding them.

---

### ADR-009 — Dynamic top-10 eligible asset scanner by rolling 24h quote volume
**Status:** Proposed (specified, NOT implemented)

**Specification:** Dynamically scan the top 10 eligible cryptocurrencies by rolling 24-hour quote volume.

**Client-approved decisions (B1–B3):**

**B1 — Independent Spot and Futures universes:** Spot and USDⓈ-M Futures each maintain an **independent** eligible-universe selection. The Spot universe is ranked by Spot 24h quote volume from `/api/v3/ticker/24hr`; the Futures universe is ranked by Futures 24h quote volume from `/fapi/v1/ticker/24hr`. Each universe selects its own top 10. Eligibility filters are:
- USDT-quoted pairs only,
- minimum liquidity filtering (numeric thresholds configurable and separate by market type — initial values require client confirmation before scanner implementation),
- exclude leveraged tokens.

Eligibility filters apply separately per `market_type`. Keep Spot and Futures scanner rankings independent.

**B2 — Scanner refresh frequency:** Refresh both Spot and Futures scanners every five minutes, with controlled membership changes using an explicit, configurable entry/exit policy. Do not invent unapproved hysteresis values. The entry/exit policy parameters require client confirmation before scanner implementation.

**B3 — Symbol leaving top 10:** When a symbol leaves its `market_type` top 10, stop new entries for that symbol but continue managing existing positions normally. Open positions must remain monitored after a symbol leaves the top 10.

**Point-in-time historical scanner snapshots:** To avoid survivorship and look-ahead bias, each scanner run must be captured as a point-in-time snapshot:
- Record the universe membership (top-10 symbol list) with a `snapshot_utc` timestamp and the `market_type` in a dedicated persistence store (DB table or append-only log).
- Backtests and historical replays must use the universe membership that was valid **at each historical bar's timestamp**, not the current membership. A symbol that entered the top 10 only at time T must not be present in the universe at time T-1.
- Replay of historical bars must join against the snapshot table as-of each bar's open time (as-of join), never using future scanner results.

**Current implementation state:** [MISSING]. No dynamic eligibility logic exists. `CRYPTO_TRADEABLE_PAIRS` remains hardcoded to 3 pairs (KI-005 open). No scanner snapshot table exists. Numeric liquidity thresholds and entry/exit policy parameters are pending client confirmation.

**Dependencies:** Requires Binance Spot 24h ticker REST endpoint (`/api/v3/ticker/24hr`) and USDM Futures 24h ticker (`/fapi/v1/ticker/24hr`). Must run periodically (every 5 minutes per B2) and refresh each universe independently. Output feeds both spot and futures data collection.

**Unresolved risks / questions:**
- Numeric liquidity thresholds per market type require client confirmation before implementation.
- Entry/exit policy parameters (hysteresis) require client confirmation before implementation.
- Where is the scanned universe persisted (config, DB table, in-memory only)? Scanner snapshots must be queryable for historical replay.

---

### ADR-010 — Maximum five independent deterministic rule-based strategies
**Status:** Proposed (specified, NOT implemented)

**Specification:** Cap active strategies at 5.

**Client-approved decisions (B4, B5, B7):**

**B4 — Global strategy cap:** Maximum five active approved strategies globally across Spot and Futures (not per market_type).

**B5 — V1 + V2 count together:** Both V1 and V2 active approved strategies count toward the same global limit of 5.

**B7 — Market-specific strategies:** Strategies are market-specific by default. Cross-market compatibility (a single strategy running on both Spot and Futures) requires explicit client approval. Each strategy must declare:
- `market_type` compatibility: `CRYPTO_SPOT`, `CRYPTO_PERP`, or both.
- `direction` capability: `LONG`, `SHORT`, or `LONG_AND_SHORT`.

The max-5 cap applies globally across Spot and Futures. A strategy declared `CRYPTO_SPOT` only cannot activate on a futures symbol; a `LONG`-only strategy cannot open SHORT positions. Cross-market compatibility requires explicit client approval before a `both` market_type strategy can be activated on both universes. V1 baselines (ema_breakout_v1, vwap_fvg_v1) are both `CRYPTO_SPOT` + `LONG`-only per their source.

**Current implementation state:** [MISSING]. No strategy cap enforcement exists. `strategies/approved/` holds 2 V1 baselines; `strategies/candidates/` is empty. No per-strategy market_type or direction declaration exists. No cross-market compatibility has been approved.

**Dependencies:** Requires a strategy registry/manager that tracks active approved strategy count globally (V1 + V2 together), enforces the max-5 cap, and rejects activation beyond cap or if strategy market_type/direction is incompatible with the target market (unless cross-market compatibility is explicitly approved).

**Unresolved risks / questions:**
- What happens when a 6th strategy is requested — error, or auto-disable lowest-performing? (client decision pending)
- Which strategies (if any) are approved for cross-market compatibility? (client decision pending)

---

### ADR-011 — USDⓈ-M Futures WS connector (perp streams)
**Status:** Proposed (specified, NOT implemented)

**Specification:** Add a USDⓈ-M Futures WebSocket connector for perpetual streams.

**Client-approved decision (B6):**

**B6 — Initial Futures data scope:** Initial Futures market data covers klines, mark price, actual funding rates, and instrument metadata. Order-book acquisition and reconstruction are deferred as a release limitation (see ADR-012 order-book section). Order-book-dependent features are unsupported in the initial release.

**Correction (expanded futures market-data requirements):** The futures connector must acquire:
- **Klines** via `<symbol>@kline_<interval>` on `wss://fstream.binance.com/ws` (same topic format as spot, different host).
- **Mark price** stream via `<symbol>@markPrice` — required for unrealized PnL, liquidation checks, and mark-price-based position valuation (not last price).
- **Funding rates** via `<symbol>@fundingRate` stream or REST `/fapi/v1/fundingRate` — required as a cost in futures paper simulation and risk.
- **Instrument metadata** via REST `/fapi/v1/exchangeInfo` — contract size (quantity step), tick size, leverage limits, maintenance margin requirements.
- **Historical backfill** via REST `/fapi/v1/klines` for futures OHLCV history.

**Live-feed reliability requirements (correction):** The futures WS (and spot WS) must implement:
- **Reconnects:** automatic reconnect with exponential backoff on connection loss; resubscribe to all topics on reconnect.
- **Stale-data detection:** track last-message timestamp per stream; declare a stream stale if no message arrives within a configured heartbeat window (e.g., 2× kline interval); pause strategy evaluation for stale symbols.
- **Duplicate events:** deduplicate by event ID / kline start time; ignore bars already persisted (PRIMARY KEY on `ohlcv_bars` provides idempotency via `INSERT OR REPLACE`).
- **Out-of-order events:** buffer and reorder by `open_time_utc`; do not process a bar with `open_time` earlier than the last processed bar for that (symbol, timeframe, market_type).
- **Incomplete candles:** only persist/process klines with `x=True` (finalized); in-progress candles must not be used for trade decisions or persistence (zero look-ahead).
- **Recovery:** on reconnect, backfill any missed closed klines from REST before resuming live streaming.

**Current implementation state:** [MISSING]. `data/feeds/binance_ws.py` is spot-only (`wss://stream.binance.com:9443/ws`). No futures WS connector exists. No reconnect, stale-data, duplicate, out-of-order, or incomplete-candle handling exists in either connector.

**Binance endpoint facts (for planning):**
- USDM Futures WS base: `wss://fstream.binance.com/ws`
- USDM Futures REST base: `https://fapi.binance.com/fapi/v1`
- Kline topic: `<symbol>@kline_<interval>` (same format as spot, different host)
- Mark price topic: `<symbol>@markPrice`
- Funding rate topic: `<symbol>@fundingRate`
- 24h ticker: `/fapi/v1/ticker/24hr` for futures quote volume
- Instrument metadata: `/fapi/v1/exchangeInfo`

**Dependencies:** New file `data/feeds/binance_futures_ws.py`. Feature store must tag futures rows with `market_type='CRYPTO_PERP'`.

**Unresolved risks / questions:**
- Separate WS connections per market_type, or multiplexed?
- Are funding rate and mark price required for the initial Phase E release, or deferred?
- What heartbeat/stale thresholds apply?

---

### ADR-012 — Spot/Futures isolation (data, instruments, order books, fees, risk models)
**Status:** Proposed (specified, NOT implemented)

**Specification:** Isolate Spot and Futures data, instruments, order books, fees, and risk models. No cross-contamination.

**Correction (expanded isolation requirements):** Isolation must cover:
- **Query filters:** every read of `ohlcv_bars`, `trades_memory`, `validation_reports`, and `indicator_features` must filter by `market_type`.
- **Cache keys:** feature-store cache keys must include `market_type` (e.g., `(symbol, market_type, timeframe, open_time_utc)`).
- **Uniqueness constraints:** `ohlcv_bars` PRIMARY KEY must include `market_type` (currently `(symbol, timeframe, open_time_utc)` — gap). `indicator_features` PRIMARY KEY must include `market_type` (currently `(symbol, timeframe, open_time_utc)` — gap).
- **Indexes:** indexes must include `market_type` to support filtered queries efficiently.
- **New columns:** `trades_memory` and `validation_reports` must gain a `market_type` column (neither currently has one).
- **Fees:** spot fee schedule (`BINANCE_SPOT_MAKER/TAKER_BP`) and futures fee schedule (`BINANCE_PERP_MAKER/TAKER_BP`) must be applied per market_type; funding cost is futures-only. Maintain separate Spot and Futures fee models; use observed funding rates with exchange-provided timestamps (no fabricated fixed funding rate).
- **Risk:** spot risk (no leverage/margin) and futures risk (leverage, initial/maintenance margin, liquidation, funding, mark-price) must be separate code paths.
- **Backend:** endpoints must accept/return `market_type`; spot default must not leak futures data into spot responses. `server.py:304` currently hardcodes `market_type = "CRYPTO_SPOT"`.

**Order-book data acquisition (correction — deferred):** No order-book depth streams exist anywhere in the codebase (Spot or Futures). Order-book snapshot/update reconstruction, sequence-gap handling, and persistence are **out of scope for Phase E** and documented as a release limitation. If order-book data is required, it must be added in a later phase with:
- Spot depth: `<symbol>@depth` / `<symbol>@depth@100ms`
- Futures depth: `<symbol>@depth` on fstream
- Snapshot + diff update reconciliation
- Sequence-gap detection and recovery (re-request snapshot on gap)

**Current implementation state:** [PARTIAL]. `memory/db.py` `ohlcv_bars` has a `market_type` column but isolation is not enforced at query layer. `trades_memory` and `validation_reports` lack `market_type`. `config.py` already has perp fee constants (verified). `risk/risk_manager.py` is spot-oriented (no leverage/margin/liquidation/funding). `server.py` snapshot defaults to `CRYPTO_SPOT` hardcoded.

**Dependencies:**
- `config.py`: spot and futures fee schedules already present; add funding rate constants.
- `memory/db.py`: add `market_type` to `trades_memory` and `validation_reports`; extend `ohlcv_bars` and `indicator_features` PK to include `market_type`; add `market_type` indexes.
- `data/feature_store.py`: cache key must include `market_type`.
- `risk/risk_manager.py`: futures-aware position sizing (leverage, initial/maintenance margin, liquidation price).
- `execution/paper_simulator.py`: futures paper simulation (mark-price valuation, funding cost, liquidation).
- `validation/gatekeeper.py`: `ValidationReport` must include `market_type`.
- `server.py`: endpoints must accept/return `market_type`; default behavior remains `CRYPTO_SPOT` (API backward compatibility); futures data returned only when explicitly requested via supported `market_type` parameter; default API responses contain Spot data only; existing frontend behavior unchanged

**Unresolved risks / questions:**
- How are fees/slippage differentiated in practice (spot taker vs futures maker/taker + funding)? — see approved decision B8 for configuration contract; fee constants already present in config.
- Order-book-dependent features remain unsupported in the initial release (approved decision B6).

---

### Conflicts, Dependencies & Unresolved Risks (matrix)

| Conflict / Risk | ADRs involved | Severity | Resolution needed before Phase E |
|---|---|---|---|
| NSE deprecated constants still imported by `data/clock.py` | ADR-001 | Low | Leave for import compatibility; new code must not use them |
| Independent Spot vs Futures universes | ADR-009 | High | Scanner must rank each market_type separately |
| Point-in-time scanner snapshots vs survivorship bias | ADR-009 | High | Snapshot table with as-of join for historical replay |
| Spot-only WS vs futures WS connector | ADR-001, ADR-011 | High | New futures connector; spot connector untouched |
| `market_type` not in `ohlcv_bars`/`indicator_features` PK | ADR-012 | High | Extend PK/uniqueness constraints before futures data collection |
| `trades_memory`/`validation_reports` lack `market_type` | ADR-012 | High | Add column before futures trades/validation |
| Futures risk: leverage, margin, liquidation, funding, mark-price | ADR-005/012 | High | Extend risk manager and paper simulator before futures paper trading |
| Live-feed reliability (reconnects, stale, dup, out-of-order, incomplete candles) | ADR-011 | High | Must be in futures WS connector design |
| Order-book data absent (deferred release limitation) | ADR-012 | Medium | Document as out of Phase E scope |
| Max-5 scope (global vs per market_type) | ADR-010, ADR-012 | Medium | Decision needed: global cap or per-market_type cap |
| Universe refresh symbol churn affecting open trades | ADR-009 | Medium | Decision needed: sticky membership vs immediate swap |
| V2 candidate promotion with futures strategies | ADR-006, ADR-011 | Medium | Gatekeeper must support `market_type` in reports |

### ADR status summary

| ADR | Title | Status | Implemented? |
|---|---|---|---|
| ADR-001 | Binance Spot + USDⓈ-M Futures only | Accepted | Partially (NSE refs retained for import compat) |
| ADR-002 | Rule-based only; no ML/LLM/RL | Accepted | Yes |
| ADR-003 | Zero look-ahead (t <= T) | Accepted | Yes |
| ADR-004 | SQLite WAL + Parquet cache | Accepted | Yes |
| ADR-005 | Paper trade first; human executes real | Accepted | Yes |
| ADR-006 | Independent Validation Gatekeeper | Accepted | Yes |
| ADR-007 | Multi-paradigm Lego library | Accepted | Yes |
| ADR-008 | Phased roadmap | Accepted | Yes (Phases 1–6 done) |
| ADR-009 | Dynamic top-10 scanner | Proposed | No (KI-005) |
| ADR-010 | Max-5 strategy cap | Proposed | No (KI-005) |
| ADR-011 | USDⓈ-M Futures WS connector | Proposed | No (KI-005) |
| ADR-012 | Spot/Futures isolation | Proposed | Partial (DB column only) |

---

## 3. Sequential Phase E Implementation Milestones

Phase E builds on Phases 1–6 (133-test baseline, all passing). Milestones are sequential — each depends on the prior. Client approval under B9 authorizes implementation of Phase E milestone E.0 only. Milestones E.1–E.7 are not authorized and require separate client approval before each milestone begins.

**Correction to milestone order (per review item 9):** Market contracts and isolation (DB schema, feature-store keys, `market_type` enforcement) are established **before** market-specific data collection (scanner, futures WS). This prevents writing futures data into an un-isolated schema and avoids a later migration.

**Prerequisite (before any Phase E work):** Client approval to begin Phase E. No commits, pushes, or merges until explicitly authorized.

---

### Milestone E.0 — Market contracts & Spot/Futures isolation foundation (ADR-012)

**Files:** `trading_engine/memory/db.py`, `trading_engine/data/feature_store.py`

**Work (done before any data collection):**
- Add `market_type` column to `trades_memory` and `validation_reports` tables.
- Extend `ohlcv_bars` PRIMARY KEY to `(symbol, market_type, timeframe, open_time_utc)` and add `market_type` index.
- Extend `indicator_features` PRIMARY KEY to `(symbol, market_type, timeframe, open_time_utc)` and add `market_type` index.
- Enforce `market_type` filtering at every DB query layer (spot queries return only `CRYPTO_SPOT`; futures queries return only `CRYPTO_PERP`).
- Feature-store cache key must include `market_type` so spot and futures features are never aliased.
- No futures market data is collected in E.0; only schema/isolation contracts are established.

**Database migration (versioned, one-time):** SQLite does not support `ALTER TABLE ... MODIFY PRIMARY KEY`. To extend `ohlcv_bars` and `indicator_features` PKs to include `market_type`:
1. Create the new table with the extended PK `(symbol, market_type, timeframe, open_time_utc)`.
2. Copy existing records from the old table into the new table, backfilling `market_type = 'CRYPTO_SPOT'` **only** for records whose Spot origin is established (existing spot-only rows). Do not silently classify ambiguous records.
3. Replace the old table with the new table within a transaction.
4. Recreate indexes on `market_type` for both tables.
5. Add `market_type` column to `trades_memory` and `validation_reports` (new column, default NULL; no backfill required as no futures records exist yet).
6. Record a migration version (e.g., `schema_version` table or PRAGMA user_version) so the migration is idempotent and does not rerun destructive operations.
7. Validate row counts and key uniqueness before and after migration.

**Dependencies:** None (builds on existing `memory/db.py`, `data/feature_store.py`)

**Tests:** Add `tests/test_phase_e_isolation_contracts.py` verifying:
- `ohlcv_bars` PK includes `market_type` (uniqueness constraint prevents duplicate symbol/timeframe/time across market_type)
- `indicator_features` PK includes `market_type`
- `trades_memory` and `validation_reports` have `market_type` column
- Spot-only query on `ohlcv_bars` returns zero `CRYPTO_PERP` rows even when futures rows exist
- Futures-only query returns zero `CRYPTO_SPOT` rows even when spot rows exist
- Feature-store `write_features`/`load_features` keys include `market_type` and never return cross-market_type rows
- Migration is idempotent: running it twice on a pre-migration database fixture produces the same final schema and row count
- Migration preserves existing Spot records (row count unchanged, `market_type = 'CRYPTO_SPOT'` backfilled for established Spot records)
- Migration is transactional or has a documented safe recovery procedure on failure

**Acceptance criteria:**
- Schema enforces market_type isolation at PK/index level
- No code path returns mixed spot/futures data without explicit `market_type`
- 133-test baseline still passes (schema migration preserves existing Spot records)
- Migration is versioned, one-time, and idempotent

---

### Milestone E.1 — Config: Spot/Futures endpoints & futures fee/funding constants

**Files:** `trading_engine/config.py`

**Work:**
- Add `BINANCE_FUTURES_WS_BASE_URL = "wss://fstream.binance.com/ws"`
- Add `BINANCE_FUTURES_REST_BASE_URL = "https://fapi.binance.com/fapi/v1"`
- Verify/add funding rate constants (`BINANCE_PERP_FUNDING_RATE_BP` or similar)
- Verify spot and futures fee schedules are distinct (`BINANCE_SPOT_MAKER/TAKER_BP` vs `BINANCE_PERP_MAKER/TAKER_BP` — already present, verified)
- Funding rate configuration: add `BINANCE_PERP_FUNDING_RATE_SOURCE` setting (e.g., `'binance_ws'` or `'binance_rest'`) identifying where observed funding rates are sourced from; do not invent or hardcode a fixed funding rate as if it were Binance's actual rate
- Store observed funding rates with their effective/funding timestamps in `ohlcv_bars` or a dedicated funding table
- Funding rate units: decimal rate (not basis points unless conversion is documented); apply to eligible paper positions at the applicable funding timestamp
- Keep spot schedule untouched; NSE deprecated constants unchanged (import compatibility)

**Dependencies:** E.0 (isolation contracts not required for config, but E.0 completes first per ordering)

**Tests:** Add `tests/test_phase_e_config.py` verifying:
- Spot and futures fee schedules are distinct constants
- Futures WS/REST base URLs are present and correct
- Funding rate constant present
- NSE deprecated constants still importable (no regression)
- 133-test baseline still passes

**Acceptance criteria:**
- `config.py` exposes separate spot and futures fee schedules + futures endpoints + funding constants
- Existing 133-test baseline still passes (no regression)

---

### Milestone E.2 — Dynamic top-10 eligible asset scanner with point-in-time snapshots (ADR-009)

**Files:** New `trading_engine/data/scanner.py` (or `data/top10_scanner.py`); new DB table `scanner_snapshots`

**Work:**
- Implement scanner that calls Binance Spot `/api/v3/ticker/24hr` for Spot universe and `/fapi/v1/ticker/24hr` for Futures universe
- Rank each market_type independently by rolling 24h quote volume; select top 10 per market_type; keep Spot and Futures scanner rankings independent
- Filter each universe to USDT-quoted symbols, exclude leveraged tokens (per B1)
- Apply configurable minimum liquidity thresholds separate by market type (initial numeric values require client confirmation before implementation — do not invent values)
- Refresh both scanners every five minutes (per B2) using an explicit, configurable entry/exit policy for controlled membership changes (hysteresis parameters require client confirmation)
- Persist each scan as a point-in-time snapshot: `snapshot_utc`, `market_type`, symbol list, volume rankings
- When a symbol leaves its market_type top 10: stop new entries for that symbol but continue managing existing positions normally; open positions must remain monitored (per B3)
- Historical replay uses the snapshot valid **at each bar's timestamp** via as-of join (no survivorship/look-ahead bias)
- Expose function returning current top-10 per market_type

**Dependencies:** E.0 (isolation), E.1 (endpoints); network access to Binance REST

**Tests:** Add `tests/test_phase_e_scanner.py` verifying:
- Scanner returns exactly 10 symbols per market_type (or fewer if insufficient eligible)
- Spot and Futures universes are independent (different rankings possible)
- All returned symbols are USDT-quoted
- Ranking is by quote volume descending per market_type
- Point-in-time snapshot: a symbol entering top 10 at time T is not present at T-1 in replay
- Zero look-ahead: uses completed 24h windows only
- As-of join: replay at historical timestamp uses snapshot valid at that timestamp, not current membership

**Acceptance criteria:**
- Independent Spot and Futures top-10 universes with separate volume rankings
- All returned symbols are USDT-quoted; leveraged tokens excluded
- Configurable minimum liquidity thresholds separate by market type (initial numeric values pending client confirmation)
- Refresh both scanners every five minutes (per B2)
- Controlled membership changes via explicit, configurable entry/exit policy (hysteresis parameters pending client confirmation)
- When a symbol leaves its market_type top 10, no new entries for that symbol; existing positions remain monitored (per B3)
- Point-in-time scanner snapshots persist with `snapshot_utc` and `market_type`
- Historical replay uses as-of universe membership (no survivorship/look-ahead bias)
- No hardcoded pair list remains as the active universe source

**Unresolved questions:**
- Numeric liquidity thresholds per market type require client confirmation before implementation.
- Entry/exit policy parameters (hysteresis) require client confirmation before implementation.
- Where is the scanned universe persisted (config, DB table, in-memory only)? Scanner snapshots must be queryable for historical replay.

---

### Milestone E.3 — USDⓈ-M Futures WS connector with reliability (ADR-011)

**Files:** New `trading_engine/data/feeds/binance_futures_ws.py`

**Work:**
- Implement futures WS connector at `wss://fstream.binance.com/ws` (isolated from spot connector)
- Klines: `<symbol>@kline_<interval>` for futures symbols; normalize with `market_type='CRYPTO_PERP'`
- Mark price: `<symbol>@markPrice` stream
- Funding rates: `<symbol>@fundingRate` stream or REST `/fapi/v1/fundingRate`
- Instrument metadata: REST `/fapi/v1/exchangeInfo` (contract size, tick size, leverage limits, maintenance margin)
- Historical backfill: REST `/fapi/v1/klines` for futures OHLCV history
- Reliability handling:
  - Reconnects with exponential backoff; resubscribe to all topics on reconnect
  - Stale-data detection: track last-message timestamp per stream; pause strategy evaluation for stale symbols
  - Duplicate events: deduplicate by event ID/kline start time; `INSERT OR REPLACE` provides idempotency
  - Out-of-order events: buffer and reorder by `open_time_utc`; reject bars earlier than last processed
  - Incomplete candles: only persist/process klines with `x=True` (finalized)
  - Recovery: on reconnect, backfill missed closed klines from REST before resuming live streaming
  - Binance REST rate limits: respect endpoint request weights and rate-limit headers; handle HTTP 429 and 418 safely; use Retry-After when supplied; apply bounded exponential backoff with jitter; avoid retry storms and uncontrolled concurrent backfills; scanner refresh and historical backfill are rate-limit-aware
- Keep spot connector (`binance_ws.py`) untouched

**Dependencies:** E.0 (isolation), E.1 (futures endpoints), E.2 (top-10 futures universe)

**Tests:** Add `tests/test_phase_e_futures_ws.py` verifying:
- Futures WS base URL is `wss://fstream.binance.com/ws` (distinct from spot)
- Normalized futures rows carry `market_type='CRYPTO_PERP'`
- Spot connector unchanged (no regression)
- Reconnect resubscribes to all topics
- Stale stream detection pauses evaluation
- Duplicate kline events are deduplicated
- Out-of-order bars are rejected/reordered
- Incomplete candles (x=False) are not persisted
- Missed klines backfilled from REST on reconnect
- Funding rates are observed and stored with timestamps
- Market data scope is limited to klines, mark price, funding rates, and instrument metadata; order-book acquisition is deferred as a release limitation
- Order-book depth streams are not implemented in the initial release (per B6)

**Acceptance criteria:**
- Futures WS connector isolated from spot connector; spot remains spot-only
- Klines, mark price, funding rates, instrument metadata acquired
- Order-book acquisition and reconstruction deferred as a release limitation; order-book-dependent features unsupported in the initial release (per B6)
- Reliability requirements (reconnect, stale, duplicate, out-of-order, incomplete candles, recovery) implemented

---

### Milestone E.4 — Futures risk & paper-simulation requirements (ADR-005/012)

**Files:** `trading_engine/risk/risk_manager.py`, `trading_engine/execution/paper_simulator.py`

**Work (futures-only additions, spot path untouched):**
- Leverage support: position sizing accounts for leverage multiplier (futures path only)
- Initial margin: required margin = notional / leverage; checked against available equity (futures path only)
- Maintenance margin: minimum margin to keep position open (futures path only)
- Liquidation price: computed per position; position auto-closes if mark price breaches liquidation price (futures path only)
- Funding cost: periodic funding payments deducted from position equity (futures path only)
- Mark-price handling: unrealized PnL and liquidation computed on mark price, not last price (futures path only)
- Futures fee schedule: maker/taker BP applied per leg; funding cost tracked separately (futures path only)
- Paper simulator: futures positions valued at mark price; funding applied; liquidation closes position (futures path only)
- **Spot-path protection:** all existing Spot position sizing, PnL, stop-loss/take-profit, and exit logic is preserved unchanged. Futures-specific logic is gated explicitly behind `market_type == 'CRYPTO_PERP'`; Spot and Futures calculations remain in separate code paths with no shared mutable state.

**Dependencies:** E.0 (isolation), E.1 (futures fee/funding constants), E.3 (mark price/funding data streams)

**Tests:** Add `tests/test_phase_e_futures_risk.py` verifying:
- Futures position sizing includes leverage
- Initial margin check rejects position if insufficient equity
- Maintenance margin and liquidation price computed correctly
- Mark-price (not last-price) used for unrealized PnL and liquidation
- Funding cost: applied only when a position is open at the applicable funding timestamp, according to the chosen simulation convention (not an unconditional hardcoded 8-hour schedule; use exchange-provided funding timestamp)
- Spot risk path unchanged (no leverage/margin applied to spot)
- Futures paper simulation produces deterministic results on identical input
- Funding payment direction: long positions pay when funding rate is positive, short positions pay when negative; positions opened/closed around funding time handled per simulation convention

**Acceptance criteria:**
- Spot risk path (no leverage/margin) fully preserved — existing Spot position sizing, PnL, SL/TP, and exit behavior unchanged
- Futures risk: leverage, initial/maintenance margin, liquidation price, funding cost, mark-price valuation implemented
- No cross-contamination: spot positions never charged funding or liquidation rules
- Futures-specific logic gated explicitly behind `market_type == 'CRYPTO_PERP'`; Spot and Futures calculations separate
- Regression tests added against existing Spot behavior (position sizing, PnL, SL/TP, exits)
- 133 baseline tests plus all new Phase E tests pass

---

### Milestone E.5 — Max-5 strategy cap with compatibility & long/short (ADR-010)

**Files:** New strategy registry/manager (e.g., `trading_engine/strategies/strategy_registry.py`)

**Work:**
- Implement registry tracking active approved strategy count globally across Spot and Futures (per B4, not per market_type)
- Both V1 and V2 active approved strategies count toward the same global limit of 5 (per B5)
- Each strategy declares `market_type` compatibility (`CRYPTO_SPOT`, `CRYPTO_PERP`, or both) and `direction` capability (`LONG`, `SHORT`, or `LONG_AND_SHORT`)
- Strategies are market-specific by default (per B7); cross-market compatibility requires explicit client approval
- V1 baselines (ema_breakout_v1, vwap_fvg_v1) declared `CRYPTO_SPOT` + `LONG`-only per their source
- Reject activation beyond the global cap of 5 with clear error
- Reject activation if strategy market_type/direction incompatible with target market (unless cross-market compatibility explicitly approved)

**Dependencies:** E.0 (isolation)

**Tests:** Add `tests/test_phase_e_strategy_cap.py` verifying:
- Activating a 6th strategy globally across Spot and Futures is rejected
- Activating up to 5 total active approved strategies globally succeeds (V1 + V2 counted together)
- Strategy with `CRYPTO_SPOT` only cannot activate on a futures symbol (market-specific by default per B7)
- Cross-market compatibility requires explicit client approval before activation on both universes
- `LONG`-only strategy cannot open SHORT positions
- Clear error when cap exceeded or incompatible

**Acceptance criteria:**
- Max 5 active approved strategies globally across Spot and Futures (per B4), V1 and V2 counted together (per B5)
- Strategies market-specific by default; cross-market compatibility requires explicit client approval (per B7)
- Strategy compatibility (market_type + direction) enforced
- Clear error on cap breach or incompatibility

---

### Milestone E.6 — Phase E test suite & regression of 133-test baseline

**Files:** `trading_engine/tests/test_phase_e_*.py` (new), existing test files untouched

**Work:**
- Consolidate all Phase E tests (isolation contracts, config, scanner, futures WS, futures risk, strategy cap, live-feed reliability)
- Run full `pytest` from repo root
- Verify 133 baseline + new Phase E tests all pass

**Dependencies:** E.0–E.5 complete

**Tests:** All Phase E test files

**Acceptance criteria:**
- `pytest` from repo root: baseline 133 + Phase E tests, all pass
- No test in existing files modified
- Tests verify actual isolation (cross-market_type queries rejected), historical replay (as-of scanner), futures risk calculations (leverage/margin/liquidation/funding/mark-price), and live-data reliability (reconnect/stale/dup/out-of-order/incomplete candles)

---

### Milestone E.7 — Documentation sync

**Files:** `docs/database_and_data_contracts.md`, `docs/master_architecture.md` (if needed), `CHANGELOG.md`

**Work:**
- Document new endpoints, fee schedules, `market_type` enforcement, top-10 scanner, max-5 cap, futures risk, live-feed reliability
- Update data contracts for futures streams and scanner snapshot table
- Record Phase E plan in CHANGELOG (planning entry only — no implementation)

**Dependencies:** E.1–E.6

**Acceptance criteria:**
- Docs reflect planned (not implemented) Phase E components
- Distinction between accepted and proposed ADRs preserved

---

### Phase E milestone dependency order (corrected)

```
E.0 market contracts & isolation (DB PK/indexes, feature-store keys, query filters)
    ↓
E.1 config (futures endpoints + fee/funding constants)
    ↓
E.2 top-10 scanner w/ point-in-time snapshots (independent Spot & Futures universes)
    ↓
E.3 futures WS connector (klines, mark price, funding, metadata + reliability)
    ↓
E.4 futures risk & paper simulation (leverage, margin, liquidation, funding, mark-price)
    ↓
E.5 max-5 strategy cap (market_type + direction compatibility)
    ↓
E.6 test suite + 133 regression
    ↓
E.7 documentation sync
```

**Total Phase E effort (estimate):** 8–12 developer days (planning estimate only, assumes no blockers).

**Exit criteria for Phase E:** All milestones E.0–E.7 complete; `pytest` passes (133 baseline + Phase E tests); client approval to proceed to Phase F.

---

## 4. Phase F Validation and Phase G Live-Signal Delivery Plans

Phase F and Phase G are **planned but not authorized**. They follow Phase E only after client approval. No implementation is authorized for F or G at this time.

---

### Phase F — Validation Gate (candidate strategy promotion)

**Objective:** Run any V2 candidate strategy (rule-based only) through the independent Validation Gatekeeper before promotion; V1 stays active on any failure.

**Scope:** Spot and USDⓈ-M Futures candidates, each validated within its `market_type`.

**Reuses existing infrastructure (no rebuild):**
- `validation/gatekeeper.py` — 4 deterministic tests (OOS 70/30, walk-forward K=5, parameter heatmap 5x5, cost stress 1.5x)
- `evaluation/analyzer.py` — PF, Win Rate, Expectancy, regime breakdown, weakness detection
- `execution/paper_simulator.py` — paper trade lifecycle for OOS/walk-forward simulation
- `memory/trade_logger.py` — trade persistence with MAE/MFE
- `data/feature_store.py` — zero look-ahead features for backtest

**Phase F milestones (planned):**

| # | Milestone | Description |
|---|---|---|
| F.1 | V2 candidate strategy authored (rule-based) | New file in `strategies/candidates/`, inherits `BaseStrategy`, no ML/LLM/RL |
| F.2 | Backtest on spot + futures data | Run candidate through `execution/paper_simulator.py` on historical spot and futures bars, `t <= T` |
| F.3 | Gatekeeper execution | Run `validation/gatekeeper.py` 4 tests; all 4 must PASS for promotion |
| F.4 | Report persisted | Validation report written to `validation_reports` table with `market_type` |
| F.5 | Promotion decision | If all 4 PASS → candidate promoted to `strategies/approved/`; if any fail → V1 stays active, candidate rejected |

**Phase F acceptance criteria:**
- Gatekeeper runs all 4 deterministic tests on candidate
- All 4 PASS required for promotion; any failure → REJECTED, V1 stays active
- Report persisted with `market_type` (spot vs futures isolation)
- No auto-promotion; human review of report before promotion

**Unresolved questions:**
- Does gatekeeper support `market_type` in reports (needs ADR-012 enforcement)?
- Are spot and futures candidates validated separately or together?

---

### Phase G — Live-Signal Delivery (paper trading + manual order ticket)

**Objective:** Deliver live trading signals from approved strategies via paper simulation and the manual order ticket UI. No automatic real-money execution.

**Scope:** Top-10 eligible assets (from ADR-009 scanner), up to 5 active strategies (ADR-010), spot and futures (ADR-001/012 isolation).

**Reuses existing infrastructure (no rebuild):**
- `data/feeds/binance_ws.py` (spot) + `data/feeds/binance_futures_ws.py` (futures, Phase E)
- `execution/paper_simulator.py` — paper position lifecycle, MAE/MFE
- `memory/trade_logger.py` — paper trade persistence, `execution_mode=PAPER_LIVE`
- `backend/server.py` — `POST /api/trades/manual` (human order ticket), `/ws/live` stream
- `frontend/` — TradingView charts, manual order ticket UI

**Phase G milestones (planned):**

| # | Milestone | Description |
|---|---|---|
| G.1 | Live signal generation | Approved strategies evaluate on live WS candles (spot + futures), `t <= T` |
| G.2 | Paper position tracking | `paper_simulator.py` opens/closes paper positions from signals, tracks MAE/MFE |
| G.3 | Manual order ticket | `POST /api/trades/manual` logs human-executed trades with `market_type` |
| G.4 | WebSocket live stream | `/ws/live` streams candles, paper positions, status badges, manual tickets |
| G.5 | Frontend display | Browser at `http://127.0.0.1:8765` shows live charts, paper trades, manual tickets |

**Phase G acceptance criteria:**
- Signals generated only from approved strategies (max 5, rule-based)
- Paper trading only; no automatic real-money execution
- Human executes broker orders manually via manual order ticket
- Spot/futures isolation preserved in live streams and tickets
- Zero look-ahead: all signals use `t <= T`

**Hard constraint (binding):** No automatic real-money order execution. Human is responsible for all trading decisions. Paper trade first, then manual execution only.

---

## 5. Final Readiness Report, Blockers, External Requirements, and Timeline

---

### 5.1 Readiness summary

| Area | Readiness | Notes |
|---|---|---|
| Codebase foundation (Phases 1–6) | **Ready** | 133 tests pass; all layers implemented |
| Accepted ADRs (001–008) | **Implemented** | Binding constraints preserved |
| Proposed ADRs (009–012) | **Not implemented** | Specified only; KI-005 open |
| Phase E blueprint | **This document** | Planning only; no implementation authorized |
| Client approval for Phase E | **Pending** | Required before any implementation |
| External dependencies (Binance API) | **Available** | Public REST/WS endpoints; no API key needed for public market data |
| Python environment | **Verified** | `pyproject.toml` and root `requirements.txt` exist (KI-006 resolved); `trading_engine.db` SQLite WAL exists |

### 5.2 Milestone Prerequisites and Remaining Client Decisions

B1–B8 are resolved (see table below). B9 authorizes E.0 only; E.1–E.7 require separate client approval before each milestone begins.

| Blocker | ADR | Description | Resolution owner |
|---|---|---|---|
| B1 | ADR-009 | RESOLVED — Independent Spot and Futures universes; USDT-quoted only; minimum liquidity thresholds configurable and separate by market type (initial numeric values require client confirmation before E.2); exclude leveraged tokens | Client (approved B1) |
| B2 | ADR-009 | RESOLVED — Scanner refresh both universes every 5 minutes with explicit, configurable entry/exit policy for controlled membership changes (hysteresis parameter values require client confirmation before E.2) | Client (approved B2) |
| B3 | ADR-009 | RESOLVED — Symbol leaving top 10: stop new entries; existing positions remain monitored normally | Client (approved B3) |
| B4 | ADR-010 | RESOLVED — Max 5 active approved strategies globally across Spot and Futures (not per market_type); sixth-strategy activation rejected with clear validation error; no existing strategy silently disabled or replaced | Client (approved B4, B5) |
| B5 | ADR-010 | RESOLVED — Both V1 and V2 active approved strategies count toward the same global limit of 5 | Client (approved B5) |
| B6 | ADR-011 | RESOLVED — Initial Futures data: klines, mark price, actual funding rates, instrument metadata; order-book acquisition and reconstruction deferred as a release limitation from the initial release | Client (approved B6) |
| B7 | ADR-012 | RESOLVED — Strategies market-specific by default; cross-market compatibility requires explicit per-strategy client approval before activation on both universes | Client (approved B7) |
| B8 | ADR-012 | RESOLVED — Separate Spot and Futures fee models; observed funding rates with exchange-provided timestamps | Client (approved B8) |
| B9 | — | Client approval to begin Phase E milestone E.0 only (market contracts & isolation foundation). E.1–E.7 NOT authorized; require separate client approval before each | Client |

### 5.3 External requirements

| Requirement | Detail |
|---|---|
| Binance public market data | REST `/api/v3/ticker/24hr` (spot), `/fapi/v1/ticker/24hr` (futures); WS `wss://stream.binance.com:9443/ws` (spot), `wss://fstream.binance.com/ws` (futures) |
| No API key required | Public market data endpoints do not require authentication for implementation planning |
| Python dependencies | `pandas`, `numpy`, `pandas-ta`, `scipy`, `websockets`, `pyarrow` (optional), `pytest` — see `pyproject.toml` / root `requirements.txt` |
| Network access | Outbound HTTPS/WSS to `api.binance.com`, `stream.binance.com`, `fapi.binance.com`, `fstream.binance.com` |
| SQLite WAL | `trading_engine.db` exists; WAL mode already configured |

### 5.4 Realistic timeline (planning estimates only)

| Phase | Estimate | Dependencies | Gate |
|---|---|---|---|
| Phase E implementation | 8–12 dev days | Client approval; B1–B9 resolved; each milestone E.0–E.7 requires its own client approval gate — this estimate is planning only, not blanket authorization for all milestones | `pytest` passes (133 + Phase E tests) |
| Phase F validation | 3–5 dev days | Phase E complete; V2 candidate authored | All 4 gatekeeper tests PASS |
| Phase G live signals | 3–5 dev days | Phase F promotion; client approval | Paper trading only; no auto real execution |

**Total (E+F+G):** ~11–18 dev days, sequential, assuming no blockers and client approval at each gate.

**Critical path:** Client approval → E.0–E.7 → pytest green → client approval → F.1–F.5 → client approval → G.1–G.5.

### 5.5 Assumptions (explicitly stated, not invented)

1. Binance public market data endpoints remain available and unchanged during implementation.
2. No API key is required for public ticker/kline WS streams (implementation planning assumption; to be confirmed if rate limits apply).
3. `pyproject.toml` and root `requirements.txt` already list all needed dependencies (KI-006 resolved).
4. `trading_engine.db` SQLite WAL database is available and writable.
5. All Phase E work occurs on branch `audit/planning-finceptengine-transformation`, not on `dev` or `main`.
6. No commits, pushes, or merges occur without explicit client approval.
7. The 133-test baseline (Phases 1–6) remains the regression baseline; Phase E adds new tests without modifying existing ones.

### 5.6 Unresolved questions (not invented — flagged for client decision)

- Q1: Top-10 scanner eligibility — **RESOLVED by B1**: USDT-quoted only; exclude leveraged/tokens. **Numeric minimum 24h quote volume threshold per market type remains pending client confirmation before E.2 implementation** — do not invent values.
- Q2: Scanner refresh frequency — **RESOLVED by B2**: every 5 minutes; controlled membership changes via explicit, configurable entry/exit policy. **Hysteresis/entry-exit parameter values remain pending client confirmation before E.2 implementation** — do not invent values.
- Q3: Open positions when symbol drops out of top 10 — **RESOLVED by B3**: stop new entries; existing positions remain monitored normally.
- Q4: Max-5 cap scope — **RESOLVED by B4**: global across Spot and Futures (not per market_type).
- Q5: Cap counting V1 + V2 — **RESOLVED by B5**: both count toward the same global limit of 5.
- Q6: Market_type-specific vs cross-market — **RESOLVED by B7**: strategies market-specific by default; cross-market compatibility requires explicit per-strategy client approval before activation on both universes.
- Q7: Futures fee schedule and funding — **RESOLVED by B8**: separate Spot and Futures fee models; observed funding rates with exchange-provided timestamps.
- Q8: Gatekeeper validation `market_type`-separated reports — **RESOLVED by ADR-012**: `validation_reports` gains `market_type` column; reports persisted per market_type.
- Q9: Order book depth streams needed for futures risk model? — **DEFERRED**: order-book acquisition and reconstruction deferred as a release limitation from the initial release (per B6); order-book-dependent features unsupported initially.
- Q10: Client approval timeline for each phase gate. — B9 approves E.0 only; E.1–E.7 require separate client approval before each milestone begins.

---

### 5.7 Conclusion

The FinceptEngine codebase (Phases 1–6, 133 tests passing) provides a solid foundation for the Binance Spot + USDⓈ-M Futures transformation. Phase E requires implementing four proposed ADRs (009–012) plus supporting config, tests, and documentation. All accepted ADRs (001–008) remain binding constraints. B1–B8 have been resolved. B9 authorizes E.0 only. E.1–E.7 require separate client approval before implementation. Numeric liquidity thresholds and scanner hysteresis parameters remain pending client confirmation before E.2.

**File:** `docs/PHASE_E_IMPLEMENTATION_BLUEPRINT.md`  
**Status:** Planning complete. STOP — no implementation, commit, push, or merge.

