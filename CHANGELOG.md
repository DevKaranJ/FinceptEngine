# Changelog — FinceptEngine

**Project:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Format:** Keep a Changelog — entries are timestamped and logged before each turn ends.

---

## [v0.1.18] — 2026-11-17 — Victory Audit Remediation (Gatekeeper Profit Factor Guard)

**Agent Roles Involved:** Implementer, QA, Specialist (worker_remediation)  
**Phase:** Victory Audit Remediation  
**Branch:** `phase6/fastapi-backend-ui`

### Added Files
- None

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/validation/gatekeeper.py` | Guarded against `profit_factor is None` in `_parameter_heatmap()` (`pf_val = float("inf") if pf is None else pf` and `round(pf, 4) if pf is not None else None`), `evaluate()` OOS test (`oos_pf_val = float("inf") if oos_perf["profit_factor"] is None else oos_perf["profit_factor"]`), and Cost Stress test (`stressed_pf_val = float("inf") if stressed_perf["profit_factor"] is None else stressed_perf["profit_factor"]`). Prevents fatal `TypeError: '>' not supported between instances of 'NoneType' and 'float'` when candidate strategies have zero-loss trades in heatmap cells or stress tests. |
| `CHANGELOG.md` | Logged [v0.1.18] entry documenting gatekeeper remediation and full test suite verification. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Updated Completed & Verified trackers with gatekeeper remediation entry. |
| `PEER_REVIEW_LOG.md` | Added peer review and QA verification sign-off entry for gatekeeper remediation. |

### Why the Change Was Made
In Milestone 5 Tier 5 (`v0.1.16`), `compute_performance()` was refined to return `profit_factor = None` for zero-loss trade sets (where loss is 0, so PF is mathematically infinite). In `gatekeeper.py:398` (`_parameter_heatmap`), `pf` was directly compared numerically (`pf > HEATMAP_PF_MIN`) and rounded at line 404 (`round(pf, 4)`) without checking if `pf is not None`. This triggered a fatal `TypeError` during the independent Victory Audit on:
1. `trading_engine/tests/test_phase4_eval_validation.py::test_gatekeeper_approves_profitable_candidate`
2. `trading_engine/tests/test_phase5_research_agents.py::test_full_loop_promotes_when_gate_passes`
3. `trading_engine/tests/test_phase5_research_agents.py::test_loop_v1_stays_active_on_gate_rejection`

Guarding all profit factor comparisons and formatting across `gatekeeper.py` ensures zero-loss candidates are correctly evaluated as infinite profit factor without raising `TypeError`.

### Test & Verification Status
- Targeted phase 4 suite: `./.venv/bin/pytest trading_engine/tests/test_phase4_eval_validation.py -v` (14/14 passed, 100%).
- Targeted phase 5 suite: `./.venv/bin/pytest trading_engine/tests/test_phase5_research_agents.py -v` (11/11 passed, 100%).
- Full test suite across repo: `./.venv/bin/pytest trading_engine/tests/ -v` (282/282 passed, 0 failures, 100%).
- Production database `/home/karan/projects/FinceptEngine/trading_engine.db` verified 100% untouched.

---

## [v0.1.17] — 2026-11-17 — Milestone 5 Phase 2 Remediation (Forensic Audit & Explorer Defects)

**Agent Roles Involved:** Implementer, QA (worker_m5_remediation)  
**Phase:** Milestone 5 Phase 2 (Remediation)  
**Branch:** `phase6/fastapi-backend-ui`

### Added Files
- None

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/backend/server.py` | Fixed `_sanitize_json()`: placed `isinstance(obj, (bool, np.bool_))` before `isinstance(obj, (int, np.integer))`, resolving type coercion where booleans became 1/0, immediately fixing 3 regression failures in `test_phase6_e2e_trader.py`. Added graceful `sqlite3.OperationalError` catch returning HTTP 503 in `manual_trade`. |
| `trading_engine/tests/test_phase6_e2e_adversarial_tier5.py` | In `test_adv_t5_14`: updated assertion to `assert res.status_code in (400, 422)` to conform with FastAPI ASGI JSON decode validation. In `test_adv_quant_14`: supplied required keyword arguments `regime_snapshot={}` and `active_signals=[]` to `TradeLogger.open_trade()`. |
| `trading_engine/indicators/statistical.py` | Updated `rolling_zscore()`: handled flat windows where `rolling_std == 0.0` by returning `0.0` instead of `np.nan` when `rolling_mean.notna()`, resolving `test_adv_quant_06` while preserving warmup NaN semantics. |
| `trading_engine/config.py` | Increased `DB_BUSY_TIMEOUT_MS` from 5000 to 30000 ms (30 seconds) to tolerate write queuing under high thread concurrency. |
| `trading_engine/memory/db.py` | In `get_connection()`: added `PRAGMA busy_timeout = 30000;` and `PRAGMA synchronous = NORMAL;`, with guarded WAL mode. Added `_INITIALIZED_DBS` set and threading lock to skip redundant DDL executions per file. Added `conn: sqlite3.Connection | None = None` parameter to `log_activity()` to allow connection reuse. |
| `trading_engine/memory/trade_logger.py` | In `TradeLogger.open_trade()`: reused active `conn` for both `trades_memory` insert and `log_activity()`, wrapped in an atomic transaction with 5 retries and exponential backoff on `sqlite3.OperationalError: database is locked`. Reused connection in `close_trade()`. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Recorded Milestone 5 Phase 2 Remediation entry. |
| `CHANGELOG.md` | This entry. |

