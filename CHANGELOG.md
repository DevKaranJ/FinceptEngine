# Changelog — FinceptEngine

**Project:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Format:** Keep a Changelog — entries are timestamped and logged before each turn ends.

---

## [v0.1.0] — 2026-11-08 — Project Initiation, Architecture Baseline & Multi-Agent Governance Setup

**Agent Roles Involved:** Architect, Backend, QA, Reviewer  
**Phase:** Project Initiation (Pre-Phase 1)

### Added Files (Post-Commit Hotfix)
| File | Purpose |
|------|---------|
| `.gitignore` | Excludes Python bytecode (__pycache__, *.pyc), venv/.env, SQLite DB (`trading_engine.db`), Parquet caches, pytest cache/coverage, IDE dirs (.vscode/.idea), OS files (.DS_Store), logs/ |

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/__init__.py` | Package root, `__version__ = "0.1.0"` |
| `trading_engine/data/__init__.py` | Layer 1 — Market Data & Feature Store |
| `trading_engine/data/feeds/__init__.py` | Data feed connectors (binance_ws, nse_broker_ws) |
| `trading_engine/indicators/__init__.py` | Layer 1B — Multi-paradigm Lego indicators |
| `trading_engine/signals/__init__.py` | Layer 2A — True/False trigger & filter building blocks |
| `trading_engine/strategies/__init__.py` | Layer 2B — Versioned strategy recipes |
| `trading_engine/strategies/approved/__init__.py` | Active validated baseline strategies (V1) |
| `trading_engine/strategies/candidates/__init__.py` | AI-generated candidate strategies (V2+) |
| `trading_engine/risk/__init__.py` | Layer 2C — Universal risk & position sizing |
| `trading_engine/execution/__init__.py` | Layer 2D & 6 — Paper simulator & manual order ticket |
| `trading_engine/memory/__init__.py` | Layer 3 — Data & trade memory engine |
| `trading_engine/evaluation/__init__.py` | Layer 4 — Evaluation & weakness detection |
| `trading_engine/agents/__init__.py` | Layer 5 — AI self-improvement agent loop |
| `trading_engine/validation/__init__.py` | Layer 6 — Independent robustness & approval gate |
| `trading_engine/backend/__init__.py` | FastAPI server & WebSocket hub |
| `trading_engine/frontend/__init__.py` | Dark-mode terminal UI assets |
| `trading_engine/frontend/js/__init__.py` | Frontend JavaScript modules |
| `trading_engine/frontend/css/__init__.py` | Frontend CSS stylesheets |
| `trading_engine/tests/__init__.py` | Deterministic pytest verification suite |
| `AGENTS.md` (root) | Multi-agent command/constraint summary with embedded 5 governance rules |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Live granular tracker (4 sections: COMPLETED, IN PROGRESS, BACKLOG, NEWLY ADDED) |
| `CHANGELOG.md` | Production changelog (this file) |
| `PEER_REVIEW_LOG.md` | Mandatory internal peer review log (Review #001+) |

### Modified Files
| File | Change |
|------|--------|
| `AGENTS.md` (root) | Created — did not previously exist at root; embeds the 5 mandatory real-world engineering governance rules (Read-Before-Act, Vice-Versa Doc Sync, DEVELOPMENT_PLAN_AND_TODO.md, CHANGELOG.md, PEER_REVIEW_LOG.md) |

### Removed Files
- None

### Why the Change Was Made
Initial project initiation per the Master Prompt: audit codebase & documentation, scaffold the `trading_engine/` folder skeleton matching `MASTER_ARCHITECTURE.md` Section 3, embed permanent governance into `AGENTS.md`, and create the 3 live project governance files. No Phase 1 Python application logic was written (scope boundary respected — hard stop at governance creation).

## [v0.1.1] — 2026-11-09 — Phase 1: Core Data Feed, Clock & SQLite Trade Memory

**Agent Roles Involved:** Backend, QA  
**Phase:** Phase 1 (branch: `phase1/core-data-memory`)  
**Branch:** `phase1/core-data-memory` (from `dev`)

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/config.py` | Market sessions (UTC 24/7 Crypto, IST NSE 09:15–15:30), fee/slippage schedules, risk constants (PRD FR-01) |
| `trading_engine/requirements.txt` | Phase 1 manifest: FastAPI, uvicorn, pandas, numpy, pandas-ta, scipy, websockets, pytest |
| `trading_engine/data/clock.py` | `MarketSession` — crypto 24/7, NSE IST window, bar alignment, session reset/open boundaries |
| `trading_engine/data/feeds/binance_ws.py` | `BinanceFeed` — live 24/7 Crypto Spot WebSocket + REST `/api/v3/klines` backfill; zero-look-ahead persist-on-close |
| `trading_engine/memory/db.py` | SQLite WAL schema: `ohlcv_bars`, `trades_memory`, `strategy_registry`, `validation_reports`, `system_activity_log` + `log_activity()` |
| `trading_engine/tests/test_phase1_data_db.py` | Deterministic pytest suite: schema, WAL mode, PK enforcement, clock logic, bar normalization, DB roundtrip |

