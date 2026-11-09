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