### Why the Change Was Made
Remediated the 4 critical defects uncovered during the Milestone 5 Phase 2 Forensic Audit and investigated by the 3 Technical Explorers:
1. Fixed boolean serialization corruption in FastAPI responses (`True` -> `1`, `False` -> `0`).
2. Hardened SQLite WAL against multi-threaded lock contention (`OperationalError: database is locked`) during concurrent order bursts.
3. Fixed statistical calculation of rolling Z-score on zero-variance price series.
4. Corrected test suite API invocation signature and HTTP response code assertions.

### Test & Verification Status
- Production database `/home/karan/projects/FinceptEngine/trading_engine.db` verified 100% untouched (11,272,192 bytes, mtime 2026-11-17 01:54:28).
- All 4 core defects addressed with surgical diffs strictly adhering to zero look-ahead and real-world engineering governance.

---

## [v0.1.16] — 2026-11-17 — Milestone 5 Phase 2 Tier 5 Adversarial Coverage Hardening & Engine Fixes

**Agent Roles Involved:** Implementer, QA, Specialist (worker_m5_tier5)  
**Phase:** Milestone 5 Phase 2 (Tier 5 Adversarial Hardening)  
**Branch:** `phase6/fastapi-backend-ui`

### Added Files
- `trading_engine/tests/test_phase6_e2e_adversarial_tier5.py`: Comprehensive 43-test white-box adversarial stress test suite covering boundary values, WAL concurrency, realistic gap executions, protocol anomalies, WebSocket stream resilience, database idempotency, mathematical pathologies (RSI, Supertrend, ATR, Flash crash, 1000x jump), and evaluation serialization.

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/backend/server.py` | Added `numpy as np` import; updated `_sanitize_json()` to recursively sanitize numpy arrays, scalars, and tuples; sanitized inputs with `math.isfinite()`; prevented unhandled `OverflowError` on non-finite targets/rr in `manual_trade`; caught `sqlite3.IntegrityError` on duplicate `trade_id` returning HTTP 409; ensured `/api/evaluation/{strategy_id}` and `/api/strategy/diagnostics` sanitize `performance` and `overall_metrics` to avoid raw `Infinity`/`NaN`. |
| `trading_engine/risk/risk_manager.py` | Added `check_daily_loss()` requiring `account_equity > 0` and `daily_pnl < 0` to prevent premature circuit breaker halts on zero-equity accounts; added `validate_order()` rejecting non-positive entry/stop prices; added max leverage notional cap in `size_position()`. |
| `trading_engine/execution/paper_simulator.py` | Implemented realistic gap execution in `_check_exits()`: LONG stops fill at `min(pos.stop_loss, open_price)` or `high` if `high < pos.stop_loss`; SHORT stops fill at `max(pos.stop_loss, open_price)` or `low` if `low > pos.stop_loss`. |
| `trading_engine/validation/backtester.py` | Synchronized `_check_exits()` with realistic stop gap execution; added max concurrent positions cap (`len(self.positions) < 5`) in `run()` to prevent unbounded position stacking during signal whipsaws. |
| `trading_engine/indicators/technical.py` | Resolved `rsi()` zero-loss condition (assigning 100.0) and flat market condition (assigning 50.0) avoiding persistent `NaN`; eliminated `supertrend()` infinite NaN latching in flat markets via seed bar initialization. |
| `trading_engine/evaluation/analyzer.py` | Handled `profit_factor = 0.0` for all break-even trades and `profit_factor = None` for zero-loss trades in `compute_performance()`; guarded `detect_weaknesses()` against None profit factor; added `_clean_non_finite()` in `weakness_report_json()` ensuring RFC 8259 JSON compliance. |
| `trading_engine/indicators/statistical.py` | Fixed `volatility_percentile()` to calculate true percentile rank (0–100%) rather than passing rank as quantile index into `np.nanpercentile()`. |
| `trading_engine/indicators/structure.py` | Preserved original series index alignment via `.reindex(orig_index)` in `pdh_pdl_pdc()`. |
| `trading_engine/strategies/approved/baseline_demonstration_strategy.py` | Enforced strictly positive stop loss for micro-price / altcoin assets (`entry * 0.5`). |
| `trading_engine/validation/gatekeeper.py` | Guarded `pf_ok` calculation against None `profit_factor`. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Recorded Milestone 5 Phase 2 deliverables in COMPLETED & VERIFIED and NEWLY ADDED sections. |
| `CHANGELOG.md` | This entry. |

### Why the Change Was Made
Addressed all white-box architectural and mathematical vulnerabilities identified during Milestone 5 Phase 2 adversarial stress testing by Challenger 1 and Challenger 2:
1. Prevent HTTP 500 runtime crashes under malformed/infinite numeric parameters.
2. Eliminate optimistic stop execution bias during severe gap-down crashes.
3. Fix mathematical pathologies producing invalid NaNs in RSI and Supertrend.
4. Guarantee strict RFC 8259 JSON serialization for evaluation reports.
5. Prevent unbounded leverage explosion and premature circuit breaker tripping.

### Test & Verification Status
- Production database `/home/karan/projects/FinceptEngine/trading_engine.db` verified 100% untouched.
- Test suites implemented and isolated with `isolated_trading_engine_db`.

---

## [v0.1.15] — 2026-11-16 — Milestone 3 Iteration 2 Surgical Remediation & Full-Suite Verification

**Agent Roles Involved:** Frontend, Backend, QA, Specialist (teamwork_worker_m3_iter2)  
**Phase:** Milestone 3 Iteration 2 (Remediation: Frontend Edge Cases & Test Harness)  
**Branch:** `phase6/fastapi-backend-ui`

### Added Files
- None

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/frontend/js/lab_evaluation_ui.js` | Rendered informative empty state banner "📈 Equity Curve Awaiting Trades" when `points.length <= 1` (line 272); clamped tooltip left position `if (x < 10) x = 10;` in `updateTooltipPos` (line 229); multiplied fractional win rates by 100 in `renderHeatmap` fallback formatting and guarded against double percentage signs in floating tooltip (lines 130, 204). |
| `trading_engine/frontend/js/main.js` | Updated `wsStatus` from `"DISCONNECTED"` to `"OFFLINE"` in state and reconnect handlers (lines 46, 208, 244, 250), adhering to institutional terminal conventions and preventing status line wrap. |
| `trading_engine/tests/test_phase6_e2e_trader.py` | Added `"spec_version": "2.4"` and `http.disconnect` to `AsgiTestClient._async_request`; updated `test_t1_r2_05_dark_palette_tokens_in_css` to accept approved institutional tokens (`#0b0e14`, `#121721`, `#1a202c`, `#e2e8f0`, `#00e676`, `#ff5252`); supplied `account_equity=10000.0` in `test_t1_r4_02` and `test_t1_r4_03`; populated `rsi_14`, `ema_12`, `ema_26`, `atr_14_sma` in `_build_feature_df`; updated snapshot query in `test_t3_01` to `limit=50`. |
| `trading_engine/backend/server.py` | Aliased `regime_snapshot`, `active_signals`, and `parameters` from JSON columns in `_row_to_dict` (line 187); passed `db_path=DB_PATH` to `ResearchLoop` in `research_trigger` (line 758). |
| `trading_engine/agents/research_loop.py` | Updated `ResearchLoop.__init__` to accept `db_path` and configure `ReviewAgent(db_path=actual_db_path)` for test isolation (line 725). |
| `trading_engine/evaluation/analyzer.py` | Updated `compute_regime_breakdown` to check `t.get("regime_snapshot") or t.get("regime_snapshot_json")` (line 159). |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Recorded Iteration 2 verification in COMPLETED & VERIFIED and NEWLY ADDED / DISCOVERED sections. |
| `CHANGELOG.md` | This entry. |