### Modified Files
| File | Change |
|------|--------|
| `DEVELOPMENT_PLAN_AND_TODO.md` | Phase 1 tasks 1.1–1.7 moved to COMPLETED & VERIFIED; IN PROGRESS cleared awaiting client gate |
| `PEER_REVIEW_LOG.md` | Review #002 added (Phase 1 code review) |

### Removed Files
- None

### Why the Change Was Made
Implement PRD Phase 1 deliverables: market data pipeline (Binance WS + REST backfill), session clock (UTC & IST), and SQLite WAL trade memory foundation. All five database tables match `DATABASE_AND_DATA_CONTRACTS.md` Section 1 exactly.

### Test & Verification Status
- **`pytest`**: **22/22 passed** (`pytest trading_engine/tests/test_phase1_data_db.py -v`, 2026-11-09) on branch `phase1/core-data-memory`.
  - Installed via virtual environment: `python3 -m venv .venv && source .venv/bin/activate && pip install pytest websockets numpy`
  - Remaining manifest packages (pandas, fastapi, uvicorn, scipy, pandas-ta) could not install — network read timeouts in this environment. They are **not required for Phase 1** (only stdlib + websockets used).
- All Phase 1 modules import cleanly; `config.py`, `data/clock.py`, `data/feeds/binance_ws.py`, `memory/db.py`, and the test suite are fully functional.

## [v0.1.2] — 2026-11-09 — Phase 2: Multi-Paradigm Lego Indicators & Signals

**Agent Roles Involved:** Backend, QA, Reviewer  
**Phase:** Phase 2 (branch: `phase1/core-data-memory`, uncommitted)  

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/data/feature_store.py` | SQLite + Parquet feature cache; `write_features`/`load_features` with zero-look-ahead `timestamp` slice + `zero_look_ahead_slice()` helper |
| `trading_engine/indicators/technical.py` | Family A: EMA, SMA, RSI, ATR, Bollinger Bands, MACD, Supertrend, Donchian Channels, Pivots |
| `trading_engine/indicators/statistical.py` | Family B: Rolling Z-Score, Hurst Exponent, Volatility Percentile, Linear Regression Slope, Relative Strength |
| `trading_engine/indicators/structure.py` | Family C: PDH/PDL/PDC, Opening Range, Dynamic Trendlines, FVG, Order Blocks, Liquidity Sweeps |
| `trading_engine/indicators/orderflow.py` | Family D: VWAP, VWAP bands, RVOL, Session Volume Profile (POC/VAH/VAL), CVD, Footprint Imbalance, Iceberg Detector |
| `trading_engine/signals/technical_signals.py` | Family A boolean signal wrappers (EMA cross, RSI, ATR filter, Bollinger touch, Supertrend, Donchian breakout) |
| `trading_engine/signals/statistical_signals.py` | Family B boolean signal wrappers (Z-score, Hurst regime, volatility regime, slope, RS) |
| `trading_engine/signals/structure_signals.py` | Family C boolean signal wrappers (PDH/PDL, ORB breakout, FVG retest, OB test, liquidity sweep, trendline touch/break) |
| `trading_engine/signals/orderflow_signals.py` | Family D boolean signal wrappers (VWAP above/below, POC/VAH/VAL, RVOL threshold, CVD rising/falling, footprint imbalance, iceberg) |
| `trading_engine/tests/test_phase2_indicators_signals.py` | Full Phase 2 verification suite: indicator math + zero look-ahead + signal wrappers |

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/tests/test_phase2_indicators_signals.py` | Fixed `test_donchian_breakout`: first call now sets `prev.high > prev.donchian_upper` so no false breakout on an already-breached channel; second call confirms genuine breakout → `True` |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Phase 2 tasks moved to COMPLETED & VERIFIED; IN PROGRESS cleared awaiting client gate; backlog gated behind Phase 2 |
| `CHANGELOG.md` | This entry |
| `PEER_REVIEW_LOG.md` | Review #003 added (Phase 2 code review) |

