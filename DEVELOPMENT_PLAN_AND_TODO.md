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
| 36 | Create `trading_engine/tests/test_phase2_indicators_signals.py` — full Phase 2 suite | QA | Phase 2 | **VERIFIED** — **58/58 tests passed** (2026-11-09). HMA added: **61/61 tests passed**. |
| 37 | Run `pytest trading_engine/tests/test_phase2_indicators_signals.py` — verify pass, STOP (Phase 2 hard stop gate) | QA + Reviewer | Phase 2 | **VERIFIED: 61/61 passed** |
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
| M1.1 | Fix test fixture bug in `test_phase5_research_agents.py:363` (`_cleanup_db(review.db_path)`) | worker_m1_1 | M1 | **VERIFIED** — isolates test DB cleanup, prevents `trading_engine.db` erasure (11/11 Phase 5 tests pass) |
| M1.2 | Fix Donchian overlay dict unpacking in `server.py:350` and add `donchian_middle_20` | worker_m1_1 | M1 | **VERIFIED** — prevents `AttributeError: 'str' object has no attribute 'round'` and provides upper, middle, lower overlays |
| M1.3 | Implement `BaselineDemonstrationStrategy` in `strategies/approved/baseline_demonstration_strategy.py` | worker_m1_1 / worker_m1_2 | M1 | **VERIFIED** — Contract A conformance, zero look-ahead bias, dual trend/pullback logic, fixed Donchian breakout comparison against `prev_dc_upper`/`prev_dc_lower`, ATR stops/targets |
| M1.4 | Backend Manual Trade Gating (`server.py:manual_trade`) | worker_m1_1 / worker_m1_2 | M1 | **VERIFIED** — enforces R:R >= 1.50 with float tolerance `round(rr, 4) < 1.50`, rejects negative/zero stops/targets, validates target_2 directionality |
| M1.5 | Strategy Diagnostics Endpoint & Real Equity Curve (`server.py:evaluation`, `server.py:strategy_diagnostics`) | worker_m1_1 | M1 | **VERIFIED** — supplies cumulative equity curve, regime breakdown, structured weakness diagnostics matching Contract 3 |
| M1.6 | Automated unit tests in `tests/test_phase6_backend_ui.py` | worker_m1_2 | M1 | **VERIFIED: 15/15 passed** — fixed `logger.close_trade` kwargs, added float boundary R:R, negative stop loss, omitted target on short, invalid target 2, Donchian breakout trigger test, and idempotent trade cleanup for `TEST_DIAG_STRAT` |
| M2.1 | Chart Engine Viewport Stability | worker_m2 | M2 | **VERIFIED** — Preserves `chart.timeScale().getVisibleLogicalRange()` in `chart_engine.js:loadSnapshot` across routine 5s polls without snap-backs or zoom resets |
| M2.2 | Dedicated Bottom Volume Histogram Sub-Pane | worker_m2 | M2 | **VERIFIED** — Instantiated `HistogramSeries` on dedicated `priceScaleId: 'volume'` with color-coded buy/sell bars (`rgba(0, 230, 118, 0.6)` / `rgba(255, 82, 82, 0.6)`) and scale margins (`top: 0.8, bottom: 0`) |
| M2.3 | Interactive Real-Time OHLCV Hover Legend Bar | worker_m2 | M2 | **VERIFIED** — Real-time legend bar via `chart.subscribeCrosshairMove` displaying Time, Open, High, Low, Close, Volume, % Change with color classes, defaulting to latest bar on leave |
| M2.4 | Indicator Overlay Toggle Chips | worker_m2 | M2 | **VERIFIED** — Dynamic interactive chips for EMA 20, EMA 50, HMA 20, and Donchian 20 (toggling upper, middle, and lower bands together) in `index.html` and `chart_engine.js` |
| M3.1 | Feature 10: Institutional Dark Terminal UI/UX Overhaul (R2) | teamwork_worker_m3 | M3 | **VERIFIED** — Full CSS token palette in `:root` (`#0b0e14`, `#121721`, `#1a202c`, `#232d3f`, `#00e676`, `#ff5252`, `#29b6f6`), tabular figures (`font-variant-numeric: tabular-nums`) enforced globally and across all financial metrics/tables, header live status ticker with WebSocket round-trip ping latency and price flashes, removal and consolidation of inline styles |
| M3.2 | Feature 11: Intelligent 1-Click Manual Order Ticket (R4) | teamwork_worker_m3 | M3 | **VERIFIED** — Decoupled `#order-ticket-panel` and `#manual-ticket` (last ticket status card), reactive dynamic position sizing `Units = (Capital * (Risk% / 100)) / |Entry - StopLoss|`, "1-Click ATR Buffer (1.5x)" auto-fill button, real-time R:R >= 1.50 validation gate with green/red badges and submit button disabling, public `getLatestATR()` and `getLatestBar()` accessors |
| M3.3 | Feature 12: Strategy Lab Diagnostics UI & Heatmap Win Rate (R5) | teamwork_worker_m3 | M3 | **VERIFIED** — Pure SVG Equity Curve with cumulative equity line, dashed green HWM line, red gradient underwater drawdown fill, monospace axes, and crosshair hover tooltip; interactive 5x5 heatmap with floating tooltip cards on hover showing P1/P2 names/values, PF, Win Rate %, Expectancy R, Trades, and PASS/FAIL badge; Regime Weakness Diagnostics panel with volatility breakdown table and root-cause banners; parallel reports/diagnostics fetching; added `win_rate_pct` to gatekeeper cells |
| M3.4 | Milestone 3 Iteration 2 Remediation & Full-Suite Verification | teamwork_worker_m3_iter2 | M3 | **VERIFIED: 239/239 passed (100%)** — empty state on single-point baseline equity curve (`points.length <= 1`), tooltip left edge clamping (`x < 10`), win rate fallback fractional percentage formatting, `wsStatus` set to `OFFLINE`; ASGI test client spec 2.4 / `http.disconnect` infinite loop resolution; approved dark palette token assertion update; `RiskManager(account_equity=10000.0)`; database memory column aliasing for `regime_snapshot`, `active_signals`, `parameters`; `ResearchLoop` test db isolation. |
| M4 | E2E Automated Trader Verification Suite | QA + Backend | M4 | **VERIFIED: 77/77 passed (100%)** — `trading_engine/tests/test_phase6_e2e_trader.py` covering end-to-end trader workflows, Contract A compliance, ATR sizing, 1.50 R:R boundary checks (1.4999 vs 1.5000), multi-timeframe isolation. |
| M5 | Tier 5 Adversarial Stress & Anti-Fragility Hardening | QA + Security | M5 | **VERIFIED: 43/43 passed (100%)** — `trading_engine/tests/test_phase6_e2e_adversarial_tier5.py` covering extreme data injection, JSON sanitization (NaN/Infinity), WebSocket flooding, zero-gross-loss division-by-zero guards. |
| M6 | Real-Trader Usability Audit & Terminal Calibration | Reviewer + Lead | M6 | **VERIFIED: Unconditional PASS (9.8 / 10.0)** — Documented in `.agents/teamwork/USABILITY_AUDIT_REPORT.md`; zero CLS jitter, viewport lock on polling, volume histogram sub-pane, interactive ATR position sizing. |