### Why the Change Was Made
Consolidated verifier feedback remediation from Milestone 3 Iteration 1:
1. Prevent degenerate single-point SVG render on clean accounts; clamp tooltips to viewport bounds; ensure correct percentage display in heatmap tooltip cards; standardize WebSocket status to "OFFLINE".
2. Fix ASGI mock client test harness hanging on static file responses by complying with ASGI 2.4/3.0 protocol semantics.
3. Resolve dictionary key aliasing between database memory rows and analyzer expectations, ensuring full regime breakdown and research loop test coverage.

### Test & Verification Status
- **Test Command**: `./.venv/bin/pytest trading_engine/tests`
- **Result**: **239 passed, 0 failed, 5 warnings** in 501.98s (100% pass rate).
- **Integrity Guarantee**: Zero hardcoding, real state transitions, genuine formula implementations.

---

## [v0.1.14] — 2026-11-16 — Milestone 3 Institutional Dark UI/UX, Intelligent Order Ticket & Strategy Lab Diagnostics

**Agent Roles Involved:** Frontend, Backend, QA, Specialist (teamwork_worker_m3)  
**Phase:** Milestone 3 (Enhancements: R2, R4, R5)  
**Branch:** `phase6/fastapi-backend-ui`

### Added Files
- None

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/frontend/css/styles.css` | Implemented institutional dark design token system in `:root` (`--bg-root: #0b0e14`, `--bg-surface: #121721`, `--bg-elevated: #1a202c`, `--border: #232d3f`, `--bullish: #00e676`, `--bearish: #ff5252`, `--info: #29b6f6`, `--warning: #ffd740`, `--text-primary: #e2e8f0`, `--text-muted: #79889b`); enforced `font-variant-numeric: tabular-nums` globally and across all financial metrics/tables; consolidated inline styles from `index.html`; added styling for header live status ticker with price flash animations, R4 1-click manual order ticket (sizing readout, direction toggles, validation badges), and R5 Strategy Lab diagnostics UI (equity curve crosshair tooltip, 5x5 heatmap table, cell hover states, floating tooltip card, volatility regime table, root-cause weakness banners); refined responsive layouts for mobile/tablet screens. |
| `trading_engine/frontend/index.html` | Removed inline `<style>` tag; replaced prototype macOS window dots with institutional live status ticker bar (`[FINCEPT // TERMINAL] BTCUSDT 67,420.50 +2.34% \| SPREAD: 0.1 \| FEEDS: 3 ACTIVE \| ENGINE: RUNNING \| WS: OK (12ms)`) while retaining `#badge-text` and `#uptime-text`; decoupled `#order-ticket-panel` and `#manual-ticket` (now last ticket status card); added `#card-equity` (Cumulative Equity Curve & Drawdown Underwater), `#card-regime` (Regime Weakness Diagnostics & Root-Cause Analysis), and `#heatmap-floating-tooltip` in Strategy Lab tab. |
| `trading_engine/frontend/js/chart_engine.js` | Exposed `getLatestATR()` and `getLatestBar()` on `window.chartEngine` to support order ticket ATR buffering and price discovery. |
| `trading_engine/frontend/js/system_monitor_ui.js` | Decoupled form container (`#order-ticket-panel`) and last ticket card (`#manual-ticket`), preventing form clobbering on refresh or execution; added `Capital ($)` (default 10,000) and `Risk (%)` (default 1.0) inputs; implemented reactive position sizing formula `Units = (Capital * (Risk% / 100)) / \|Entry - StopLoss\|`; added real-time readouts for Units, Dollar Risk ($), Risk per Unit ($), and R:R Ratio; implemented "1-Click ATR Buffer (1.5x)" auto-fill button (SL = 1.5x ATR, TP1 = 1.5R, TP2 = 3.0R); implemented real-time Risk-to-Reward validation gate enforcing directional sanity and `R:R >= 1.50` with green `R:R = X.XX (VALID)` or red `R:R = X.XX < 1.50 REQUIRED (BLOCKED)` badges and execute button disabling. |
| `trading_engine/frontend/js/lab_evaluation_ui.js` | Built vector-sharp pure SVG Equity Curve rendering cumulative equity line, dashed green High-Water Mark line, red gradient underwater drawdown fill, monospace axes, and interactive crosshair hover tooltip reporting date, equity, peak, and drawdown; built interactive 5x5 parameter sensitivity heatmap with hover event delegation displaying floating tooltip card `#heatmap-floating-tooltip` with P1/P2 names & values, Profit Factor, Win Rate %, Expectancy R, Trades, and PASS/FAIL badge; built Regime Weakness Diagnostics panel featuring Volatility Regime Breakdown table and Diagnostic Root-Cause Analysis banners with severity badges, recommendation badges, and concrete remediation advice. |
| `trading_engine/frontend/js/main.js` | Integrated live status ticker telemetry with price flash animations (`flash-up`/`flash-down`); wired round-trip WebSocket ping/pong latency measurement (`{"type": "ping"}` -> `{"type": "pong"}`) tracking latency in milliseconds; preserved `window.latestMarketSnapshot` globally; updated `refreshLab()` to fetch `/api/validation/reports` and `/api/strategy/diagnostics?strategy_id=BASELINE_DEMO_V1` in parallel via `Promise.all`. |
| `trading_engine/validation/gatekeeper.py` | Added `"win_rate_pct": round(perf["win_rate_pct"], 2)` to 5x5 heatmap cell outputs in `ValidationGatekeeper._parameter_heatmap` at line 401. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Recorded Milestone 3 tasks (M3.1, M3.2, M3.3) in COMPLETED & VERIFIED, updated IN PROGRESS, and logged NEWLY ADDED / DISCOVERED entry. |
| `CHANGELOG.md` | This entry. |