### Removed Files
- None

### Why the Change Was Made
Implement PRD Phase 2 deliverables: all four indicator families (technical/statistical/structure/orderflow), corresponding boolean signal wrappers, and the zero-look-ahead feature store. Pure pandas/numpy implementations for deterministic, version-independent behavior. Zero look-ahead enforced (t <= T) across all indicators via `shift(1)` for previous-bar references and calendar-day grouping for PDH/PDL/PDC.

### Test & Verification Status
- **`pytest`**: **61/61 passed** (`pytest trading_engine/tests/test_phase2_indicators_signals.py -v`, 2026-11-09).
- Zero look-ahead enforcement verified: future-bar changes do not alter outputs at time T for EMA, RSI, PDH/PDL/PDC, VWAP, and HMA.
- All Phase 2 modules import cleanly; no look-ahead leakage detected.
- **Phase 2 hard stop gate: PASSED.** Awaiting client approval before Phase 3.

---

## [v0.1.5] — 2026-11-09 — Phase 3: Strategy Builder V1, Risk Manager & Paper Simulator

**Agent Roles Involved:** Backend, QA, Reviewer  
**Branch:** `dev`  

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/strategies/base_strategy.py` | Abstract `BaseStrategy` interface + Contract A signal dict (`strategy_id`, `symbol`, `timeframe`, `timestamp_utc`, `direction`, `entry_price`, `stop_loss_raw`, `target_1_raw`, `target_2_raw`, `active_signals`, `regime_snapshot`) |
| `trading_engine/strategies/approved/ema_breakout_v1.py` | Baseline V1: EMA breakout long — EMA cross trigger + bullish trend alignment + ATR expansion filter (inline rolling SMA) + HMA bias; ATR stop + R:R targets |
| `trading_engine/strategies/approved/vwap_fvg_v1.py` | Baseline V1: VWAP + FVG mean-reversion long — above VWAP + value area + bullish FVG retest + bullish OB test; ATR stop floored at FVG bottom + R:R targets |
| `trading_engine/risk/risk_manager.py` | Universal risk governance — position sizing from equity & max risk %, ATR-buffered stop, slippage & commission cost deduction, daily loss circuit breaker, consecutive-loss breaker, max-drawdown kill-switch, R:R validation |
| `trading_engine/memory/trade_logger.py` | Persist trades with MAE/MFE, regime & signal snapshots — open trade (OPEN), tick-by-tick MAE/MFE update, close trade (CLOSED) with gross/net PnL & R-multiple, SQLite WAL `trades_memory` persistence |
| `trading_engine/execution/paper_simulator.py` | Event-driven paper simulator — accepts `BaseStrategy.evaluate()` signals, risk-managed sizing (`RiskManager`), tick-by-tick MAE/MFE tracking, stop-loss/take-profit exits, slippage + commission deduction on entry & exit, equity curve, summary report |
| `trading_engine/tests/test_phase3_execution_memory.py` | Full Phase 3 verification suite — BaseStrategy Contract A, both V1 strategies, RiskManager, TradeLogger, PaperSimulator end-to-end paper trade lifecycle |

### Modified Files
| File | Change |
|------|--------|
| `DEVELOPMENT_PLAN_AND_TODO.md` | Phase 3 moved to COMPLETED & VERIFIED; IN PROGRESS cleared awaiting client gate; Phase 4–6 backlog gated behind Phase 3 |

### Removed Files
- None

### Why the Change Was Made
Implement PRD Phase 3 deliverables: versioned strategy builder (two baseline V1 strategies), universal risk manager with circuit breakers, and an event-driven paper simulator with tick-by-tick MAE/MFE tracking and slippage/commission deduction. Zero look-ahead enforced (t <= T) across all strategies/risk/execution code. ATR volatility filter computed inline (rolling SMA of ATR up to current bar) since no `atr_sma_*` column exists in indicators. Paper trade first — strategies go historical backtest → live paper → manual real order ticket.

### Test & Verification Status
- **`pytest`**: **24/24 passed** (`pytest trading_engine/tests/test_phase3_execution_memory.py -v`, 2026-11-09).
- No regressions: Phase 1 (`test_phase1_data_db.py`) **22/22 passed**; Phase 2 (`test_phase2_indicators_signals.py`) **61/61 passed**; combined **83/83 passed**.
- **Phase 3 hard stop gate: PASSED.** STOPPED — awaiting client approval before Phase 4.

---

## [v0.1.6] — 2026-11-11 — Phase 4: Backtester, Evaluation Engine & Validation Gatekeeper

**Agent Roles Involved:** Backend, QA  
**Phase:** Phase 4 (branch: `phase4/backtest-eval-validation`, uncommitted)  
**Branch:** `phase4/backtest-eval-validation` (from `dev`)  

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/validation/backtester.py` | Event-driven historical backtester — replays bars bar-by-bar through `BaseStrategy.evaluate()` (Contract A), simulates SL/TP/TIME exits on current-bar OHLC only (zero look-ahead), deducts slippage+commission per leg, persists trades to `trades_memory` via `TradeLogger`, returns `BacktestResult` (trades + equity curve + summary metrics). Opens fresh `TradeLogger`/`RiskManager` per `run()` for determinism/re-entrancy. |
| `trading_engine/evaluation/analyzer.py` | Evaluation engine — `compute_performance` (win rate, PF, expectancy R, gross/net PnL), `compute_risk` (max drawdown, VaR/CVaR 95%), `compute_regime_breakdown`, `detect_weaknesses` (structured Weakness Detection JSON: NEGATIVE_EXPECTANCY, LOW_PROFIT_FACTOR, LOW_WIN_RATE, LOSING_REGIMES, STOPS_TOO_TIGHT, HIGH_COST_DRAG, HIGH_DRAWDOWN), `weakness_report_json`. All deterministic (t <= T). |
| `trading_engine/validation/gatekeeper.py` | Independent Validation Gatekeeper — 4 tests required for APPROVED (any failure → REJECTED, V1 stays active): (1) OOS 70/30 split PF≥1.25 & ER>baseline & MaxDD≤baseline; (2) Walk-Forward K=5 ≥80% windows ER>0; (3) Parameter Sensitivity Heatmap 5×5 ≥80% cells PF>1.10; (4) Cost Stress 1.5× slippage PF≥1.15 & ER≥+0.12R. Report persisted to SQLite `validation_reports`. Never lets AI self-approve. |
| `trading_engine/tests/test_phase4_eval_validation.py` | Full Phase 4 verification suite — backtester (runs/records/persists/zero-look-ahead/flat-close/summary), analyzer (performance/risk/regime/weakness/JSON), gatekeeper (approves profitable, rejects losing, cost-stress rejects/no self-approval). |

