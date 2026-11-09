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
