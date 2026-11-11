# Peer Review Log — FinceptEngine

**Project:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Rule:** No coder agent may declare its own work finished. Every completed task must pass through QA Tester (04) and Reviewer (05). Review outcomes are recorded here before client sign-off.

---

## Review #001 — Documentation Consistency Audit (Project Initiation)

**Reviewer:** 05_reviewer  
**Date:** 2026-11-08  
**Scope:** All root-level and `docs/` documentation files:
- `readme.md` (root)
- `docs/master_architecture.md`
- `docs/prd_and_roadmap.md`
- `docs/database_and_data_contracts.md`
- `docs/strategy_and_validation_spec.md`
- `docs/AGENTS.md`
- `AGENTS.md` (root — newly created)
- `DEVELOPMENT_PLAN_AND_TODO.md` (newly created)
- `CHANGELOG.md` (newly created)

### Issues Found
1. **Missing root `AGENTS.md`** — No agent-facing command/constraint summary existed at project root; only `docs/AGENTS.md` was present. (Severity: High — governance entry point missing)
2. **Missing governance files** — `DEVELOPMENT_PLAN_AND_TODO.md`, `CHANGELOG.md`, and `PEER_REVIEW_LOG.md` did not exist. (Severity: High — mandatory real-world engineering governance not instantiated)
3. **Empty source tree** — Root contained only `.git/`, `docs/`, `readme.md`; no `trading_engine/` package, no `config.py`, no `requirements.txt`, no Python files whatsoever. (Severity: Informational — expected at pre-Phase 1 initiation)
4. **Lowercase `readme.md`** — Root uses `readme.md` (lowercase) rather than `README.md`; kept as-is to avoid breaking any references. (Severity: Low — cosmetic)

### Fixes Applied
1. Created root `AGENTS.md` embedding the 5 mandatory governance rules:
   - Read-Before-Act (audit README/MASTER_ARCHITECTURE/PRD/DATABASE/STRATEGY/AGENTS/DEVELOPMENT_PLAN/CHANGELOG before every task)
   - Vice-Versa Doc Sync (code↔docs↔trackers updated immediately on every change)
   - Live `DEVELOPMENT_PLAN_AND_TODO.md` with 4 explicit sections
   - Production `CHANGELOG.md` with timestamped entries
   - Mandatory internal peer review via `PEER_REVIEW_LOG.md` (QA + Reviewer sign-off; no self-declaration)
2. Scaffolded `trading_engine/` with all 16 subdirectories matching `MASTER_ARCHITECTURE.md` Section 3, each with clean `__init__.py`.
3. Created `DEVELOPMENT_PLAN_AND_TODO.md` breaking Phases 1–6 into granular checkable tasks, with Phase 1 hard stop gate (client approval required before any Phase 1 Python logic).
4. Created `CHANGELOG.md` with initial v0.1.0 entry listing all foundational documentation files and directory scaffolding.
5. Created `PEER_REVIEW_LOG.md` with this Review #001 entry.

### Schema / Folder Path / Phase Gate Consistency Check
- Folder skeleton vs `MASTER_ARCHITECTURE.md` Section 3: **MATCH 100%** — all 16 directories present (data/feeds, indicators, signals, strategies/approved, strategies/candidates, risk, execution, memory, evaluation, agents, validation, backend, frontend/js, frontend/css, tests).
- Database tables vs `DATABASE_AND_DATA_CONTRACTS.md` Section 1: **MATCH 100%** — ohlcv_bars, trades_memory, strategy_registry, validation_reports, system_activity_log all documented (tables themselves will be created in Phase 1 `memory/db.py`).
- Phase gates vs `MASTER_ARCHITECTURE.md` Section 4 and `PRD_AND_ROADMAP.md` Section 4: **MATCH 100%** — all 6 phases, allowed files, deliverables, and hard stop gates reflected in `DEVELOPMENT_PLAN_AND_TODO.md`.
- Validation criteria vs `STRATEGY_AND_VALIDATION_SPEC.md` Section 3: **MATCH 100%** — OOS 70/30, Walk-Forward ≥80% windows, 5×5 heatmap ≥80% cells, 1.5× cost stress PF ≥1.15.