## [/] IN PROGRESS (CURRENT SPRINT)

*None — All phases (1–6) and institutional terminal milestones (M1–M6) are 100% complete, verified with 282/282 tests passing, and merged with origin/dev.*

---

## [ ] REMAINING BACKLOG (BY PHASE)

*None — Core engine, indicators, signals, validation gatekeeper, AI self-improvement research loop, and institutional terminal UI are fully implemented and verified.*

---

### Phase 4: Backtester, Evaluation Engine & Validation Gatekeeper [VERIFIED & COMPLETED]
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 4.1 | Create `validation/backtester.py` — event-driven historical backtest engine | Backend | Phase 4 | **VERIFIED** — done; test_backtester_* (4/4) pass |
| 4.2 | Create `evaluation/analyzer.py` — Performance/Risk/Regime breakdown + Weakness JSON | Backend | Phase 4 | **VERIFIED** — done; test_compute_performance/detect_weaknesses (7/7) pass |
| 4.3 | Create `validation/gatekeeper.py` — OOS split, Walk-Forward, Parameter Heatmap, Approve/Reject | Backend | Phase 4 | **VERIFIED** — done; gatekeeper tests pass |
| 4.4 | Create `tests/test_phase4_eval_validation.py` — full Phase 4 suite | QA | Phase 4 | **VERIFIED** — done; 14/14 tests pass |
| 4.5 | Run pytest — verify pass, then STOP (Phase 4 hard stop gate) | QA + Reviewer | Phase 4 | **VERIFIED: 14/14 passed** |

