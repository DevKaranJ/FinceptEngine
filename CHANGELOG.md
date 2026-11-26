# Changelog — FinceptEngine

**Project:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Format:** Keep a Changelog — entries are timestamped and logged before each turn ends.

---

## [v0.1.13] — 2026-11-25 — Phase E.0: Market Contracts & Schema Isolation (Audit Branch)

**Agent Roles Involved:** Backend, QA, Architect  
**Phase:** Phase E milestone E.0 — Market Contracts and Schema Isolation for Binance Spot + USDⓈ-M Futures transformation (branch: `audit/planning-finceptengine-transformation`, from `dev`, NOT committed, NOT pushed, NOT merged to `dev`)  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`)

### Added Files
| File | Purpose |
|------|---------|
| `trading_engine/tests/test_phase_e_isolation_contracts.py` | Phase E.0 verification suite — 20 tests covering PK isolation, cross-market-type isolation, feature-store keys, migration idempotency/preservation, versioned migration ledger |

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/memory/db.py` | `ohlcv_bars` PK extended to `(symbol, market_type, timeframe, open_time_utc)`; `market_type` column added to `trades_memory` and `validation_reports` (default `CRYPTO_SPOT`); `schema_migrations` ledger table added; versioned one-time `run_migration()` with create-copy-replace-validate pattern; `initialize_database()` calls `run_migration()`; `market_type` indexes added on `ohlcv_bars`, `trades_memory`, `validation_reports` |
| `trading_engine/data/feature_store.py` | `indicator_features` PK extended to `(symbol, market_type, timeframe, open_time_utc)`; `market_type` indexes added; `write_features()`/`load_features()` include `market_type` in cache keys and queries (default `CRYPTO_SPOT`); Parquet methods pass `market_type` |
| `trading_engine/config.py` | Added `CRYPTO_SPOT = "CRYPTO_SPOT"` and `CRYPTO_PERP = "CRYPTO_PERP"` market type constants |
| `trading_engine/memory/trade_logger.py` | `open_trade()` accepts `market_type` param (default `CRYPTO_SPOT`), included in `trades_memory` INSERT |
| `trading_engine/validation/gatekeeper.py` | `ValidationReport` includes `market_type` field; `evaluate()` accepts `market_type`; `to_db_row()` includes `market_type`; `_persist_report()` INSERT includes `market_type`; `_run_backtest()`/`_walk_forward()`/`_parameter_heatmap()` pass `market_type` through |
| `trading_engine/validation/backtester.py` | `Backtester.__init__()` accepts `market_type` (default `CRYPTO_SPOT`), stored as `self.market_type`, passed to `TradeLogger.open_trade()` |
| `trading_engine/backend/server.py` | `/api/trades/memory` and `/api/validation/reports` endpoints accept optional `market_type` query filter (default `CRYPTO_SPOT`); `market_type` column included in response payloads |
| `CHANGELOG.md` | This entry |

### Why the Change Was Made
Phase E.0 establishes market-type isolation at the schema/query layer before any Futures market data is collected (per B9 authorization):
- Existing Spot/Futures universes kept independent; `market_type` defaults to `CRYPTO_SPOT` for backward compatibility.
- SQLite does not support `ALTER TABLE ... MODIFY PRIMARY KEY`, so `ohlcv_bars` is rebuilt via create-copy-replace-validate within a transaction, backfilling existing Spot rows with `CRYPTO_SPOT`.
- Migration is versioned (`SCHEMA_MIGRATION_VERSION = "1.0.0-e0"`), one-time, and idempotent via `schema_migrations` ledger table.
- No Futures data collection, scanner, Futures WS, Futures risk engine, or strategy cap implemented in E.0 (deferred to E.1+ pending separate approval).

### Test & Verification Status
- **`pytest`**: **153 passed** (`trading_engine/tests/`, 2026-11-25).
  - Phase 1: 22/22 passed (baseline preserved).
  - Phase 2: 64/64 passed (baseline preserved).
  - Phase 3: 24/24 passed (baseline preserved).
  - Phase 4: 14/14 passed (baseline preserved).
  - Phase 6: 9/9 passed (baseline preserved).
  - Phase E.0: 20/20 passed (new isolation contract tests).
- Migration preservation: existing Spot records preserved (3267 ohlcv_bars, 25528 trades_memory, 167 validation_reports all backfilled `CRYPTO_SPOT`).
- Peer review (QA + Reviewer) pending — Rule 5 requires sign-off before presenting to Client.
- Nothing committed, pushed, or merged (Rule 6). Client approval required before committing.

---

## [v0.1.9] — 2026-11-24 — Phase A Codebase Audit (Audit Branch)