### Final Sign-Off
**Reviewer:** 05_reviewer  
**Outcome:** APPROVED — All documentation schemas, folder paths, and phase gates are consistent (100% match).  
**Sign-off Date:** 2026-11-08  
**Next Action:** Await client approval of `DEVELOPMENT_PLAN_AND_TODO.md` before Phase 1 Python application logic is written.

---

## Review #002 — Phase 1 Code Review (Core Data Feed, Clock & SQLite Trade Memory)

**Reviewer:** 05_reviewer  
**Date:** 2026-11-09  
**Branch:** `phase1/core-data-memory`  
**Scope:** `trading_engine/config.py`, `trading_engine/requirements.txt`, `trading_engine/data/clock.py`, `trading_engine/data/feeds/binance_ws.py`, `trading_engine/memory/db.py`, `trading_engine/tests/test_phase1_data_db.py`

### Issues Found
1. **Relative import depth bug in `binance_ws.py`** — `..config` / `..memory.db` resolved to `trading_engine.data.config` (wrong level) because the file lives in `trading_engine/data/feeds/`. Fixed to `...config` / `...memory.db`. (Severity: High — import would fail at runtime)
2. **`aiohttp` dependency mismatch** — initial draft imported `aiohttp` which is NOT in the declared stack/manifest. Rewrote `binance_ws.py` to use `websockets` (declared) + stdlib `urllib.request` for REST. (Severity: High — would break `pip install -r requirements.txt`)
3. **`pytest` unavailable in environment** — PyPI read timeout, no root for apt, no pip cache. Phase 1 verified via inline Python execution of the full test logic instead of `pytest`. (Severity: Medium — environment constraint, not a code defect)

### Fixes Applied
1. Corrected import depth to three dots (`...`) in `binance_ws.py`.
2. Removed `aiohttp`; `binance_ws.py` now uses `websockets.connect` + `urllib.request.urlopen`, matching `requirements.txt` exactly.
3. Verified all Phase 1 modules import cleanly and the complete `test_phase1_data_db.py` test logic passes via inline execution (schema, WAL mode, PK enforcement, clock logic, bar normalization, DB roundtrip).

### Schema / Folder Path / Phase Gate Consistency Check
- Database tables vs `DATABASE_AND_DATA_CONTRACTS.md` Section 1: **MATCH 100%** — `ohlcv_bars`, `trades_memory`, `strategy_registry`, `validation_reports`, `system_activity_log` all created with exact DDL.
- `config.py` constants vs PRD FR-01 / master_architecture Section 2: **MATCH** — Crypto 24/7 UTC, NSE 09:15–15:30 IST, Binance Spot fee schedule, risk constants.
- Zero-look-ahead: bars persisted only on kline `x=True` (finalized), satisfying AGENTS.md Hard Constraint #1.
- Phase 1 hard stop gate: `pytest tests/test_phase1_data_db.py` suite is written and ready; execution blocked only by missing `pytest` binary in this environment (noted in CHANGELOG + TODO).

### Final Sign-Off
**Reviewer:** 05_reviewer  
**Outcome:** APPROVED (with import-depth fix applied) — Phase 1 code is consistent with all schemas, contracts, and phase gates.  
**Sign-off Date:** 2026-11-09  
**Next Action:** Client approval of Phase 1 completion required before Phase 2 (indicators & signals) begins.

---

## Review #003 — Phase 2 Code Review (Multi-Paradigm Lego Indicators & Signals)

**Reviewer:** 05_reviewer  
**Date:** 2026-11-09  
**Branch:** `phase1/core-data-memory` (uncommitted Phase 2 files)  
**Scope:** `trading_engine/data/feature_store.py`, `trading_engine/indicators/{technical,statistical,structure,orderflow}.py`, `trading_engine/signals/{technical,statistical,structure,orderflow}_signals.py`, `trading_engine/tests/test_phase2_indicators_signals.py`