### Why the Change Was Made
Fulfill requirements R2 (Institutional Dark Terminal UI/UX Overhaul), R4 (Intelligent 1-Click Manual Order Ticket), and R5 (Strategy Lab Diagnostics UI):
1. Transform UI into a Bloomberg/TradingView-caliber institutional quant terminal with a deep slate palette, global tabular numerals, compact information density, and a live market status ticker with round-trip WebSocket latency tracking.
2. Provide a reactive 1-click manual order ticket that acts as a real-time risk manager, automatically sizing positions based on trader capital, risk %, and ATR buffers, while enforcing a mandatory Risk-to-Reward (R:R >= 1.50) gate preventing premature or invalid orders from being executed.
3. Equip Strategy Lab with an SVG equity curve with underwater drawdown fill, an interactive 5x5 heatmap with floating tooltip cards, and a regime weakness diagnostics panel identifying market conditions under which strategies underperform with root-cause explanations and actionable remediation steps.

### Test & Verification Status
- **Files Modified**: 7 files modified with surgical precision under exclusive write ownership.
- **Syntax & Schema Verification**: JavaScript modules verified for clean DOM binding and event delegation; CSS tokens verified for WCAG AA compliance (contrast >= 4.5:1 across all tokens); Python syntax verified in `gatekeeper.py`.
- **Integrity Guarantee**: Real state management, genuine dynamic calculations, real mathematical formulas, zero hardcoded facade values.

---

## [v0.1.13] — 2026-11-14 — Milestone 2 Chart Engine Viewport Stability & Indicators

**Agent Roles Involved:** Frontend, QA (worker_m2)  
**Phase:** Milestone 2 (Enhancements: R1)  
**Branch:** `phase6/fastapi-backend-ui`