### Modified Files
| File | Change |
|------|--------|
| `DEVELOPMENT_PLAN_AND_TODO.md` | Phase 4 tasks 47–51 moved to COMPLETED & VERIFIED (14/14 passed); IN PROGRESS cleared, STOPPED at Phase 4 hard stop gate awaiting client approval |
| `PEER_REVIEW_LOG.md` | Review #004 added (Phase 4 code review) |
| `CHANGELOG.md` | This entry |

### Removed Files
- None

### Why the Change Was Made
Implement PRD Phase 4 deliverables: historical event-driven backtester mirroring `PaperSimulator` semantics (re-entrant, returns `BacktestResult`), evaluation engine with weakness detection, and the independent 4-test validation gatekeeper that must pass before any V2 candidate promotion. Zero look-ahead enforced (t <= T) across backtester exits, MAE/MFE, analyzer metrics, and gatekeeper splits. Paper trade first principle: historical backtest → live paper → manual real order ticket.

### Test & Verification Status
- **`pytest`**: **14/14 passed** (`pytest trading_engine/tests/test_phase4_eval_validation.py -q`, 2026-11-11).
  - Backtester: 4/4 — runs & records trades, zero look-ahead, flat close at end, summary structure
  - Analyzer: 7/7 — compute_performance (basic + empty), compute_risk/drawdown, regime breakdown, detect_weaknesses (negative expectancy + losing regime), weakness_report_json valid JSON
  - Gatekeeper: 3/3 — approves profitable candidate (APPROVED, all 4 tests pass), rejects losing candidate (REJECTED), cost-stress rejects (REJECTED, COST_STRESS_FAILED — no self-approval)