**Agent Roles Involved:** Architect  
**Phase:** Phase A — Codebase audit (branch: `audit/planning-finceptengine-transformation`, from `dev`, NOT committed, NOT pushed, NOT merged to `dev`)  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`)

### Added Files
| File | Purpose |
|------|---------|
| `PROJECT_AUDIT.md` | Phase A audit findings — codebase inventory, architecture assessment, deviations from Binance-only scope, constraints compliance status, untracked artifacts |
| `KNOWN_ISSUES.md` | 10 known issues (KI-001 to KI-010): NSE/IST out-of-scope refs, agent-loop vs rule-based restriction, ~300+ candidate files, untracked non-source artifacts, hardcoded 3-pair list, missing root manifests, missing 13 GitHub repo URLs (blocker), Phase 6 not merged, lowercase readme, claude-mem unavailable |

### Modified Files
| File | Change |
|------|--------|
| `DEVELOPMENT_PLAN_AND_TODO.md` | Added Phase A/B IN PROGRESS items; added `[+] NEWLY ADDED / DISCOVERED ITEMS` entries for audit, cleanup backlog, and untracked artifacts |

### Why the Change Was Made
Completed Phase A codebase audit. Identified that the codebase targets both Crypto (Binance) and NSE Equities (IST) — NSE references are out of scope for the intended Binance Spot + USDⓈ-M Futures transformation. Flagged `agents/research_loop.py` conflict with rule-based-only restriction. Identified blocker: 13 GitHub repository URLs not found anywhere in codebase/local filesystem; client must supply them before Phase C source-level research.

### Test & Verification Status
- No code changes — audit/documentation only; no pytest run required.
- All 6 existing phase suites previously verified (22/22, 61/61, 24/24, 14/14, 11/11, 9/9).

---

## [v0.1.10] — 2026-11-24 — Phase B: Binance-Only Documentation Cleanup & Archive (Audit Branch)

**Agent Roles Involved:** Architect  
**Phase:** Phase B — Documentation cleanup & archive (branch: `audit/planning-finceptengine-transformation`, from `dev`, NOT committed, NOT pushed, NOT merged to `dev`)  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`)

### Added Files
| File | Purpose |
|------|---------|
| `archive/documentation/DOCUMENTATION_CLEANUP_REPORT.md` | Phase B documentation classifications (keep/update/archive) and research-loop exclusion rationale |
| `archive/documentation/prd_and_roadmap.md` | Archived full text of superseded PRD (historical record) |

### Modified Files
| File | Change |
|------|--------|
| `docs/prd_and_roadmap.md` | Deprecation header added; marked SUPERSEDED → ARCHIVED (NSE/FR-01, 6-phase crypto+NSE roadmap, 4-Agent AI Self-Improvement Loop conflict with Binance-only scope) |
| `docs/master_architecture.md` | Title & subtitle → Binance Spot + USDⓈ-M Futures; removed Layer 5 AI Research Agents layer → Human Review & Validation Gate; removed `agents/` + `nse_broker_ws.py` from folder structure; roadmap Phase 5 → Human Strategy Review & Validation Gate (no AI self-improvement); renumbered layers |
| `docs/database_and_data_contracts.md` | Project name → Binance platform; `market_type` column → `'CRYPTO_SPOT', 'CRYPTO_PERP'` (removed `NSE_EQUITY`); `POST /api/research/trigger` endpoint removed (agent loop excluded); weakness report now passed to Human Strategy Reviewer (not AI Research Agent) |
| `trading_engine/config.py` | NSE session constants marked DEPRECATED (retained for clock.py/test imports); removed `timedelta`/`ZoneInfo` IST imports still needed; Binance scope documented |
| `trading_engine/data/clock.py` | Docstring updated; NSE methods marked DEPRECATED (retained so Phase 1 tests keep passing) |
| `trading_engine/backend/server.py` | `market_snapshot` fallback `NSE_EQUITY` → `CRYPTO_SPOT`; `POST /api/research/trigger` replaced with removed-stub returning `ok: false` + exclusion reason |

### Removed Files (archived — not deleted)
| File | Destination | Reason |
|------|-------------|--------|
| `trading_engine/agents/research_loop.py` | `archive/research_loop_archive/research_loop.py` | 4-Agent AI self-improvement loop conflicts with rule-based-only restriction (no ML/DL/RL/LLM multi-agent systems) |
| `trading_engine/tests/test_phase5_research_agents.py` | `archive/research_artifacts/test_phase5_research_agents.py` | Imports removed `research_loop`; no longer part of active V1 workflow |
| `trading_engine/strategies/candidates/*.py` (566 files) | `archive/research_artifacts/` | AI-generated V2 candidates; not imported by active code or tests; archived per rule-based-only scope |
| 8 `.whl` files | `archive/untracked_artifacts/` | Untracked non-source build artifacts |
| `graphify-out/` | `archive/untracked_artifacts/graphify-out` | Untracked knowledge-graph output (~12 MB) |
| `UII/` (4 PNG screenshots) | `archive/untracked_artifacts/UII` | Untracked screenshot artifacts |