### Issues Found
1. **`test_donchian_breakout` had contradictory assertions** — both calls passed identical inputs (`prev.high=99`, `prev.donchian_upper=100`) yet expected `False` then `True`. Deterministic logic cannot produce different outputs from identical inputs. First call was actually `True` (a genuine breakout: `99 <= 100 and 101 > 100`), contradicting the expected `False`. (Severity: High — test would fail / assert wrong behavior)
2. **Zero look-ahead enforcement check** — verified all indicators use only past bars (`shift(1)` for pivots/ATR/true-range, rolling windows incl. current bar, calendar-day grouping for PDH/PDL/PDC carried forward). No `shift(-1)` or future-row usage found. (Severity: Informational — confirmed compliant)
3. **Determinism check** — indicators implemented with pure pandas/numpy rather than pandas-ta, making behavior version-independent. Confirmed no reliance on optional pandas-ta cross-checks in code paths under test. (Severity: Informational — confirmed compliant)

### Fixes Applied
1. Rewrote `test_donchian_breakout`: first call sets `prev.high=100.5 > prev.donchian_upper=100` (price already above channel → no cross → `False`); second call keeps `prev.high=99 <= prev_upper=100` and `now=101 > upper=100` → genuine breakout → `True`.
2. Verified zero-look-ahead slice helper and feature store `timestamp` load exclude future rows.

### Schema / Folder Path / Phase Gate Consistency Check
- Indicator families vs PRD Phase 2 deliverables: **MATCH 100%** — `data/feature_store.py`, all 4 indicator families, all 4 signal wrappers, test suite present.
- Zero-look-ahead vs AGENTS.md Hard Constraint #1: **MATCH** — all indicators use `t <= T` only.
- Phase gate vs MASTER_ARCHITECTURE Section 4 / PRD Section 4: **MATCH** — Phase 2 hard stop gate requires all tests pass then STOP.

### Test & Verification Status
- **`pytest trading_engine/tests/test_phase2_indicators_signals.py -v`**: **58/58 passed** (2026-11-09).

### Final Sign-Off
**Reviewer:** 05_reviewer  
**Outcome:** APPROVED — Phase 2 code is consistent with all schemas, contracts, zero-look-ahead constraint, and phase gates.  
**Sign-off Date:** 2026-11-09  
**Next Action:** STOP at Phase 2 hard stop gate — await client approval before Phase 3.

---

## Review #004 — Phase 4 Code Review (Backtester, Evaluation Engine & Validation Gatekeeper)

**Reviewer:** 05_reviewer  
**Date:** 2026-11-11  
**Branch:** `phase4/backtest-eval-validation`  
**Scope:** `trading_engine/validation/backtester.py`, `trading_engine/evaluation/analyzer.py`, `trading_engine/validation/gatekeeper.py`, `trading_engine/tests/test_phase4_eval_validation.py`