- All Phase 4 modules import cleanly; no look-ahead leakage detected.
- **Phase 4 hard stop gate: PASSED.** STOPPED — awaiting client approval before Phase 5.

---

## [v0.1.4] — 2026-11-09 — Added HMA Indicator + Signal Wrappers + Tests

**Agent Roles Involved:** Backend, QA  
**Branch:** `phase1/core-data-memory` (uncommitted)

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/indicators/technical.py` | Added `hma()` function (Hull Moving Average) + added to `__all__` |
| `trading_engine/signals/technical_signals.py` | Added `price_above_hma()` and `price_below_hma()` signal wrappers + added to `__all__` |
| `trading_engine/tests/test_phase2_indicators_signals.py` | Added `test_hma_basic`, `test_hma_zero_look_ahead`, `test_hma_signals`; updated imports |

### Why the Change Was Made
Demonstrated how to add a new indicator to an existing family file (technical.py) following the contribution guide in `docs/contributing_indicators.md`. HMA is a popular trend indicator not previously in the project. Added matching boolean signal wrappers and tests covering basic math, zero look-ahead, and signal True/False behavior.

### Test & Verification Status
- **`pytest`**: **61/61 passed** (58 original + 3 new HMA tests).

---

## [v0.1.3] — 2026-11-09 — pandas-ta Installed + Indicator Contribution Guide

**Agent Roles Involved:** Backend, QA  
**Branch:** `phase1/core-data-memory` (uncommitted)

### Added Files
| File | Purpose |
|------|---------|
| `docs/contributing_indicators.md` | Step-by-step guide for adding new indicators to any of the 4 families (technical/statistical/structure/orderflow) + matching signal wrappers + zero-look-ahead rules + testing checklist |

### Modified Files
| File | Change |
|------|--------|
| `docs/contributing_indicators.md` | Created — indicator contribution documentation |

### Why the Change Was Made
`pandas-ta` (130+ indicators) is already installed in `.venv` and listed in `trading_engine/requirements.txt`. Added documentation so contributors know how to add more indicators without mixing families into one file, how to use `pandas-ta` alongside pure-pandas implementations, and how to enforce the mandatory zero-look-ahead rule (`t <= T`).

### Test & Verification Status
- `pandas-ta` imports cleanly in the `.venv` (pandas 3.1.1, numpy 2.2.6).
- No new code changes required — installation verified, documentation added only.
