# PROJECT_AUDIT.md — Phase A Codebase Audit

**Project:** FinceptEngine — Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Branch:** `audit/planning-finceptengine-transformation` (created from `dev`, no commits yet)  
**Audit Phase:** Phase A — Codebase audit (completed); Phase B documentation cleanup (completed); Phase C planning & research (in progress)  
**Audit Date:** 2026-11-24  
**Auditor:** OpenCode Agent (Architect role)

---

## 1. Executive Summary

FinceptEngine is a complete, working v0.1.0 implementation of a modular, strategy-agnostic trading engine spanning Phases 1–6. All six phases are implemented, tested via `pytest`, and verified against their hard stop gates. Phase 6 (FastAPI backend + frontend UI) is committed to `phase6/fastapi-backend-ui` and pushed to origin but **NOT merged to `dev`** — awaiting explicit client approval (AGENTS.md Rule 6).

The codebase is internally consistent: all documentation/data-contract files exist, every route in `server.py` matches `docs/database_and_data_contracts.md` Section 3 exactly, and all phase test suites pass (22/22, 64/64, 24/24, 14/14, 9/9 — 133 total) — Phase 2 now 64/64 (63 prior + 1 new Antigravity C1 regression test `test_opening_range_no_pre_market_positional_leak`).

**Phase B status:** COMPLETED. `prd_and_roadmap.md` archived; `master_architecture.md` and `database_and_data_contracts.md` scoped to Binance Spot + USDⓈ-M Futures only; NSE constants in `config.py`/`clock.py` marked DEPRECATED (retained for Phase 1 tests); `research_loop.py` import removed from `server.py`; `POST /api/research/trigger` replaced with removed-stub; `agents/research_loop.py` and `test_phase5_research_agents.py` archived; ~566 candidate files + `.whl` + `graphify-out/` + `UII/` archived (not deleted). `docs/ARCHITECTURE_DECISIONS.md` created (ADR-001–ADR-012).

**Phase C status:** TASKS EXECUTED (not committed). Root `pyproject.toml` + `requirements.txt` created (Task 3). ZLA-001 fixed + regression tests added (Task 2). 13 external repos researched (Task 1). Top-10 scanner, max-5 cap, USDM futures WS connector, spot/futures isolation specified only (ADR-009–012, Task 4 — not implemented). Per-condition review response written (`docs/ANTIGRAVITY_REVIEW_CONDITION_RESPONSE.md`, Task 5).

---

## 2. Codebase Inventory (Tracked Files)

### Root (tracked)
| File | Role |
|------|------|
| `AGENTS.md` | Multi-agent governance (5 permanent rules) |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Phase/task tracker (Rule 3) |
| `CHANGELOG.md` | Change log (Rule 4) |
| `PEER_REVIEW_LOG.md` | Peer review sign-offs (Rule 5) |
| `readme.md` | Root project README (lowercase; no `README.md`) |
| `.gitignore` | Python/SQLite/pytest/IDE ignores |
| `trading_engine.db` | SQLite WAL database (gitignored, present on disk) |

### `docs/` (5 tracked)
| File | Role |
|------|------|
| `master_architecture.md` | Full 6-layer architecture + phased roadmap + stop gates |
| `prd_and_roadmap.md` | Product requirements + non-goals + 6-phase roadmap |
| `database_and_data_contracts.md` | SQLite schema (5 tables) + JSON contracts + FastAPI endpoints |
| `strategy_and_validation_spec.md` | Lego-block authoring guide + Validation Gatekeeper math |
| `contributing_indicators.md` | How to add indicators per family (zero-look-ahead rules) |

### `trading_engine/` package (36 tracked source files)
| Module | Files | Purpose |
|--------|-------|---------|
| Config | `config.py` | Market sessions, fee/slippage schedules, risk constants |
| Data | `data/clock.py`, `data/feature_store.py`, `data/feeds/binance_ws.py` | Sessions (UTC+IST), feature cache, Binance WS+REST |
| Indicators | `technical.py`, `statistical.py`, `structure.py`, `orderflow.py` | Families A–D (pure math, zero-look-ahead) |
| Signals | `technical_signals.py`, `statistical_signals.py`, `structure_signals.py`, `orderflow_signals.py` | Boolean trigger/filter wrappers |
| Strategies | `base_strategy.py`, `approved/ema_breakout_v1.py`, `approved/vwap_fvg_v1.py`, `candidates/__init__.py` | Versioned strategy recipes (V1 active) |
| Risk | `risk/risk_manager.py` | Position sizing, circuit breakers, R:R, execution costs |
| Execution | `execution/paper_simulator.py` | Event-driven paper lifecycle + MAE/MFE |
| Memory | `memory/db.py`, `memory/trade_logger.py` | SQLite WAL schema (5 tables) + trade persistence |
| Evaluation | `evaluation/analyzer.py` | Performance/Risk/Regime + Weakness Detection JSON |
| Agents | `agents/research_loop.py` | 4-role AI self-improvement loop |
| Validation | `validation/backtester.py`, `validation/gatekeeper.py` | OOS, Walk-Forward, Heatmap, Cost Stress |
| Backend | `backend/server.py` | FastAPI REST (9 routes) + WS `/ws/live` |
| Frontend | `frontend/index.html`, `css/styles.css`, `js/*.js`, `vendor/*.js` | Dark-mode terminal UI |
| Tests | `tests/test_phase{1..6}_*.py` | Deterministic pytest suites |

