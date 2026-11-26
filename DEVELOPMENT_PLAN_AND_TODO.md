# Development Plan & To-Do — FinceptEngine

**Project:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Version:** v0.1.0 (Project Initiation Baseline)  
**Status:** Active  
**Tracker Rule:** Updated at the start and end of every task across four sections: COMPLETED & VERIFIED, IN PROGRESS, REMAINING BACKLOG, NEWLY ADDED / DISCOVERED.

---

## [x] COMPLETED & VERIFIED

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| 1 | Read all 6 documentation files in `docs/` | Architect | Done | Full audit complete — no source code existed yet |
| 2 | Inspect directory tree — confirmed empty-codebase baseline | Architect | Done | |
| 3 | Scaffold `trading_engine/` package with all 16 subdirectories per MASTER_ARCHITECTURE.md Section 3 | Architect | Done | data/, indicators/, signals/, strategies/, risk/, execution/, memory/, evaluation/, agents/, validation/, backend/, frontend/, tests/ plus feeds/, approved/, candidates/, js/, css/ |
| 4 | Add clean `__init__.py` to every Python package directory (18 files) | Architect | Done | `trading_engine/__init__.py` sets `__version__ = "0.1.0"` |
| 5 | Multi-agent governance initiation | All 5 agents | Done | Steps 1–3 of the Master Prompt |
| 6 | Embed permanent 5-rule governance into root `AGENTS.md` | Architect + Reviewer | Done | Verified in Review #001 |
| 7 | Create `DEVELOPMENT_PLAN_AND_TODO.md` with Phase 1–6 breakdown | Architect | Done | |
| 8 | Create `CHANGELOG.md` with initial v0.1.0 entry | Architect + QA | Done | |
| 9 | Create `PEER_REVIEW_LOG.md` with Review #001 | Reviewer | Done | |
| 1.1 | Create `config.py` — market sessions, fee/slippage, risk constants | Backend | Phase 1 | Per PRD FR-01; `trading_engine/config.py` |
| 1.2 | Create `requirements.txt` — FastAPI, uvicorn, pandas, numpy, pandas-ta, scipy, websockets, pytest | Backend | Phase 1 | `trading_engine/requirements.txt` |
| 1.3 | Create `data/clock.py` — Session manager UTC & IST | Backend | Phase 1 | `trading_engine/data/clock.py` |
| 1.4 | Create `data/feeds/binance_ws.py` — Binance WS + REST backfill | Backend | Phase 1 | `trading_engine/data/feeds/binance_ws.py` |
| 1.5 | Create `memory/db.py` — SQLite WAL schema (5 tables) | Backend | Phase 1 | `trading_engine/memory/db.py` |
| 1.6 | Create `tests/test_phase1_data_db.py` — deterministic pytest suite | QA | Phase 1 | `trading_engine/tests/test_phase1_data_db.py` |
| 1.7 | Run `pytest tests/test_phase1_data_db.py` — verify pass, STOP (Phase 1 hard stop gate) | QA + Reviewer | Phase 1 | **VERIFIED: 22/22 tests passed** on `phase1/core-data-memory` branch (2026-11-09). Client approval required before Phase 2. |

---

## [x] COMPLETED & VERIFIED (continued)

| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 30 | Create `trading_engine/data/feature_store.py` — SQLite + Parquet feature cache with zero-look-ahead load | Backend | Phase 2 | **VERIFIED** — test_feature_store_write_and_load, test_feature_store_zero_look_ahead_load, test_zero_look_ahead_slice_excludes_future pass |
| 31 | Create `trading_engine/indicators/technical.py` — Family A indicators + tests | Backend/QA | Phase 2 | **VERIFIED** — EMA/SMA/RSI/ATR/BB/MACD/Supertrend/Donchian/Pivots + zero-look-ahead pass |
| 32 | Create `trading_engine/indicators/statistical.py` — Family B indicators + tests | Backend/QA | Phase 2 | **VERIFIED** — Z-Score/Hurst/Vol Percentile/LinReg Slope/RS pass |
| 33 | Create `trading_engine/indicators/structure.py` — Family C indicators + tests | Backend/QA | Phase 2 | **VERIFIED** — PDH/PDL/PDC/ORB/Trendlines/FVG/Order Blocks/Liquidity Sweeps pass |
| 34 | Create `trading_engine/indicators/orderflow.py` — Family D indicators + tests | Backend/QA | Phase 2 | **VERIFIED** — VWAP/RVOL/Volume Profile/CVD/Footprint/Iceberg pass |
| 35 | Create `trading_engine/signals/{technical,statistical,structure,orderflow}_signals.py` — boolean signal wrappers | Backend/QA | Phase 2 | **VERIFIED** — all signal wrappers return correct True/False |
| 36 | Create `trading_engine/tests/test_phase2_indicators_signals.py` — full Phase 2 suite | QA | Phase 2 | **VERIFIED** — **64/64 tests passed** (61 original + 2 ZLA regression tests + 1 Antigravity C1 regression test `test_opening_range_no_pre_market_positional_leak`) |
| 37 | Run `pytest trading_engine/tests/test_phase2_indicators_signals.py` — verify pass, STOP (Phase 2 hard stop gate) | QA + Reviewer | Phase 2 | **VERIFIED: 64/64 passed** (2026-11-24, after Antigravity C1 fix) |
| 38 | Client approved Phase 2 hard stop gate; merged `phase2/indicators-signals` into `dev` and pushed to origin | Architect | Phase 2 | Merge commit `f2d8c45` on `dev`; PR #2 merged |
| 39 | Create `strategies/base_strategy.py` — abstract BaseStrategy interface + Contract A signal dict | Backend/QA | Phase 3 | **VERIFIED** — test_base_strategy_build_signal_contract_a, test_base_strategy_target_2_defaults_to_target_1 pass |
| 40 | Create `strategies/approved/ema_breakout_v1.py` — baseline V1 EMA breakout | Backend/QA | Phase 3 | **VERIFIED** — ATR expansion inline filter, EMA cross trigger, bullish trend + HMA bias, stop/R:R pass |
| 41 | Create `strategies/approved/vwap_fvg_v1.py` — baseline V1 VWAP + FVG | Backend/QA | Phase 3 | **VERIFIED** — above_vwap, value_area, fvg_retest_bull, ob_test_bull, stop floored at FVG bottom pass |
| 42 | Create `risk/risk_manager.py` — position sizing, ATR stop, slippage/commission, circuit breakers, R:R | Backend/QA | Phase 3 | **VERIFIED** — sizing, ATR stop long/short, validate_rr, daily loss breaker, consecutive-loss breaker, slippage/commission pass |
| 43 | Create `memory/trade_logger.py` — open trade, MAE/MFE update, close trade (PnL/R), SQLite persistence | Backend/QA | Phase 3 | **VERIFIED** — open/close roundtrip, MAE/MFE update, net PnL + R-multiple, list by strategy/mode pass |
| 44 | Create `execution/paper_simulator.py` — event-driven paper lifecycle, tick-by-tick MAE/MFE, slippage/commission deduction | Backend/QA | Phase 3 | **VERIFIED** — full lifecycle open→TP1 exit, MAE/MFE recorded, halt on consecutive losses, summary pass |
| 45 | Create `tests/test_phase3_execution_memory.py` — full Phase 3 test suite | QA | Phase 3 | **VERIFIED** — **24/24 tests passed** (2026-11-09) |
| 46 | Run `pytest trading_engine/tests/test_phase3_execution_memory.py` — verify pass, STOP (Phase 3 hard stop gate) | QA + Reviewer | Phase 3 | **VERIFIED: 24/24 passed** — client approved; Phase 4 started |
| 47 | Create `validation/backtester.py` — event-driven historical backtest runner + `BacktestResult` | Backend/QA | Phase 4 | **VERIFIED** — imports OK; test_backtester_* (4/4) pass |
| 48 | Create `evaluation/analyzer.py` — Performance/Risk/Regime breakdown + Weakness Detection JSON | Backend/QA | Phase 4 | **VERIFIED** — imports OK; test_compute_performance_*, test_detect_weaknesses_* (7/7) pass |
| 49 | Create `validation/gatekeeper.py` — OOS 70/30, Walk-Forward K=5, Heatmap 5x5, Cost Stress 1.5x; APPROVED/REJECTED | Backend/QA | Phase 4 | **VERIFIED** — imports OK; gatekeeper tests pass |
| 50 | Create `tests/test_phase4_eval_validation.py` — full Phase 4 suite (backtester + analyzer + gatekeeper) | QA | Phase 4 | **VERIFIED** — **14/14 tests passed** (`pytest trading_engine/tests/test_phase4_eval_validation.py -q`, 2026-11-11) |
| 51 | Run `pytest trading_engine/tests/test_phase4_eval_validation.py` — verify pass, STOP (Phase 4 hard stop gate) | QA + Reviewer | Phase 4 | **VERIFIED: 14/14 passed** — client approved; merged into `dev` via PR #3 |