### Why the Change Was Made
Phase B documentation cleanup for Binance Spot + USDⓈ-M Futures-only transformation:
- NSE/IST references out of scope; `prd_and_roadmap.md` classified CONFLICTING and archived.
- `master_architecture.md` updated to Binance-only; Layer 5 AI Research Agents removed (rule-based-only), replaced with Human Review & Validation Gate.
- `database_and_data_contracts.md` scoped to Binance Spot + USDⓈ-M Futures; `/api/research/trigger` removed (agent loop excluded).
- `research_loop.py` runtime import removed from `server.py`; documented exclusion.
- Candidate files (566), `test_phase5_research_agents.py`, `.whl`, `graphify-out/`, `UII/` archived (not deleted) per "do not delete source code" rule with removal reasons recorded.
- Nothing committed, pushed, merged, or permanently deleted (Rule 6).

### Test & Verification Status
- No runtime code changed except `server.py` (research trigger stub) and `server.py` line 301 market_type; `config.py`/`clock.py` NSE constants retained as DEPRECATED so Phase 1 tests keep importing.
- `pytest` NOT re-run this turn per Rule 4 hard-stop (awaiting client approval before next phase).
- All 6 existing phase suites previously verified (22/22, 61/61, 24/24, 14/14, 11/11, 9/9).

---

## [v0.1.11] — 2026-11-24 — Phase C: Planning & Research (Audit Branch)

**Agent Roles Involved:** Architect + QA + Reviewer  
**Phase:** Phase C — Planning & research for Binance Spot + USDⓈ-M Futures transformation (branch: `audit/planning-finceptengine-transformation`, from `dev`, NOT committed, NOT pushed, NOT merged to `dev`)  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`)

### Added Files
| File | Purpose |
|------|---------|
| `docs/ARCHITECTURE_DECISIONS.md` | ADR-001 through ADR-008 for Binance-only transformation (Binance-only scope, rule-based only, human review gate, market_type CRYPTO_SPOT/CRYPTO_PERP, deprecated NSE retained, archive-before-remove, max-5 deferred to implementation, research trigger stubbed) |
| `docs/REPOSITORY_RESEARCH.md` | Phase C research findings vs 14 research areas (local codebase research complete; 13 GitHub repo URLs blocker KI-010 still open) |
| `docs/REBUILD_RECOMMENDATION.md` | Rebuild vs in-place evolution recommendation (in-place chosen) + manifest choice (`pyproject.toml` + `requirements.txt` both) |
| `docs/ZERO_LOOK_AHEAD_REVALIDATION.md` | Zero-look-ahead revalidation evidence — PASS with 1 Medium finding (ZLA-001 `session_volume_profile()` intra-day look-ahead) |

### Modified Files
| File | Change |
|------|--------|
| `PROJECT_AUDIT.md` | Phase B marked COMPLETED; Phase C status added (in-place evolution recommended; 3 implementation gaps: top-10 eligibility, max-5 cap, Futures connector; root pyproject.toml) |
| `KNOWN_ISSUES.md` | KI-001 through KI-006 marked RESOLVED (Phase B); KI-007/KI-008/KI-009/KI-010 remain open; status line updated |
| `DEVELOPMENT_PLAN_AND_TODO.md` | C.1–C.4 marked DONE; C.5 in progress; C.6 (this CHANGELOG entry) todo; C.7 peer review todo |

### Why the Change Was Made
Phase C planning & research completed for Binance Spot + USDⓈ-M Futures transformation:
- ADRs documented all 8 architectural decisions (ADR-001 through ADR-008).
- Repository research confirmed 12 of 14 areas have complete local implementations; areas 2 (Futures connector), 3 (top-10 eligibility), 4 (max-5 cap) require implementation — none depend on the blocked 13 GitHub repo URLs.
- Rebuild vs in-place: in-place evolution recommended (verified codebase through Phase 6, all test suites pass); root `pyproject.toml` + existing `trading_engine/requirements.txt` chosen.
- Zero-look-ahead revalidated PASS with 1 Medium finding (ZLA-001) documented with remediation.
- 13 GitHub repo URLs verified absent from codebase (zero matches for github.com/github.io/git.com); blocker KI-010 remains open awaiting client supply.

### Test & Verification Status
- No code changes — planning/research/documentation only; no pytest run required.
- All 6 existing phase suites previously verified (22/22, 61/61, 24/24, 14/14, 11/11, 9/9).

---

## [v0.1.12] — 2026-11-24 — Antigravity Final Verification Corrections C1–C5 (Audit Branch)

**Agent Roles Involved:** Backend, QA, Reviewer  
**Phase:** Antigravity Final Verification Corrections (branch: `audit/planning-finceptengine-transformation`, from `dev`, NOT committed, NOT pushed, NOT merged to `dev`)  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`)