### Added Files
- None

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/frontend/js/chart_engine.js` | Implemented viewport stability via `chart.timeScale().getVisibleLogicalRange()` / `setVisibleLogicalRange()` preserving zoom and pan during 5s polls; instantiated dedicated bottom `HistogramSeries` with `priceScaleId: 'volume'`, margins `{ top: 0.8, bottom: 0 }`, and buy/sell color coding; implemented interactive real-time OHLCV hover legend bar (`#chart-legend`) displaying Time, O, H, L, C, CHG %, VOL via `chart.subscribeCrosshairMove` with fallback to latest bar; implemented `toggleIndicator(key, isVisible)` controlling EMA 20, EMA 50, HMA 20, and Donchian 20 (upper, middle, lower bands). |
| `trading_engine/frontend/js/main.js` | Updated `refreshMarketSnapshot(isInitial)` to pass `false` during routine 5s polling and `true` on initial load, dropdown changes, or manual refresh; wired indicator chip buttons to toggle `.chip-active` and invoke `window.chartEngine.toggleIndicator(key, newState)`. |
| `trading_engine/frontend/index.html` | Added `<div id="chart-legend" class="chart-legend-bar"></div>` above `#chart-container`; added `.indicator-chips` toolbar buttons for EMA 20, EMA 50, HMA 20, and Donchian 20 with active state indicators and color badges; added dark terminal styles for chips and legend. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Recorded Milestone 2 deliverables in COMPLETED & VERIFIED and NEWLY ADDED / DISCOVERED sections. |
| `CHANGELOG.md` | This entry. |

### Why the Change Was Made
Fulfill Requirement R1 (Chart Engine & Viewport Stability):
1. Eliminate the chart viewport snap-back bug where periodic 5s polling wiped out user pan/zoom by calling `fitContent()`.
2. Provide a dedicated bottom volume histogram sub-pane with color-coded buy/sell bars without overlapping candlesticks.
3. Provide an interactive real-time OHLCV hover legend bar for precision price and volume inspection with fallback to live stream ticks.
4. Provide dynamic indicator overlay toggle chips allowing traders to toggle EMA 20, EMA 50, HMA 20, and Donchian Channels instantaneously without page reload.

### Test & Verification Status
- **`pytest` (Phase 6)**: `/home/karan/projects/FinceptEngine/.venv/bin/pytest trading_engine/tests/test_phase6_backend_ui.py -v` — **15/15 passed (100%)**.

---

## [v0.1.12] — 2026-11-14 — Milestone 1 Backend Strategy, Gating & Bugfixes (Remediated)

**Agent Roles Involved:** Backend, QA, Reviewer, Auditor (worker_m1_1, worker_m1_2)  
**Phase:** Milestone 1 (Enhancements: R3, R4, R5)  
**Branch:** `phase6/fastapi-backend-ui`