## [x] COMPLETED & VERIFIED (continued)

| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 52 | Create `agents/research_loop.py` — Research → Hypothesis → Coding V2 → Review pipeline (4-role AI self-improvement loop) | Backend | Phase 5 | **VERIFIED** — offline deterministic template-based, no LLM SDK, zero look-ahead, V1 stays active on failure |
| 53 | Create `tests/test_phase5_research_agents.py` — full Phase 5 suite (all 4 roles + Contract A + zero-look-ahead audit + no-LLM-SDK + full loop) | QA | Phase 5 | **VERIFIED** — **11/11 tests passed** (`pytest trading_engine/tests/test_phase5_research_agents.py -q`, 2026-11-11) |
| 54 | Run `pytest trading_engine/tests/test_phase5_research_agents.py` — verify pass, STOP (Phase 5 hard stop gate) | QA + Reviewer | Phase 5 | **VERIFIED: 11/11 passed** — STOPPED at Phase 5 hard stop gate awaiting client approval before Phase 6 |

## [/] IN PROGRESS (CURRENT SPRINT)

| # | Task | Owner | Notes |
|---|------|-------|-------|
| — | Phase 6 complete, committed (f01f2ca) & pushed to `origin/phase6/fastapi-backend-ui`. **NOT merged to `dev`** — awaiting explicit client approval before merge (Rule 6). | — | 9 endpoints + WS smoke-tested; pytest suite 9/9 passed |
| — | Phase C planning & research — **COMPLETED** (this turn) | Architect | All deliverables complete; peer review & sign-off recorded in `PEER_REVIEW_LOG.md`; ready for client presentation |

---

## [x] COMPLETED & VERIFIED (Phase C)

| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| C.1 | Create `docs/REPOSITORY_RESEARCH.md` — findings from local codebase vs 14 research areas | Architect | Phase C | **VERIFIED** — 12/14 areas have complete local implementations; blocker KI-010 (13 GitHub URLs) open |
| C.2 | Create `docs/REBUILD_RECOMMENDATION.md` — rebuild vs in-place + manifest choice | Architect + QA + Reviewer | Phase C | **VERIFIED** — in-place evolution recommended; `pyproject.toml` + `requirements.txt` both |
| C.3 | Create `docs/ARCHITECTURE_DECISIONS.md` — ADRs for Binance-only transformation | Architect | Phase C | **VERIFIED** — ADR-001 through ADR-008 |
| C.4 | Revalidate zero-look-ahead claim & risk-management concerns | QA + Reviewer | Phase C | **VERIFIED** — PASS with 1 Medium finding (ZLA-001 `session_volume_profile()`) |
| C.5 | Update `PROJECT_AUDIT.md`, `KNOWN_ISSUES.md` to reflect Phase B completion | Architect | Phase C | **VERIFIED** — KI-001–KI-006 resolved; KI-007–010 open |
| C.6 | Add `CHANGELOG.md` Phase C entry | Architect | Phase C | **VERIFIED** — [v0.1.11] entry added |
| C.7 | Peer review & sign-off (Rule 5) — record in `PEER_REVIEW_LOG.md` | Reviewer | Phase C | **VERIFIED** — QA + Reviewer PASSED; ready for client presentation |