### Tests (6 tracked)
| File | Result |
|------|--------|
| `tests/test_phase1_data_db.py` | 22/22 passed |
| `tests/test_phase2_indicators_signals.py` | 64/64 passed (includes new Antigravity C1 regression test `test_opening_range_no_pre_market_positional_leak`) |
| `tests/test_phase3_execution_memory.py` | 24/24 passed |
| `tests/test_phase4_eval_validation.py` | 14/14 passed |
| `tests/test_phase6_backend_ui.py` | 9/9 passed |

---

## 3. Architecture Assessment (Master Architecture Layers)

| Layer | Module | Status | Notes |
|-------|--------|--------|-------|
| L1 Market Data & Feature Store | `data/`, `indicators/` | ✅ Complete | 4 indicator families, Binance WS + REST backfill, feature cache |
| L2 Strategy Engine & Paper Execution | `signals/`, `strategies/`, `risk/`, `execution/` | ✅ Complete | BaseStrategy Contract A, 2 V1 strategies, risk manager, paper simulator |
| L3 Data & Trade Memory | `memory/` | ✅ Complete | SQLite WAL, 5 tables, MAE/MFE/regime snapshots |
| L4 Evaluation Engine | `evaluation/analyzer.py` | ✅ Complete | Performance/Risk/Regime breakdown, Weakness Detection JSON |
| L5 AI Research Agents | `agents/research_loop.py` | ⚠️ Archived | 4-role loop archived (rule-based-only); not in active tree — see `archive/research_loop_archive/` |
| L5 Human Review & Validation Gate | `validation/gatekeeper.py` | ✅ Complete | OOS 70/30, WFA K=5, Heatmap 5x5, Cost Stress 1.5x; deterministic, never lets AI self-approve |
| L6 Validation Gate | `validation/backtester.py` | ✅ Complete | Event-driven bar replay; SL/TP/TIME exits on current-bar OHLC only |
| Backend + Frontend | `backend/server.py`, `frontend/` | ✅ Complete | Phase 6, 9 REST routes + WS, dark-mode UI |

---

## 4. Deviations from Intended Binance-Only Scope

The codebase contains multiple NSE/IST references that conflict with the intended **Binance Spot + USDⓈ-M Futures only** scope:

1. `config.py` lines 26–33: `NSE_SESSION_IST_START`, `NSE_SESSION_IST_END`, `NSE_SESSION_IST_WINDOW`, `NSE_TRADING_DAYS` — NSE equities session config (09:15–15:30 IST, Mon–Fri).
2. `data/clock.py`: Full NSE session logic (`is_nse_session_open`, `nse_next_session_open_utc`, `nse_square_off_utc`).
3. `docs/database_and_data_contracts.md` Table 1: `market_type` column allows `'NSE_EQUITY'` alongside `'CRYPTO_SPOT'`/`'CRYPTO_PERP'`.
4. `readme.md`: Explicitly mentions "Indian Intraday Equities (NSE F&O)" and master_architecture Layer 1 mentions "Phase 2 Expansion (India NSE): Dhan / Fyers / Angel One".
5. `master_architecture.md`: References NSE feeds (`nse_broker_ws.py` listed in folder structure but not present as a file) and NSE expansion.

**Action:** Phase B documentation cleanup + code audit classified NSE references as DEPRECATED (retained for Phase 1 tests) — `config.py` NSE constants and `data/clock.py` NSE methods; `docs/database_and_data_contracts.md` `market_type` → `'CRYPTO_SPOT', 'CRYPTO_PERP'` (`NSE_EQUITY` removed). `master_architecture.md` scoped to Binance Spot + USDⓈ-M Futures only; `readme.md` NSE mention retained as-is pending client decision (not part of code-change scope).

---

## 5. Constraints & Compliance Status