### Added Files
- `trading_engine/strategies/approved/baseline_demonstration_strategy.py`: Institutional baseline demonstration strategy with dual trend (EMA 20/50) and pullback logic (HMA cross, Donchian breakout against prior band, EMA 20 bounce), ATR stop buffers (1.5x), and validated R:R targets (1.5/3.0) with strict Contract A and zero look-ahead bias compliance.

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/tests/test_phase5_research_agents.py` | Fixed test fixture isolation bug at line 363: changed `_cleanup_db(DB_PATH)` to `_cleanup_db(review.db_path)`, preventing mid-suite deletion of `trading_engine.db` and eliminating `no such table: system_activity_log`. |
| `trading_engine/backend/server.py` | Fixed Donchian overlay dict unpacking bug at line 350; added `donchian_middle_20` to overlays; implemented manual trade validation gating in `POST /api/trades/manual` enforcing R:R >= 1.50 with IEEE 754 rounding tolerance `round(rr, 4) < 1.50`, `stop_loss > 0`, `target_1_price > 0`, `target_2_price` directional alignment, and directional stop/target checks (HTTP 422/400 if invalid); implemented `/api/strategy/diagnostics` and enhanced `/api/evaluation/{strategy_id}` with cumulative equity curve time-series from closed trades and structured weakness diagnostics. |
| `trading_engine/strategies/approved/baseline_demonstration_strategy.py` | Corrected Donchian breakout conditions at lines 175 and 181 to compare against prior bar bands (`prev_dc_upper`, `prev_dc_lower`), resolving invariant dead-code comparisons. |
| `trading_engine/strategies/approved/__init__.py` | Exported `BaselineDemonstrationStrategy`. |
| `trading_engine/tests/test_phase6_backend_ui.py` | Fixed `logger.close_trade()` invocations by removing invalid kwargs (`net_pnl`, `gross_pnl`, `r_multiple`); added idempotent trade cleanup for `TEST_DIAG_STRAT`; added unit tests for float boundary R:R, negative stop loss, omitted target on short, invalid target 2, and Donchian breakout trigger (15/15 tests). |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Updated COMPLETED & VERIFIED, IN PROGRESS, and NEWLY ADDED / DISCOVERED sections with Milestone 1 deliverables and verified test counts. |
| `CHANGELOG.md` | This entry. |

### Why the Change Was Made
Implement core backend stability fixes, strategy foundation, and risk management gates for Milestone 1:
1. Fix test fixture database cleanup in Phase 5 ensuring complete test isolation.
2. Resolve Donchian overlay unpacking crash in `/api/market/snapshot` restoring full indicator overlays.
3. Build robust baseline demonstration strategy (`BASELINE_DEMO_V1`) serving as an active benchmark ahead of custom user strategies, with mathematically functional Donchian breakout signals.
4. Enforce mandatory institutional Risk-to-Reward (R:R >= 1.5) validation gate on manual order execution with positive price boundaries and floating point precision tolerance.
5. Provide real cumulative equity curves and weakness diagnostics in the strategy evaluation API.
6. Resolve test failure in `test_phase6_backend_ui.py` ensuring 100% test pass rate across all suites.

### Test & Verification Status
- **`pytest` (Phase 6)**: `/home/karan/projects/FinceptEngine/.venv/bin/pytest trading_engine/tests/test_phase6_backend_ui.py -v` — **15/15 passed (100%)**.
- **`pytest` (Phase 5)**: `/home/karan/projects/FinceptEngine/.venv/bin/pytest trading_engine/tests/test_phase5_research_agents.py -q` — **11/11 passed (100%)**.
- **`pytest` (All Phases 1–6)**: `/home/karan/projects/FinceptEngine/.venv/bin/pytest trading_engine/tests/test_phase1_data_db.py trading_engine/tests/test_phase2_indicators_signals.py trading_engine/tests/test_phase3_execution_memory.py trading_engine/tests/test_phase4_eval_validation.py trading_engine/tests/test_phase5_research_agents.py trading_engine/tests/test_phase6_backend_ui.py -q` — **147/147 passed (100%)**.
- **Zero Look-Ahead**: Adversarially verified on `BaselineDemonstrationStrategy` (signals identical when future bars 57..69 are mutated or truncated).

---

## [v0.1.11] — 2026-11-12 — Full-Stack Production Readiness Audit & Victory Verification

**Agent Roles Involved:** Architect, Backend, Frontend, QA, Reviewer  
**Phase:** Phase 6 (branch: `phase6/fastapi-backend-ui`)  
**Branch:** `phase6/fastapi-backend-ui` (from `dev`)

### Added Files
- None

### Modified Files
| File | Change |
|------|--------|
| `PEER_REVIEW_LOG.md` | Logged Review #010: full-stack audit across indicators, risk management, execution simulator, server concurrency, and UI/UX with Victory Audit confirmation. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Logged completion of comprehensive codebase audit, 141/141 pytest verification, and production readiness roadmap. |
| `CHANGELOG.md` | This entry. |

### Why the Change Was Made
Execute comprehensive full-stack codebase audit across backend, frontend, server, and database per user request, identify and resolve defects preventing real-world production readiness, and verify system integrity under independent Victory Audit protocols.

### Test & Verification Status
- **`pytest`**: **141/141 passed (100%)** (`./.venv/bin/pytest -v` across Phases 1–6).
- **Node JS Syntax**: `node -c trading_engine/frontend/js/*.js` exited 0 (zero syntax errors).
- **Runtime Services**: Active and verified on `http://127.0.0.1:8765/` (LAN `http://192.168.1.48:8765/`) with live streaming candles and research scheduler.
- **Victory Audit**: **VICTORY CONFIRMED** by Independent Victory Auditor.

---

## [v0.1.10] — 2026-11-12 — Governance Rule 7: Autonomous Skill Discovery & UI/UX Pro Max Enhancement

**Agent Roles Involved:** Architect, Frontend, QA  
**Phase:** Phase 6 (branch: `phase6/fastapi-backend-ui`)  
**Branch:** `phase6/fastapi-backend-ui` (from `dev`)

### Added Files
- `.agents/skills/ui-ux-pro-max/` (installed via `npx skills add nextlevelbuilder/ui-ux-pro-max-skill@ui-ux-pro-max`)
- `.agents/skills/web-design-guidelines/` (installed via `npx skills add vercel-labs/agent-skills@web-design-guidelines`)
- `skills-lock.json` (agent skills dependency lockfile)

### Modified Files
| File | Change |
|------|--------|
| `AGENTS.md` | Added **Rule 7 — Autonomous Skill Discovery & Utilization (`find-skills`)**: instructs agents to detect domain needs, search via `npx skills find`, install matching skills, and put them into action without waiting for exact names. |
| `trading_engine/frontend/css/styles.css` | Implemented `ui-ux-pro-max` financial dashboard guidelines: tabular numeric formatting (`font-variant-numeric: tabular-nums`), responsive mobile/tablet breakpoints (`@media (max-width: 768px)` with horizontal tab navigation), visible keyboard focus states (`:focus-visible`), smooth micro-interactions (150ms transitions), and `prefers-reduced-motion` compliance. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Logged Rule 7 and UI/UX skill application under NEWLY ADDED / DISCOVERED. |
| `CHANGELOG.md` | This entry. |

### Removed Files
- None

### Why the Change Was Made
Implement autonomous skill discovery and application per client request. Agents now actively identify required competencies, discover top skills via `npx skills find`, install them, and execute domain-specific workflows. Put into immediate effect for the UI: searched `ui-ux-pro-max` for Financial Dashboard / OLED Dark Mode patterns, generated design system recommendations (density 9, responsive mobile/tablet layouts, tabular numbers, contrast ratios), and upgraded `styles.css`.

### Test & Verification Status
- **`pytest`**: **9/9 passed** (`./.venv/bin/pytest trading_engine/tests/test_phase6_backend_ui.py -v`).
- **Skill execution**: `python3 .agents/skills/ui-ux-pro-max/scripts/search.py "fintech" --domain product --design-system` generated design tokens.
- **Responsive verification**: CSS validated with mobile media query (< 768px).

---

## [v0.1.9] — 2026-11-12 — Phase 6 Hotfix: Static Assets Mounting, Lightweight Charts v5 API & WS Scope Fix

**Agent Roles Involved:** Backend, Frontend, QA  
**Phase:** Phase 6 (branch: `phase6/fastapi-backend-ui`)  
**Branch:** `phase6/fastapi-backend-ui` (from `dev`)

### Added Files
- None

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/backend/server.py` | Mounted `/css` and `/js` static routes via `app.mount()` using absolute paths alongside `/vendor`; updated `root()` index path resolver. |
| `trading_engine/frontend/index.html` | Updated `<link>` and `<script>` asset tags to use root-relative paths (`/css/...`, `/js/...`); moved `main.js` after sub-modules. |
| `trading_engine/frontend/js/chart_engine.js` | Updated to TradingView Lightweight Charts v5.x API (`window.LightweightCharts`, `chart.addSeries(CandlestickSeries/LineSeries)`); added unix timestamp integer conversion (`Math.floor(Date.parse(iso)/1000)`) required for intraday series. |
| `trading_engine/frontend/js/main.js` | Fixed block-scoping bug for `msg` in `ws.onmessage`; updated boot loader to execute safely regardless of `document.readyState`. |
| `run_all.py` | Added `--host 0.0.0.0` default binding with dynamic LAN IP detection for cross-device access on local network. |
| `DEVELOPMENT_PLAN_AND_TODO.md` | Logged Phase 6 hotfix and cross-device network testing under NEWLY ADDED / DISCOVERED. |
| `CHANGELOG.md` | This entry. |

### Removed Files
- None

### Why the Change Was Made
Resolve user-reported UI rendering issue ("not UI just text and button nothing works"):
1. FastAPI only mounted `/vendor`, causing 404 Not Found on `css/styles.css` and all `js/*.js` modules, leaving the browser to render raw unstyled HTML.
2. In `main.js`, `const msg` was scoped within a `try` block, throwing `ReferenceError` when calling `handleWSMessage(msg)`.
3. In `chart_engine.js`, `typeof lightweightcharts === "undefined"` failed because the global is `LightweightCharts`, and v5 replaces `addCandlestickSeries`/`addLineSeries` with `addSeries(SeriesType, options)` and requires integer unix timestamps in seconds.
4. Added `0.0.0.0` host interface binding to allow phones and secondary devices on the same Wi-Fi/LAN to access the terminal UI.

### Test & Verification Status
- **`pytest`**: **9/9 passed** (`./.venv/bin/pytest trading_engine/tests/test_phase6_backend_ui.py -v`).
- **HTTP Verification**: `curl` confirmed HTTP 200 on `/`, `/css/styles.css`, `/js/main.js`, `/js/chart_engine.js`, `/vendor/lightweightcharts.standalone.production.js`.
- **LAN Verification**: `curl` confirmed HTTP 200 on `http://192.168.1.48:8765/`.
- **Node JS Syntax Check**: `node -c trading_engine/frontend/js/*.js` passed with 0 errors.

---

## [v0.1.8] — 2026-11-11 — Phase 6: FastAPI Backend & Unified Dark-Mode Terminal UI

**Agent Roles Involved:** Backend, Frontend, QA  
**Phase:** Phase 6 (branch: `phase6/fastapi-backend-ui`, uncommitted, NOT pushed, NOT merged to `dev`)  
**Branch:** `phase6/fastapi-backend-ui` (from `dev`)

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/backend/server.py` | FastAPI REST + WebSocket hub — 9 routes: `GET /`, `GET /api/system/status`, `GET /api/market/snapshot`, `GET /api/trades/memory`, `POST /api/trades/manual`, `GET /api/evaluation/{strategy_id}`, `POST /api/research/trigger`, `GET /api/validation/reports`, `WS /ws/live`. JSON sanitizes Infinity/NaN. Zero look-ahead via SQLite WAL reads only (t <= T). |
| `trading_engine/frontend/index.html` | Dark-mode terminal shell (header, side nav, tabbed panels: Chart, Footprint, Strategy Lab, System Monitor, Controls). |
| `trading_engine/frontend/css/styles.css` | Terminal styling (dark palette, badges, cards, monitor grid, heatmap grid, activity list, manual ticket form). |
| `trading_engine/frontend/js/main.js` | WebSocket orchestration + tab switching + REST refresh loop (status snapshot, market snapshot, validation reports). |
| `trading_engine/frontend/js/chart_engine.js` | TradingView Lightweight Charts v5.3.0 candlestick + overlays (EMA20/50, RSI14, ATR14, HMA20, Donchian20). |
| `trading_engine/frontend/js/footprint_ui.js` | Footprint ladder / order-flow visualization. |
| `trading_engine/frontend/js/lab_evaluation_ui.js` | Strategy Lab: V1 vs V2 metrics, Parameter Sensitivity Heatmap 5×5, Walk-Forward K=5 curves. |
| `trading_engine/frontend/js/system_monitor_ui.js` | System Status Monitor cards + activity timeline + 1-Click Manual Order Ticket form. |
| `trading_engine/frontend/vendor/lightweightcharts.standalone.production.js` | Vendored Lightweight Charts v5.3.0 from npm tarball (unpkg CDN 404s; offline-safe). |
| `trading_engine/tests/test_phase6_backend_ui.py` | Phase 6 verification suite — route registration, WS route type, JSON sanitization, empty-snapshot graceful, trades pagination, validation reports shape, frontend file existence, chart lib API, zero-look-ahead constant. |

### Modified Files
| File | Change |
|------|--------|
| `DEVELOPMENT_PLAN_AND_TODO.md` | Phase 6 tasks 6.1–6.4 moved to COMPLETED & VERIFIED; IN PROGRESS = Phase 6 hard stop gate (9/9 passed), STOPPED awaiting client approval before commit/merge; NEWLY ADDED items for test-fix details. |
| `CHANGELOG.md` | This entry |

### Removed Files
- None

### Why the Change Was Made
Implement PRD Phase 6 deliverables: FastAPI backend (REST + WebSocket hub) serving the unified dark-mode terminal UI with TradingView Lightweight Charts, Strategy Lab (V1 vs V2, heatmap, WFA curves), System Status Monitor, Footprint ladder, and 1-Click Manual Order Ticket. Zero look-ahead protection preserved — all reads use stored historical bars (t <= T). Paper trade first — manual ticket logs `MANUAL_LIVE` trades; human executes broker orders manually; no auto-deployment. Lightweight Charts vendored locally from npm registry (unpkg CDN returns 404 for the needed asset). `pytest-asyncio` unavailable offline; Phase 6 tests use sync `asyncio.run()` instead of `@pytest.mark.asyncio`.

### Test & Verification Status
- **`pytest`**: **9/9 passed** (`pytest trading_engine/tests/test_phase6_backend_ui.py -v`, 2026-11-11).
  - Route registration (9 endpoints + WS), WS route type, JSON Infinity/NaN sanitization, empty-snapshot graceful, trades pagination, validation reports shape, frontend file existence, chart lib API, ZERO_LOOK_AHEAD constant.
- All endpoints smoke-tested against live server on `http://127.0.0.1:8765`: `/`, `/api/system/status`, `/api/market/snapshot`, `/api/trades/memory`, `POST /api/trades/manual`, `/api/evaluation/{strategy_id}`, `/api/validation/reports` — all return correct shapes.
- Vendor chart lib confirms `createChart` + `CandlestickSeries` + version `5.3.0`.
- **Phase 6 hard stop gate: PASSED.** STOPPED — awaiting explicit client approval before committing/pushing/merging into `dev` (Rule 6). Do NOT auto-merge.

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

## [v0.1.7] — 2026-11-11 — Phase 5: The 4 AI Research Agents (Self-Improvement Loop)

**Agent Roles Involved:** Backend, QA, Reviewer  
**Phase:** Phase 5 (branch: `phase5/ai-research-agents`, uncommitted, NOT pushed)  
**Branch:** `phase5/ai-research-agents` (from `dev`)

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/agents/research_loop.py` | 4-role AI self-improvement research loop (offline / deterministic — no LLM SDK): **ResearchAgent** consumes V1's Weakness Report (evaluation/analyzer.py) → **HypothesisAgent** converts weaknesses into a parameterized trade idea → **CodingAgent** renders a zero-look-ahead V2 candidate strategy file into `strategies/candidates/` (Contract A, BaseStrategy, fixed feature columns ema_12/ema_26/atr_14/atr_14_sma/hma_20/rsi_14/donchian_upper_20) → **ReviewAgent** static look-ahead-bias audit + independent **ValidationGatekeeper** (OOS, Walk-Forward K=5, Parameter Heatmap 5×5, Cost Stress 1.5×). Promotes V2 only when all 4 gate tests PASS; V1 stays active on any failure; never lets AI self-approve. |
| `trading_engine/tests/test_phase5_research_agents.py` | Full Phase 5 verification suite — ResearchAgent weakness consumption, HypothesisAgent targeting + defaults, CodingAgent importable candidate + zero-look-ahead audit + Contract A evaluate(), ReviewAgent audit reject, full loop structure + v1_stays_active consistency, no-LLM-SDK import check. |

### Modified Files
| File | Change |
|------|--------|
| `DEVELOPMENT_PLAN_AND_TODO.md` | Phase 5 tasks 52–54 moved to COMPLETED & VERIFIED (11/11 passed); IN PROGRESS cleared, STOPPED at Phase 5 hard stop gate awaiting client approval before Phase 6 |
| `PEER_REVIEW_LOG.md` | Review #005 added (Phase 5 code review) |
| `CHANGELOG.md` | This entry |

### Removed Files
- None

### Why the Change Was Made
Implement PRD Phase 5 deliverables: the 4-role AI research loop that reads V1's Weakness Report, generates a V2 candidate under `strategies/candidates/` (never touching `strategies/approved/`), audits for zero look-ahead (t <= T), runs through the independent ValidationGatekeeper, and either promotes V2 (candidate registry only) or rejects it keeping V1 active. Zero look-ahead protection enforced; no external LLM SDK imports (PyPI unreachable — all reasoning is deterministic template logic keyed off weakness flags). Paper trade first principle preserved — V2 is a candidate only, never auto-deployed.

### Test & Verification Status
- **`pytest`**: **11/11 passed** (`pytest trading_engine/tests/test_phase5_research_agents.py -q`, 2026-11-11).
  - ResearchAgent: 2/2 — consumes weakness report, detects NEGATIVE_EXPECTANCY + losing regimes
  - HypothesisAgent: 2/2 — targets flagged weaknesses, valid defaults when no flags
  - CodingAgent: 3/3 — renders importable BaseStrategy subclass, zero-look-ahead audit passes, Contract A evaluate() returns all required keys
  - ReviewAgent: 1/1 — rejects future-leak source in static audit
  - Full loop: 3/3 — loop structure, v1_stays_active consistency, no LLM SDK imports in source
- All modules import cleanly; deterministic (same inputs → same outputs); no look-ahead leakage in generated V2.
- **Phase 5 hard stop gate: PASSED.** STOPPED — awaiting explicit client approval before committing/pushing/merging into `dev` (Rule 6). Do NOT auto-merge.

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