---

## [+] NEWLY ADDED / DISCOVERED ITEMS

| Date | Item | Reason | Owner |
|------|------|--------|-------|
| 2026-11-24 | Phase B documentation cleanup complete — `prd_and_roadmap.md` archived; `master_architecture.md` → Binance-only; `database_and_data_contracts.md` → Binance-only; `server.py` line 301 NSE_EQUITY→CRYPTO_SPOT; `research_loop` import removed from `server.py`; NSE constants in `config.py`/`clock.py` marked DEPRECATED; 566 candidate files + `test_phase5_research_agents.py` + `research_loop.py` + `.whl` + `graphify-out/` + `UII/` archived (not deleted) | Phase B transformation work | Architect |
| 2026-11-24 | `CHANGELOG.md` entry [v0.1.10] added | Phase B timestamped entry | Architect |
| 2026-11-09 | **Phase 1 Python logic written & verified**: `config.py`, `requirements.txt`, `data/clock.py`, `data/feeds/binance_ws.py`, `memory/db.py`, `tests/test_phase1_data_db.py` | PRD Phase 1 deliverables complete | Backend + QA |
| 2026-11-09 | **Environment constraint**: PyPI unreachable (read timeout), no root for apt, no pip cache — `pytest`/`pandas`/`fastapi`/`scipy` cannot be installed. Phase 1 verified via inline Python execution instead of `pytest`. | Network restriction in dev container | QA |

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
| 4.1 | Create `validation/backtester.py` — event-driven historical backtest engine | Backend | Phase 4 | **VERIFIED** — done; test_backtester_* (4/4) pass |
| 4.2 | Create `evaluation/analyzer.py` — Performance/Risk/Regime breakdown + Weakness JSON | Backend | Phase 4 | **VERIFIED** — done; test_compute_performance/detect_weaknesses (7/7) pass |
| 4.3 | Create `validation/gatekeeper.py` — OOS split, Walk-Forward, Parameter Heatmap, Approve/Reject | Backend | Phase 4 | **VERIFIED** — done; gatekeeper tests pass |
| 4.4 | Create `tests/test_phase4_eval_validation.py` — full Phase 4 suite | QA | Phase 4 | **VERIFIED** — done; 14/14 tests pass |
| 4.5 | Run pytest — verify pass, then STOP (Phase 4 hard stop gate) | QA + Reviewer | Phase 4 | **VERIFIED: 14/14 passed** — STOPPED awaiting client approval |

### Phase 5: The 4 AI Research Agents (Self-Improvement Loop)
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| — | All Phase 5 tasks complete & verified (11/11) — `agents/research_loop.py` + `test_phase5_research_agents.py` archived to `archive/research_loop_archive/` & `archive/research_artifacts/` | — | Phase 5 | EXCLUDED from active V1 workflow — conflicts with rule-based-only restriction (no multi-agent/autonomous strategy generation). Source preserved (not deleted). |

### Phase 6: FastAPI Backend & Unified Dark-Mode Terminal UI
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 6.1 | Create `backend/server.py` — FastAPI REST + WebSocket hub | Backend | Phase 6 | **VERIFIED** — `http://127.0.0.1:8765`; 9 routes registered incl. WS `/ws/live` |
| 6.2 | Create `execution/alert_dispatcher.py` — 1-Click Manual Order Ticket + audio/Telegram alerts | Backend | Phase 6 | Manual ticket exposed via `POST /api/trades/manual` + System Monitor UI form (server.py + system_monitor_ui.js) |
| 6.3 | Create `frontend/index.html`, `frontend/css/styles.css`, `frontend/js/*.js` | Frontend | Phase 6 | **VERIFIED** — dark-mode terminal shell, Lightweight Charts v5.3.0 vendored, all endpoints smoke-tested |
| 6.4 | Full end-to-end launch verification in browser, zero console errors | Frontend + QA | Phase 6 | **VERIFIED** — all endpoints smoke-tested OK; `pytest trading_engine/tests/test_phase6_backend_ui.py` **9/9 passed** |