| Constraint | Status | Evidence |
|------------|--------|----------|
| Zero look-ahead (`t <= T`) | ✅ Enforced (ZLA-001 fixed) | `ZERO_LOOK_AHEAD = True` in config; `session_volume_profile()` rewritten as expanding past-only per-session; `opening_range()` rewritten past-only; new regression tests added; all phase suites pass |
| No AI self-approval | ✅ Enforced | `validation/gatekeeper.py` independent; V1 stays active on V2 failure |
| Paper trade first | ✅ Enforced | `execution/paper_simulator.py`; `POST /api/trades/manual` logs `MANUAL_LIVE`; human executes broker orders manually |
| Rule-based only (no ML/DL/RL/LLM) | ✅ Enforced | `agents/research_loop.py` archived; rule-based V1 only; V2 candidates require human review + gatekeeper |
| Max 5 strategies | ⚠️ NOT YET ENFORCED (specified only) | ADR-010 specifies `StrategyRegistry.MAX_ACTIVE_STRATEGIES = 5`; not implemented (awaits client approval) |
| Top 10 by rolling 24h quote volume | ❌ NOT IMPLEMENTED (specified only) | `CRYPTO_TRADEABLE_PAIRS` hardcoded to 3 pairs; ADR-009 specifies `Top10EligibilityScanner`; not implemented (awaits client approval) |
| Binance Spot + USDⓈ-M Futures only | ✅ Binance-only scope | NSE constants DEPRECATED; `market_type` → `CRYPTO_SPOT`/`CRYPTO_PERP`; root manifests + ZLA fix applied |

---

## 6. Untracked Artifacts (Working Tree, Not Committed)

| Item | Count | Notes |
|------|-------|-------|
| `trading_engine/strategies/candidates/v2_candidate_hyp_*.py` | ~300+ | Research artifacts from Phase 5 research loop; likely candidates for archiving/removal decision |
| `*.whl` files (root) | 8 | `annotated_doc`, `annotated_types`, `anyio`, `pydantic`, `pydantic_core`, `starlette`, `typing_extensions`, `typing_inspection` — pip wheel caches, not source |
| `UII/` | 4 screenshot PNGs | UI screenshots; non-source artifact |
| `graphify-out/` | directory | Graphify knowledge-graph output; non-source artifact |
| `.venv/`, `.pytest_cache/`, `__pycache__/` | directories | gitignored environment/cache |

---

## 7. Phase A Audit Conclusion & Phase C Status

The codebase is complete, tested, and internally consistent through Phase 6. Phase B (documentation cleanup for Binance-only scope) is complete.

**Phase C task execution (this session — uncommitted on phase branch):**

| # | Task | Status |
|---|------|--------|
| C.1 | External repo source-level research (13 repos) | ✅ Complete — all 13 cloned to `/tmp/opencode/` and inspected; findings in `docs/REPOSITORY_RESEARCH.md`; KI-010 cleared |
| C.2 | Zero-look-ahead correction (ZLA-001) | ✅ Complete — `session_volume_profile()` + `opening_range()` rewritten past-only; 2 regression tests added; all phase suites pass; `docs/ZERO_LOOK_AHEAD_REVALIDATION.md` verdict → "PASS — clean" |
| C.3 | Root manifests (`pyproject.toml` + `requirements.txt`) | ✅ Complete — created; fresh-env `pip install` + `pytest` verified reproducible from repo root; KI-006 cleared |
| C.4 | Specify (not implement) top-10 scanner, max-5 cap, perp WS connector, spot/futures isolation | ✅ Complete — ADR-009/010/011/012 added to `docs/ARCHITECTURE_DECISIONS.md`; interfaces + acceptance criteria specified; not implemented |
| C.5 | Per-condition response to independent review | ✅ Complete — `docs/ANTIGRAVITY_REVIEW_CONDITION_RESPONSE.md` addresses every condition |
| C.6 | Doc reconciliation (`KNOWN_ISSUES.md`, `PROJECT_AUDIT.md`, `DEVELOPMENT_PLAN_AND_TODO.md`, `CHANGELOG.md`) | ✅ Complete (this session) |

**Remaining transformation work (implementation, awaits client approval):**
1. Implement dynamic top-10-by-quote-volume eligibility (specified ADR-009, not implemented).
2. Implement max-5 strategy cap enforcement (specified ADR-010, not implemented).
3. Implement USDⓈ-M Futures WebSocket connector (specified ADR-011, not implemented).
4. Spot/futures isolation enforcement in code (specified ADR-012, not implemented).
5. Commit archived cleanup changes to phase branch (exclude binaries) — awaits client approval (Rule 6).
6. Phase C peer review & sign-off (Rule 5).

**13 GitHub repo URLs:** Supplied by client and inspected (KI-010 cleared). No longer a blocker.

---