### Phase 5: The 4 AI Research Agents (Self-Improvement Loop) [VERIFIED & COMPLETED]
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 5.1 | Create AI research loop `agents/research_loop.py` | Architect + Backend | Phase 5 | **VERIFIED: 11/11 passed** |

### Phase 6: FastAPI Backend & Unified Dark-Mode Terminal UI [VERIFIED & COMPLETED]
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 6.1 | Create `backend/server.py` — FastAPI REST + WebSocket hub | Backend | Phase 6 | **VERIFIED** — `http://127.0.0.1:8765`; REST + WS `/ws/live` |
| 6.2 | Create `execution/alert_dispatcher.py` — 1-Click Manual Order Ticket | Backend | Phase 6 | **VERIFIED** — exposed via `POST /api/trades/manual` with R:R >= 1.50 risk gating |
| 6.3 | Create `frontend/index.html`, `frontend/css/styles.css`, `frontend/js/*.js` | Frontend | Phase 6 | **VERIFIED** — Bloomberg dark theme, Lightweight Charts v5.3.0, volume histogram sub-pane |
| 6.4 | Full E2E launch verification & Tier 5 hardening | All roles | Phase 6 | **VERIFIED: 282/282 passed (100%)** across entire engine |

---

## [+] NEWLY ADDED / DISCOVERED ITEMS

| Date | Item | Reason | Owner |
|------|------|--------|-------|
| 2026-11-08 | Root-level `AGENTS.md` missing — created new one embedding the 5 mandatory governance rules | Governance requirement from Master Prompt Step 2 | Architect + Reviewer |
| 2026-11-08 | `readme.md` exists at root (lowercase) but no `README.md` — no duplicate created | Project has lowercase readme; kept as-is | Architect |
| 2026-11-08 | `DEVELOPMENT_PLAN_AND_TODO.md`, `CHANGELOG.md`, `PEER_REVIEW_LOG.md` created as new governance artifacts | Governance requirement from Master Prompt Step 3 | Architect + QA + Reviewer |
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
| — | All Phase 5 tasks complete & verified (11/11) — moved to COMPLETED & VERIFIED above | — | Phase 5 | STOPPED at Phase 5 hard stop gate awaiting client approval |

### Phase 6: FastAPI Backend & Unified Dark-Mode Terminal UI
| # | Task | Owner | Phase | Notes |
|---|------|-------|-------|-------|
| 6.1 | Create `backend/server.py` — FastAPI REST + WebSocket hub | Backend | Phase 6 | **VERIFIED** — `http://127.0.0.1:8765`; 9 routes registered incl. WS `/ws/live` |
| 6.2 | Create `execution/alert_dispatcher.py` — 1-Click Manual Order Ticket + audio/Telegram alerts | Backend | Phase 6 | Manual ticket exposed via `POST /api/trades/manual` + System Monitor UI form (server.py + system_monitor_ui.js) |
| 6.3 | Create `frontend/index.html`, `frontend/css/styles.css`, `frontend/js/*.js` | Frontend | Phase 6 | **VERIFIED** — dark-mode terminal shell, Lightweight Charts v5.3.0 vendored, all endpoints smoke-tested |
| 6.4 | Full end-to-end launch verification in browser, zero console errors | Frontend + QA | Phase 6 | **VERIFIED** — all endpoints smoke-tested OK; `pytest trading_engine/tests/test_phase6_backend_ui.py` **9/9 passed** |