---

## [x] COMPLETED & VERIFIED (Phase E.0)

| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| E.0.1 | `config.py` — Add `CRYPTO_SPOT`, `CRYPTO_PERP` market type constants | Backend | E.0 | **VERIFIED** — defaults Spot for backward compatibility |
| E.0.2 | `memory/db.py` — Extend `ohlcv_bars` PK to include `market_type`; add `market_type` column + indexes to `trades_memory`/`validation_reports`; add `schema_migrations` table; versioned `run_migration()` | Backend | E.0 | **VERIFIED** — create-copy-replace-validate migration; row counts preserved |
| E.0.3 | `data/feature_store.py` — Extend `indicator_features` PK to include `market_type`; `market_type` in cache keys/queries/Parquet | Backend | E.0 | **VERIFIED** — Spot/Futures features never aliased |
| E.0.4 | `memory/trade_logger.py` — `open_trade()` accepts `market_type` (default `CRYPTO_SPOT`) | Backend | E.0 | **VERIFIED** |
| E.0.5 | `validation/gatekeeper.py` — `ValidationReport` includes `market_type`; threaded through `evaluate()`/`_run_backtest()`/`_walk_forward()`/`_parameter_heatmap()` | Backend | E.0 | **VERIFIED** |
| E.0.6 | `validation/backtester.py` — `Backtester.__init__()` accepts `market_type`; passed to `TradeLogger.open_trade()` | Backend | E.0 | **VERIFIED** |
| E.0.7 | `backend/server.py` — `/api/trades/memory` and `/api/validation/reports` accept optional `market_type` filter (default `CRYPTO_SPOT`) | Backend | E.0 | **VERIFIED** |
| E.0.8 | `tests/test_phase_e_isolation_contracts.py` — 20 tests per blueprint acceptance criteria | QA | E.0 | **VERIFIED** — 20/20 passed |
| E.0.9 | Full `pytest` run — 156 passed (133 baseline + 23 Phase E.0 incl. 3 QA regression tests for F1/F2/F3) | QA | E.0 | **VERIFIED** — baseline preserved |
| E.0.10 | Rule 5 peer review (QA + Reviewer) complete; sign-off in `PEER_REVIEW_LOG.md`; findings F1/F2/F3 fixed | QA + Reviewer | E.0 | **VERIFIED** — sign-off recorded; E.1–E.7 blocked on separate client approval |

---

## [/] REMAINING BACKLOG (BY PHASE)

### Phase E.1–E.7 (Blocked — separate client approval required per B9)

| # | Task | Phase | Notes |
|---|------|-------|-------|
| E.1 | Config: Spot/Futures endpoints & futures fee/funding constants | E.1 | Not authorized — requires separate client approval |
| E.2 | Dynamic top-10 eligible asset scanner with point-in-time snapshots | E.2 | Numeric liquidity thresholds + hysteresis pending client confirmation |
| E.3–E.7 | Subsequent Phase E milestones | E.3+ | Not authorized — requires separate client approval |

---

## [+] NEWLY ADDED / DISCOVERED ITEMS

| Date | Item | Reason | Owner |
|------|------|--------|-------|
| 2026-11-25 | Phase E.0 implemented: schema isolation + versioned migration + feature store keys + query-layer filtering + 20 tests | B9 authorizes E.0 only | Backend + QA + Architect |
| 2026-11-25 | `CHANGELOG.md` entry [v0.1.13] added | Phase E.0 timestamped entry | Architect |
| 2026-11-25 | `DEVELOPMENT_PLAN_AND_TODO.md` updated: Phase E.0 added to COMPLETED & VERIFIED; E.1–E.7 moved to REMAINING BACKLOG | Rule 2 & Rule 3 — sync docs/trackers with code | Architect |
| 2026-11-25 | Nothing committed, pushed, or merged (Rule 6) | Client approval required before committing | All |

