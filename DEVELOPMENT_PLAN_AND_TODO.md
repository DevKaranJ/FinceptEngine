# Development Plan & To-Do — FinceptEngine

**Project:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Version:** v0.1.0 (Project Initiation Baseline)  
**Status:** Active  
**Tracker Rule:** Updated at the start and end of every task across four sections: COMPLETED & VERIFIED, IN PROGRESS, REMAINING BACKLOG, NEWLY ADDED / DISCOVERED.

---

## [x] COMPLETED & VERIFIED

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1 | Read all 6 documentation files in `docs/` (master_architecture, prd_and_roadmap, database_and_data_contracts, strategy_and_validation_spec, AGENTS, readme.md) | Architect | Done | Full audit complete — no source code existed yet |
| 2 | Inspect directory tree — confirmed root has only `.git/`, `docs/`, `readme.md`; no Python package or manifests exist | Architect | Done | Confirmed empty-codebase baseline |
| 3 | Scaffold `trading_engine/` package with all 16 subdirectories per MASTER_ARCHITECTURE.md Section 3 | Architect | Done | data/, indicators/, signals/, strategies/, risk/, execution/, memory/, evaluation/, agents/, validation/, backend/, frontend/, tests/ plus feeds/, approved/, candidates/, js/, css/ |
| 4 | Add clean `__init__.py` to every Python package directory (18 files) | Architect | Done | `trading_engine/__init__.py` sets `__version__ = "0.1.0"` |
| 5 | Multi-agent governance initiation (Project Initiation, Codebase Audit, Directory Scaffolding, Governance File creation) | All 5 agents | Done | Steps 1–3 of the Master Prompt |

---

## [/] IN PROGRESS (CURRENT SPRINT)

| # | Task | Owner | Notes |
|---|------|-------|-------|
| 1 | Embed permanent 5-rule governance into root `AGENTS.md` (and `.opencode/` rules if needed) | Architect + Reviewer | Drafting now |
| 2 | Create `DEVELOPMENT_PLAN_AND_TODO.md` with Phase 1–6 breakdown | Architect | Drafting now |
| 3 | Create `CHANGELOG.md` with initial v0.1.0 entry | Architect + QA | Drafting now |
| 4 | Create `PEER_REVIEW_LOG.md` with Review #001 | Reviewer | Drafting now |

---

## [ ] REMAINING BACKLOG (BY PHASE)

### Pre-Phase (Governance)
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| G1 | Client review & approval of `DEVELOPMENT_PLAN_AND_TODO.md` (hard stop gate — no Phase 1 code until approved) | Client | Initiation | **HARD STOP GATE — awaiting client green light** |

### Phase 1: Core Data Feed, Clock & SQLite Trade Memory
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 1.1 | Create `config.py` — market sessions (UTC 24/7 Crypto, IST NSE 09:15–15:30), fee/slippage schedules, risk constants | Backend | Phase 1 | Per PRD FR-01 |
| 1.2 | Create `requirements.txt` — FastAPI, uvicorn, pandas, numpy, pandas-ta, scipy, websockets, pytest | Backend | Phase 1 | No `pip install` until manifests exist (AGENTS.md constraint) |
| 1.3 | Create `data/clock.py` — Session manager for UTC & IST market windows | Backend | Phase 1 | |
| 1.4 | Create `data/feeds/binance_ws.py` — Live 24/7 Crypto Spot & USDT-M WebSocket + REST backfill | Backend | Phase 1 | BTCUSDT, ETHUSDT, SOLUSDT top pairs |
| 1.5 | Create `memory/db.py` — SQLite WAL schema: ohlcv_bars, trades_memory, strategy_registry, validation_reports, system_activity_log | Backend | Phase 1 | Per DATABASE_AND_DATA_CONTRACTS.md Section 1 |
| 1.6 | Create `tests/test_phase1_data_db.py` — deterministic pytest suite | QA | Phase 1 | Verify live Binance WS ingestion + SQLite WAL table creation |
| 1.7 | Run `pytest tests/test_phase1_data_db.py` — verify pass, then STOP (Phase 1 hard stop gate) | QA + Reviewer | Phase 1 | Client approval required before Phase 2 |

### Phase 2: Multi-Paradigm Lego Indicators & Signals
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 2.1 | Create `data/feature_store.py` — SQLite + Parquet feature caching (zero look-ahead) | Backend | Phase 2 | |
| 2.2 | Create `indicators/technical.py` — Family A: EMA, SMA, RSI, ATR, Bollinger, MACD, Supertrend, Pivots | Backend | Phase 2 | Zero look-ahead enforcement |
| 2.3 | Create `indicators/statistical.py` — Family B: Rolling Z-Score, Hurst, Vol Percentile, Reg Slope, RS | Backend | Phase 2 | |
| 2.4 | Create `indicators/structure.py` — Family C: PDH/PDL/PDC, ORB, Trendlines, FVG, Order Blocks, Liquidity Sweeps | Backend | Phase 2 | |
| 2.5 | Create `indicators/orderflow.py` — Family D: VWAP, RVOL, Volume Profile POC/VAH/VAL, CVD, Footprint, Iceberg | Backend | Phase 2 | |
| 2.6 | Create `signals/technical_signals.py`, `statistical_signals.py`, `structure_signals.py`, `orderflow_signals.py` | Backend | Phase 2 | Reusable True/False conditions |
| 2.7 | Create `tests/test_phase2_indicators_signals.py` — verify math + zero look-ahead leakage | QA | Phase 2 | |
| 2.8 | Run pytest — verify pass, then STOP (Phase 2 hard stop gate) | QA + Reviewer | Phase 2 | |