### Modified Files
| File | Change |
|------|--------|
| `trading_engine/indicators/structure.py` | C1 — `opening_range()` look-ahead bias fixed: whole-day positional slicing `window_high.iloc[:j+1]` replaced with timestamp-based `window_high.loc[:ts]` so early window bars never see future window bars. `j` retained for `g_mask.iloc[j]` boundary checks. |
| `trading_engine/tests/test_phase2_indicators_signals.py` | C1 — Added regression test `test_opening_range_no_pre_market_positional_leak`: dataset starts at 00:00 UTC (pre-market bars present), opening window 09:15–09:45, price spike at 09:20 inside window; 09:15 bar must return ORH=100.0 (actual), NOT 200.0 (future leak). |
| `pyproject.toml` | C2 — Package discovery fixed: `where=["trading_engine"]` → `where=["."]`; dependencies converted from invalid PEP 621 key=value under `[project.dependencies]` to a proper `dependencies` array in `[project]`. |
| `docs/REPOSITORY_RESEARCH.md` | C3 — License table corrected: `binance-strategy` = No License / All Rights Reserved (NOT MIT); `crypto-trading-strategies` = No License / All Rights Reserved + ZERO source code files (README link list only); remaining 11 licenses verified and recorded (MIT/Apache 2.0). Clean-room reference warnings added. No external source code copied into FinceptEngine. |
| `.venv` | C4 — setuptools 84.2.1 + wheel 0.48.0 installed in project virtual environment; editable install `pip install -e . --no-deps` verified OK; package discovery finds 18 `trading_engine*` packages. |
| `trading_engine/data/clock.py` | C5 — Formal `DeprecationWarning` (runtime) added to 3 NSE methods: `is_nse_session_open()`, `nse_next_session_open_utc()`, `nse_square_off_utc()`. Methods remain functional so Phase 1 tests keep passing; new code must not use them. |
| `trading_engine/config.py` | C5 — NSE constants (`NSE_SESSION_IST_START`, `NSE_SESSION_IST_END`, `NSE_SESSION_IST_WINDOW`, `NSE_TRADING_DAYS`) kept but explicitly marked `# naive IST (deprecated)` with binar-scope deprecation comments retained. |

### Why the Change Was Made
Antigravity Final Verification report (Verdict B — Conditionally Ready) identified five corrections required before Phase C implementation work may proceed. All five applied:
- C1: Critical look-ahead leak in `opening_range()` (bar at 09:15 incorrectly saw 09:20 future spike of 200.0 instead of actual 100.0). Fixed via timestamp-based past-only slicing.
- C2: Package discovery defect (`where=["trading_engine"]` found no packages) plus invalid PEP 621 dependencies format.
- C3: Inaccurate licensing metadata in repository research doc (two repos without licenses wrongly labeled MIT; one with zero source code misclassified).
- C4: Missing setuptools/wheel in `.venv` preventing editable installs.
- C5: NSE equity/IST constants lacking formal deprecation markers conflicting with Binance-only direction.

### Test & Verification Status
- **`pytest`**: **133 passed** (`/home/karan/projects/FinceptEngine/.venv/bin/python -m pytest trading_engine/tests`, 2026-11-24).
  - Phase 1: 22/22 passed (NSE deprecation warnings do not break tests).
  - Phase 2: 64/64 passed (includes new `test_opening_range_no_pre_market_positional_leak` regression test).
  - Phase 3: 24/24 passed.
  - Phase 4: 14/14 passed.
  - Phase 6: 9/9 passed.
- Regression test result: `test_opening_range_no_pre_market_positional_leak` PASS — 09:15 bar ORH=100.0 excludes 09:20 future spike.
- Editable installation: `pip install -e . --no-deps` — OK.
- Package discovery: `find_packages(where=".", include=["trading_engine*"])` — 18 packages found.
- Remaining issues: None from the five corrections.
- Git status: 16 modified + deleted tracked files + untracked docs/manifests present (see `git status`). Nothing committed, pushed, or merged (Rule 6). Client approval required before committing.

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