## [+] NEWLY ADDED / DISCOVERED ITEMS

| Date | Item | Reason | Owner |
|------|------|--------|-------|
| 2026-11-08 | Root-level `AGENTS.md` missing — created new one embedding the 5 mandatory governance rules | Governance requirement from Master Prompt Step 2 | Architect + Reviewer |
| 2026-11-08 | `readme.md` exists at root (lowercase) but no `README.md` — no duplicate created to avoid confusion | Project has lowercase readme; kept as-is | Architect |
| 2026-11-08 | `DEVELOPMENT_PLAN_AND_TODO.md`, `CHANGELOG.md`, `PEER_REVIEW_LOG.md` created as new governance artifacts | Governance requirement from Master Prompt Step 3 | Architect + QA + Reviewer |
| 2026-11-09 | **Phase 2 complete & verified**: `data/feature_store.py`, `indicators/{technical,statistical,structure,orderflow}.py`, `signals/{technical,statistical,structure,orderflow}_signals.py`, `tests/test_phase2_indicators_signals.py` | PRD Phase 2 deliverables complete; **58/58 tests passed**; hard stop gate reached — awaiting client approval before Phase 3 | Backend + QA + Reviewer |
| 2026-11-09 | Installed `pandas-ta` in `.venv` (already listed in `trading_engine/requirements.txt`) | 130+ installable indicators available as `import pandas_ta as pta`; kept alongside pure-pandas implementations for cross-checking | Backend + QA |
| 2026-11-09 | Created `docs/contributing_indicators.md` | Step-by-step guide: how to add new indicators per family, keep files separate, enforce zero-look-ahead, write signal wrappers, and test | Architect + QA |
| 2026-11-09 | Added HMA indicator + signal wrappers + tests to `technical.py`, `technical_signals.py`, `test_phase2_indicators_signals.py` | Demonstrated contribution guide in practice; **61/61 tests passed** | Backend + QA |
| 2026-11-11 | **Phase 6 complete**: `backend/server.py` (9 routes + WS `/ws/live`), full frontend (`index.html`, `css/styles.css`, `js/{main,chart_engine,footprint_ui,lab_evaluation_ui,system_monitor_ui}.js`, vendored Lightweight Charts v5.3.0), `tests/test_phase6_backend_ui.py` | All endpoints smoke-tested OK; pytest suite **9/9 passed**; Lightweight Charts vendored locally from npm (unpkg CDN 404s) | Backend + Frontend + QA |
| 2026-11-11 | Fixed Phase 6 test suite: corrected `ROOT` path (3 levels up from `tests/`), converted `@pytest.mark.asyncio` tests to sync `asyncio.run()` (no `pytest-asyncio` available offline), added `count: 0` to empty snapshot case | `pytest-asyncio` not installed; PyPI unreachable | QA |

---

| Date | Item | Reason | Owner |
|------|------|--------|-------|
| 2026-11-24 | Phase A codebase audit complete — `PROJECT_AUDIT.md` + `KNOWN_ISSUES.md` created | Identify all deviations from intended Binance-only scope; blocker: 13 GitHub repo URLs not found | Architect |
| 2026-11-24 | Phase B documentation cleanup backlog added | Inventory docs, classify KEEP/UPDATE/ARCHIVE/REMOVE, archive before removing | Architect |
| 2026-11-24 | ~300+ `v2_candidate_hyp_*.py` candidate files + `*.whl` + `UII/` + `graphify-out/` untracked artifacts | Working-tree hygiene; archive-before-remove rule applies | Architect |

---

**Execution Rule:** No Phase 1 Python application logic (`binance_ws.py`, `db.py`) is to be written until the Client reviews and approves this `DEVELOPMENT_PLAN_AND_TODO.md`.