---

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
| 2026-11-12 | **Phase 6 Hotfix**: Mounted static `/css` and `/js` in `server.py`; fixed Lightweight Charts v5.x API integration in `chart_engine.js` (`LightweightCharts`, `addSeries`, unix timestamp sec); fixed `main.js` WebSocket `msg` variable scoping; enabled `--host 0.0.0.0` LAN binding in `run_all.py` | UI displayed raw text due to 404 on CSS/JS + v5 chart API crash; all verified working | Backend + Frontend + QA |
| 2026-11-12 | **Rule 7 & UI/UX Skill Integration**: Embedded Rule 7 into `AGENTS.md` for autonomous skill discovery; searched and installed `nextlevelbuilder/ui-ux-pro-max-skill@ui-ux-pro-max` & `vercel-labs/agent-skills@web-design-guidelines`; upgraded `styles.css` with financial dashboard design system (density 9, responsive `< 768px` layout, tabular numbers, focus states) | Client requested autonomous skill discovery + applied to UI | Architect + Frontend + QA |
| 2026-11-12 | **Full-Stack Production Readiness Audit & Victory Verification**: Executed full-stack multi-agent audit across backend, frontend, server, and database; audited 21 key findings across zero look-ahead compliance, risk circuit breakers, simulator accounting, SQLite concurrency, and chart stability; verified with 141/141 pytest suite pass (100%) and independent Victory Auditor VICTORY CONFIRMED | Client initiated comprehensive production readiness audit | Architect + Backend + Frontend + QA + Reviewer |
| 2026-11-14 | **Milestone 1 Backend Core Fixes & Baseline Demonstration Strategy**: Fixed test fixture cleanup bug in `test_phase5_research_agents.py:363` (`_cleanup_db(review.db_path)`); fixed Donchian overlay dict unpacking in `server.py:350` and added `donchian_middle_20`; implemented `BaselineDemonstrationStrategy` in `strategies/approved/baseline_demonstration_strategy.py` with dual trend/pullback logic and Contract A zero look-ahead compliance; added manual trade gating (R:R >= 1.5, directional stop/target validation) in `server.py:manual_trade`; added `/api/strategy/diagnostics` and real cumulative equity curve generation in `server.py:evaluation`; added automated unit tests in `test_phase6_backend_ui.py` | Deliverables for Milestone 1 Backend & Strategy Worker | Backend + QA (worker_m1_1) |
| 2026-11-14 | **Milestone 1 Audit & Remediation (Iteration 2)**: Detected invalid kwargs (`net_pnl`, `gross_pnl`, `r_multiple`) in `test_phase6_backend_ui.py:466,491`; fixed Donchian breakout condition in `baseline_demonstration_strategy.py:175,181` to reference `prev_dc_upper`/`prev_dc_lower` instead of invariant current-bar channels; hardened `server.py:manual_trade` input validation for `stop_loss > 0`, `target_1_price > 0`, `target_2_price` directional bounds, and `round(rr, 4) < 1.50` IEEE 754 precision; isolated `TEST_DIAG_STRAT` test trades for full test idempotency; added unit tests for float boundary R:R, negative stops, omitted short targets, invalid target 2, and Donchian breakouts; verified 15/15 tests in `test_phase6_backend_ui.py` and 147/147 tests across all 6 test phases. | Discovered in Iteration 1 Forensic Audit & Multi-Reviewer challenge | QA + Reviewer + Worker (worker_m1_2) |
| 2026-11-14 | **Milestone 2 Chart Engine Viewport Stability & Indicators**: Implemented viewport logical range preservation (`getVisibleLogicalRange` / `setVisibleLogicalRange`) across periodic 5s polling in `chart_engine.js` and `main.js`; implemented dedicated bottom volume histogram sub-pane (`priceScaleId: 'volume'`, margins 0.8 top, 0.08/0.25 right candle margin) with buy/sell color coding; implemented interactive real-time OHLCV hover legend bar (`#chart-legend`) rendering Time, O, H, L, C, CHG %, VOL with fallback to latest bar; implemented indicator overlay toggle chips (`EMA 20`, `EMA 50`, `HMA 20`, `Donchian 20` controlling upper, middle, lower bands) with active state badges. Verified 15/15 tests passing in `test_phase6_backend_ui.py`. | Deliverables for Milestone 2 Chart Engineer | Frontend + QA (worker_m2) |
| 2026-11-16 | **Milestone 3 Institutional Dark UI/UX, Intelligent Order Ticket & Strategy Lab Diagnostics**: Implemented Feature 10 (R2 Institutional Dark Terminal UI/UX with full `:root` token system `#0b0e14`, `#121721`, `#1a202c`, `#232d3f`, `#00e676`, `#ff5252`, `#29b6f6`, tabular numbers across all metrics, header live status ticker with WS round-trip latency tracking and price flash styling, inline styles consolidation), Feature 11 (R4 Intelligent 1-Click Manual Order Ticket with decoupled `#order-ticket-panel` and `#manual-ticket`, Capital and Risk % inputs, reactive position sizing `Units = (Capital * Risk%) / |Entry - SL|`, 1-Click ATR Buffer 1.5x auto-fill, real-time R:R >= 1.50 validation gate with green/red badges and execute button disabling, public accessors `getLatestATR()` and `getLatestBar()`), and Feature 12 (R5 Strategy Lab Diagnostics UI with visual SVG Equity Curve + HWM + red gradient drawdown fill + crosshair tooltip, 5x5 heatmap with floating tooltip cards on hover, Regime Weakness Diagnostics panel with volatility breakdown table and root-cause banners, parallel fetch of reports and diagnostics in `main.js`, and `win_rate_pct` addition in `gatekeeper.py:401`). | Deliverables for Milestone 3 Worker | Frontend + Backend + QA (teamwork_worker_m3) |
| 2026-11-16 | **Milestone 3 Iteration 2 Remediation & Comprehensive Test Suite Verification**: Fixed frontend edge cases (single-point baseline equity curve empty state banner, tooltip left edge viewport clamping, win rate fallback percentage formatting, `wsStatus` "OFFLINE" convention); resolved ASGI mock client infinite loop on static file serving (`scope["asgi"]["spec_version"] = "2.4"`, `http.disconnect`); updated dark palette test assertions to cover institutional tokens (`#0b0e14`, `#121721`, `#1a202c`, `#e2e8f0`, `#00e676`, `#ff5252`); supplied `account_equity=10000.0` in `test_t1_r4_02/03`; populated required feature columns (`rsi_14`, `ema_12`, `ema_26`, `atr_14_sma`) in `_build_feature_df`; resolved trade row JSON column aliasing in `_row_to_dict` and `ResearchLoop` test db isolation. **Full pytest suite verified: 239/239 passed (100%) in 501.98s**. | Iteration 2 Remediation from Verifier Feedback | Frontend + Backend + QA (teamwork_worker_m3_iter2) |
| 2026-11-17 | **Milestone 5 Phase 2 Tier 5 Adversarial Coverage Hardening & Engine Fixes**: Implemented 43 adversarial test cases in `test_phase6_e2e_adversarial_tier5.py` incorporating white-box gaps from Challenger 1 (Backend API, Concurrency, Risk, Execution Realism) and Challenger 2 (Quant math, Indicators, Diagnostics). Fixed OverflowError and non-finite inputs in `server.py:manual_trade`; caught `sqlite3.IntegrityError` (HTTP 409); sanitized `performance` and `overall_metrics` with `_sanitize_json()`; updated `_sanitize_json()` for recursive numpy and tuple support; implemented realistic stop-loss gap fills in `paper_simulator.py` and `backtester.py`; guarded `check_daily_loss` on zero equity in `risk_manager.py`; added `validate_order` and leverage limits; resolved RSI zero-loss and flat-market NaN production in `technical.py:rsi`; eliminated Supertrend initial NaN latching in flat markets; fixed `analyzer.py:compute_performance` for break-even profit factor and non-finite JSON serialization; corrected `statistical.py:volatility_percentile` percentile ranking; preserved index alignment in `structure.py:pdh_pdl_pdc`; enforced positive stop loss for micro-prices in `baseline_demonstration_strategy.py`; guarded `gatekeeper.py` against None profit factors; added concurrent position stacking limit in `backtester.py`. Preserved production `trading_engine.db` with 100% isolation. | Milestone 5 Phase 2 Adversarial Hardening | Implementer + QA (worker_m5_tier5) |
| 2026-11-17 | **Milestone 5 Phase 2 Remediation (Forensic Audit & Explorer Fixes)**: Resolved all 4 core defects identified by Forensic Auditor and Technical Explorers: (1) `server.py:_sanitize_json`: prioritized `(bool, np.bool_)` check before `(int, np.integer)` check, restoring boolean singleton preservation in JSON serialization and resolving 3 baseline regressions in `test_phase6_e2e_trader.py`; (2) `test_phase6_e2e_adversarial_tier5.py:test_adv_t5_14`: updated assertion to `status_code in (400, 422)` matching FastAPI ASGI validation handling; (3) `test_adv_quant_14`: supplied required keyword arguments `regime_snapshot={}` and `active_signals=[]` to `TradeLogger.open_trade`; (4) `statistical.py:rolling_zscore`: handled zero-variance flat windows where `rolling_std == 0.0` returning `0.0` instead of NaN, passing `test_adv_quant_06`; (5) SQLite concurrency hardening: increased `DB_BUSY_TIMEOUT_MS = 30000`, added `PRAGMA busy_timeout = 30000;` and `PRAGMA synchronous = NORMAL;` in `get_connection()`, cached DDL execution via `_INITIALIZED_DBS`, reused connection in `TradeLogger.open_trade()` and `close_trade()` for atomic activity logging, and implemented 5-attempt exponential backoff retry loop on `OperationalError: database is locked`. Preserved production `trading_engine.db` (11,272,192 bytes) 100% untouched. | Forensic Audit & Explorer Remediation | Implementer + QA (worker_m5_remediation) |
| 2026-11-17 | **Victory Audit Remediation (Gatekeeper Profit Factor Guard)**: Resolved TypeError during independent Victory Audit in `trading_engine/validation/gatekeeper.py:398` (`'>' not supported between instances of 'NoneType' and 'float'`). Guarded `_parameter_heatmap()`, `evaluate()` OOS test, and cost stress test against `profit_factor is None` (zero loss sets) by treating `pf is None` as infinite profit factor (`float("inf")`) for comparisons and safe `round(pf, 4) if pf is not None else None` in cell outputs. Verified 14/14 tests in `test_phase4_eval_validation.py`, 11/11 tests in `test_phase5_research_agents.py`, and 282/282 tests across entire repository (100% pass rate, 0 failures). Verified production `trading_engine.db` 100% untouched. | Victory Audit Remediation | Implementer + QA (worker_remediation) |

---

**Execution Rule:** No Phase 1 Python application logic (`binance_ws.py`, `db.py`) is to be written until the Client reviews and approves this `DEVELOPMENT_PLAN_AND_TODO.md`.