### Phase 3: Strategy Builder (V1), Risk Manager & Paper Simulator
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 3.1 | Create `strategies/base_strategy.py` — abstract interface | Backend | Phase 3 | Per STRATEGY_AND_VALIDATION_SPEC.md |
| 3.2 | Create `strategies/approved/ema_breakout_v1.py` — baseline V1 | Backend | Phase 3 | Never overwrite V1 |
| 3.3 | Create `strategies/approved/vwap_fvg_v1.py` — baseline V1 | Backend | Phase 3 | |
| 3.4 | Create `risk/risk_manager.py` — position sizing, ATR stop buffer, slippage pad, daily circuit breaker | Backend | Phase 3 | |
| 3.5 | Create `execution/paper_simulator.py` — tick-by-tick MAE/MFE tracking, slippage/commission deduction | Backend | Phase 3 | |
| 3.6 | Create `memory/trade_logger.py` — persist trades with MAE/MFE, regime & signal snapshots | Backend | Phase 3 | |
| 3.7 | Create `tests/test_phase3_execution_memory.py` — full paper trade lifecycle | QA | Phase 3 | |
| 3.8 | Run pytest — verify pass, then STOP (Phase 3 hard stop gate) | QA + Reviewer | Phase 3 | |

### Phase 4: Backtester, Evaluation Engine & Validation Gatekeeper
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 4.1 | Create `validation/backtester.py` — fast vectorized & event-driven backtest engine | Backend | Phase 4 | |
| 4.2 | Create `evaluation/analyzer.py` — Performance/Risk/Regime breakdown + Weakness JSON report | Backend | Phase 4 | |
| 4.3 | Create `validation/gatekeeper.py` — OOS split, Walk-Forward, Parameter Heatmap, Approve/Reject | Backend | Phase 4 | Never let AI self-approve |
| 4.4 | Create `tests/test_phase4_eval_validation.py` — weakness detection + gatekeeper logic | QA | Phase 4 | |
| 4.5 | Run pytest — verify pass, then STOP (Phase 4 hard stop gate) | QA + Reviewer | Phase 4 | |

### Phase 5: The 4 AI Research Agents (Self-Improvement Loop)
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 5.1 | Create `agents/research_loop.py` — Research → Hypothesis → Coding V2 → Review pipeline | Backend | Phase 5 | Gemini / OpenRouter |
| 5.2 | Create `tests/test_phase5_research_agents.py` — end-to-end candidate generation + gating | QA | Phase 5 | |
| 5.3 | Run pytest — verify pass, then STOP (Phase 5 hard stop gate) | QA + Reviewer | Phase 5 | |

### Phase 6: FastAPI Backend & Unified Dark-Mode Terminal UI
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 6.1 | Create `backend/server.py` — FastAPI REST + WebSocket hub | Backend | Phase 6 | `http://127.0.0.1:8765` |
| 6.2 | Create `execution/alert_dispatcher.py` — 1-Click Manual Order Ticket + audio/Telegram alerts | Backend | Phase 6 | |
| 6.3 | Create `frontend/index.html`, `frontend/css/styles.css`, `frontend/js/*.js` | Frontend | Phase 6 | TradingView Lightweight Charts |
| 6.4 | Full end-to-end launch verification in browser, zero console errors | Frontend + QA | Phase 6 | **COMPLETE** |

---

## [+] NEWLY ADDED / DISCOVERED ITEMS

| Date | Item | Reason | Owner |
|------|------|--------|-------|
| 2026-11-08 | Root-level `AGENTS.md` missing — created new one embedding the 5 mandatory governance rules | Governance requirement from Master Prompt Step 2 | Architect + Reviewer |
| 2026-11-08 | `readme.md` exists at root (lowercase) but no `README.md` — no duplicate created to avoid confusion | Project has lowercase readme; kept as-is | Architect |
| 2026-11-08 | `DEVELOPMENT_PLAN_AND_TODO.md`, `CHANGELOG.md`, `PEER_REVIEW_LOG.md` created as new governance artifacts | Governance requirement from Master Prompt Step 3 | Architect + QA + Reviewer |

---

**Execution Rule:** No Phase 1 Python application logic (`binance_ws.py`, `db.py`) is to be written until the Client reviews and approves this `DEVELOPMENT_PLAN_AND_TODO.md`.