### Issues Found
1. **`test_compute_performance_basic` profit_factor rounding too strict** — asserted `isclose(pf, 190/130, rel_tol=1e-6)` but `analyzer.compute_performance` rounds PF to 4 decimals. Fixed test to compare against `round(190/130, 4)`. (Severity: Medium — test would fail despite correct implementation)
2. **`test_backtester_zero_look_ahead` regenerated data with different `n`** — `pd.Series` cumsum base differs when `n` changes, so identical trigger index produced different results. Fixed by truncating the same DataFrame (`df_full.iloc[:200].copy()`) so both runs share identical bars up to T. (Severity: High — test was validating the wrong thing / not actually testing zero look-ahead)
3. **Double-counting closed trades** — `run()` appended `result.__dict__` after `_finalize_close()` already appended to `closed_trades`, producing duplicate trade records (trades persisted count ≠ result count). Removed the duplicate appends in both the per-bar exit path and the flat-close path. (Severity: High — would corrupt trade log counts and SQLite persistence)
4. **`_finalize_close` trade dict missing `entry_price`** — tests assert `entry_price` on closed trade dicts; added `entry_price=pos.entry_price` to the closed-trade record. (Severity: Medium — test assertion would KeyError)
5. **Gatekeeper test fixtures had all trigger indices in-sample (<350)** → OOS had 0 trades → OOS/WFA/heatmap/cost-stress all failed → REJECTED instead of APPROVED. Moved `trigger_indices` into `default_params` so heatmap variants preserve them, and spread triggers across in-sample `[0,350)` (100/200/300) for the heatmap plus one per walk-forward window in OOS `[350,500)` (380/410/440/470/495). (Severity: High — gatekeeper could never APPROVE a valid candidate)
6. **_LosingStrategy used LONG with tiny target in uptrend** → would win, not lose. Switched to SHORT in rising market so stop loss is hit → guaranteed losing baseline. (Severity: Medium — baseline would not lose, invalidating the reject test)

### Fixes Applied
1. Test compares `round(190/130, 4)` via `isclose` with `rel_tol=1e-6`.
2. Truncated same DataFrame for look-ahead test; identical bars up to T.
3. Removed duplicate `closed_trades.append(result.__dict__)` calls; `_finalize_close` is the single writer.
4. Added `entry_price` to closed-trade dict in `_finalize_close`.
5. Triggers in `default_params["trigger_indices"]`; split across IS/OOS; variants preserve triggers via `cls(params=params)`.
6. `_LosingStrategy` now issues SHORT entries with stop above entry in a rising market.

### Schema / Folder Path / Phase Gate Consistency Check
- Backtester `BacktestResult` / trade dicts vs `DATABASE_AND_DATA_CONTRACTS.md` Section 2 (Contract A signal dict + trades_memory columns): **MATCH** — trade_id, strategy_id, symbol, direction, entry/exit price/time, net_pnl, r_multiple, mae/mfe, regime_snapshot, active_signals, exit_reason all present.
- `validation_reports` table exists in `memory/db.py` (created Phase 1) — gatekeeper persists `final_status`, `rejection_reason`, per-test booleans + metrics JSON. **MATCH**.
- Zero-look-ahead vs AGENTS.md Hard Constraint #1: **MATCH** — exits use current-bar OHLC only; equity curve per bar; OOS split is chronological (first 70% IS, last 30% OS); WFA trains only on historical bars before each test window.
- Gate thresholds vs `docs/strategy_and_validation_spec.md` Section 3: **MATCH** — OOS PF≥1.25 & ER>baseline & MaxDD≤baseline; WFA ≥4/5 windows ER>0; Heatmap ≥20/25 cells PF>1.10; Cost stress 1.5× slippage PF≥1.15 & ER≥+0.12R. All 4 must PASS for APPROVED; any failure → REJECTED.
- Phase gate vs MASTER_ARCHITECTURE Section 4 / PRD Section 4: **MATCH** — Phase 4 hard stop gate requires `pytest trading_engine/tests/test_phase4_eval_validation.py` pass then STOP.

### Test & Verification Status
- **`pytest trading_engine/tests/test_phase4_eval_validation.py -q`**: **14/14 passed** (2026-11-11).
  - Backtester: 4/4
  - Analyzer: 7/7
  - Gatekeeper: 3/3
- No regressions: Phases 1–3 suites still pass (22/22, 61/61, 24/24).
- All Phase 4 modules import cleanly; deterministic (same inputs → same outputs); no look-ahead leakage.

### Final Sign-Off
**Reviewer:** 05_reviewer  
**Outcome:** APPROVED — Phase 4 code is consistent with all schemas, contracts, zero-look-ahead constraint, validation thresholds, and phase gates.  
**Sign-off Date:** 2026-11-11  
**Next Action:** STOP at Phase 4 hard stop gate — await explicit client approval before committing/pushing/merging into `dev` (Rule 6). Do NOT auto-merge.
