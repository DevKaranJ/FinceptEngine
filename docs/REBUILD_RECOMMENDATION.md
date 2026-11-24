# Rebuild vs. In-Place Recommendation — Phase C

**Project:** FinceptEngine — Binance Spot + USDⓈ-M Futures Trading Platform  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`, NOT committed, NOT pushed, NOT merged)  
**Date:** 2026-11-24  
**Owner:** Architect + QA + Reviewer  
**Scope:** Binance Spot + USDⓈ-M Futures only (rule-based, human-reviewed, paper-first)

---

## Executive Recommendation: **IN-PLACE EVOLUTION (do NOT rebuild)**

**Recommendation:** Continue evolving the existing v0.1.0 codebase **in place** on branch `audit/planning-finceptengine-transformation`. Do **not** start a greenfield rebuild.

**Rationale (summary):** The codebase is complete, tested, and internally consistent through Phase 6 (all 6 phase suites verified: 22/22, 61/61, 24/24, 14/14, 11/11, 9/9). The Binance-only transformation requires primarily **documentation cleanup** (done in Phase B) plus **three targeted implementation gaps** (dynamic top-10 eligibility, max-5 strategy cap, USDⓈ-M Futures connector). None of these justify discarding a working, vetted codebase. A rebuild would reintroduce look-ahead risk, lose the validation gatekeeper math, and reset test coverage to zero.

---

## Evidence Supporting In-Place Evolution

### 1. Codebase is complete through Phase 6

| Phase | Scope | Tests | Status |
|-------|-------|-------|--------|
| Phase 1 | Core data feed, clock, SQLite trade memory | 22/22 | VERIFIED |
| Phase 2 | Multi-paradigm Lego indicators + signals | 61/61 | VERIFIED |
| Phase 3 | Strategy builder V1, risk manager, paper simulator | 24/24 | VERIFIED |
| Phase 4 | Backtester, evaluation engine, validation gatekeeper | 14/14 | VERIFIED |
| Phase 5 | (Archived) AI research loop — excluded per rule-based-only | 11/11 | ARCHIVED |
| Phase 6 | FastAPI backend + UI, 9 routes + WS | 9/9 | VERIFIED |

### 2. All hard constraints already satisfied (or near-satisfied)

| Constraint | Status in current codebase | Gap to close |
|------------|---------------------------|--------------|
| Zero look-ahead (`t <= T`) | Enforced (`ZERO_LOOK_AHEAD = True`; `iloc[:t]` / `shift(1)`; tests assert none) | None |
| No AI self-approval | `validation/gatekeeper.py` independent; V1 stays active on V2 failure | None (AI loop archived) |
| Paper trade first | `execution/paper_simulator.py`; `POST /api/trades/manual` → `MANUAL_LIVE`; human executes broker orders | None |
| Rule-based only | Indicators/strategies deterministic; no ML/DL/RL/LLM | None (AI loop archived) |
| Binance Spot + USDⓈ-M Futures only | `market_type` = `CRYPTO_SPOT`/`CRYPTO_PERP`; NSE deprecated/removed | USDⓈ-M Futures WS connector missing |
| Max 5 strategies | Conceptual only; not enforced in code | **Implementation gap** |
| Top 10 by rolling 24h quote volume | `CRYPTO_TRADEABLE_PAIRS` hardcoded to 3 pairs | **Implementation gap** |

### 3. The 3 implementation gaps are small and additive

| Gap | Estimated effort | Dependencies | External repo needed? |
|-----|-----------------|--------------|----------------------|
| Dynamic top-10 eligibility by rolling 24h quote volume | Small | `binance_ws.py` REST ticker endpoint | No |
| Max-5 strategy cap enforcement | Small | `strategies/approved/` registry + `strategy_registry` table | No |
| USDⓈ-M Futures WS connector | Moderate | `binance_ws.py` pattern reused for Futures stream | Partial (Binance API docs only) |

None require the 13 blocked GitHub repo URLs.

---

## What a Rebuild Would Cost

A greenfield rebuild would discard:

- **~36 tracked source files** across `trading_engine/` (config, data, indicators ×4, signals ×4, strategies, risk, execution, memory, evaluation, validation, backend, frontend)
- **~131 verified pytest assertions** across 6 phase suites
- **The Validation Gatekeeper math** (OOS 70/30, WFA K=5, heatmap 5×5, cost stress) — the core "no AI self-approval" safeguard
- **The Lego-block indicator/signal/strategy architecture** (4 families, zero-look-ahead enforced)
- **SQLite WAL schema** (5 tables) and `trade_logger`/`paper_simulator` lifecycle
- **FastAPI + WebSocket hub + vendored Lightweight Charts v5.3.0 UI**

A rebuild would also **reintroduce look-ahead risk**: every indicator, signal, backtest exit, and MAE/MFE calculation would need to be re-audited for `t <= T` compliance. The existing test suites already encode this audit.

**Conclusion:** Rebuild cost ≫ benefit. In-place evolution preserves verified behavior while adding the 3 Binance-only gaps.

---

## Manifest Choice: `pyproject.toml` vs `requirements.txt` vs Both

### Recommendation: **`pyproject.toml` + `requirements.txt` (both)**

| Aspect | `pyproject.toml` | `requirements.txt` | Both (recommended) |
|--------|------------------|--------------------|---------------------|
| PEP 621 / modern Python packaging | ✅ Native | ❌ Not a packaging standard | ✅ `pyproject.toml` for build |
| Install command | `pip install .` / `pip install -e .` | `pip install -r requirements.txt` | Both supported |
| Offline / air-gapped friendliness | Needs build backend | Simple flat list, easy to vendor | Best of both |
| Existing repo convention | None yet (no manifest exists) | `trading_engine/requirements.txt` exists (Phase 1 list) | Keeps Phase 1 list, adds root `pyproject.toml` |
| Dependency lock granularity | Project-level metadata | Exact pins per environment | `pyproject.toml` declares; `requirements.txt` pins |

### Proposed manifest layout

**Root `pyproject.toml`** (new, project-level):
```toml
[project]
name = "finceptengine"
version = "0.1.0"
description = "Binance Spot + USDⓈ-M Futures rule-based trading research, backtesting, paper-trading, and live-signal platform"
requires-python = ">=3.10"
dependencies = [
    "fastapi",
    "uvicorn",
    "pandas",
    "numpy",
    "pandas-ta",
    "scipy",
    "websockets",
    "pytest",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["trading_engine*"]

[project.scripts]
fincept = "trading_engine.backend.server:main"
```

**Keep `trading_engine/requirements.txt`** (existing Phase 1 list) unchanged — it is referenced by AGENTS.md Section 1 and the Phase 1 changelog entry. Do not delete it (archive-before-remove spirit; it documents the original Phase 1 pin set).

**Do NOT create `package.json` or `Makefile`** — AGENTS.md Section 1 explicitly states none exist yet and none should be created until manifests are decided. The frontend is static HTML/JS (vendored Lightweight Charts), no npm tooling needed.

### Why not `requirements.txt`-only?

- `trading_engine/requirements.txt` lives inside the package, not at root; tooling (`pip install -r`) from repo root is less discoverable.
- No build backend declaration means `pip install .` won't work from root.
- `pyproject.toml` is the current Python packaging standard; adding it now avoids a later migration.

### Why not `pyproject.toml`-only?

- `trading_engine/requirements.txt` is already referenced by docs/changelog; removing it creates churn for no gain.
- Flat pin lists are easier to vendor in offline/air-gapped CI (this dev container has PyPI unreachable).

---

## Migration / Implementation Plan (In-Place)

If the client approves in-place evolution, the remaining Binance-only work is:

| Task | File(s) | Depends on external 13 URLs? |
|------|---------|------------------------------|
| Dynamic top-10-by-24h-quote-volume eligibility | `trading_engine/data/feeds/binance_ws.py` (+ REST ticker) | No |
| Max-5 strategy cap enforcement | `trading_engine/strategies/approved/`, `trading_engine/memory/db.py` (`strategy_registry`) | No |
| USDⓈ-M Futures WS connector | `trading_engine/data/feeds/binance_ws.py` (new Futures stream class) | Partial (Binance API docs) |
| Root `pyproject.toml` manifest | `/pyproject.toml` (new) | No |
| Update `AGENTS.md` Section 1 with install/test commands | `/AGENTS.md` | No |
| Phase C peer review & sign-off | `PEER_REVIEW_LOG.md` | No |

None of these require the 13 GitHub repo URLs. They can proceed immediately on the audit branch.

---

## Decision Gate

| Option | Verdict |
|--------|---------|
| Greenfield rebuild | **REJECTED** — cost ≫ benefit; would discard verified code + tests |
| In-place evolution (recommended) | **APPROVED** — add 3 small gaps + manifests to existing codebase |
| Hybrid (rebuild only UI layer) | **REJECTED** — frontend already complete (9/9 tests, vendored charts) |

---

## Cross-References

- `docs/ARCHITECTURE_DECISIONS.md` — ADR-001 (Binance-only scope), ADR-007 (max-5 strategies deferred), ADR-008 (research trigger stubbed)
- `docs/master_architecture.md` — Binance-only architecture
- `docs/database_and_data_contracts.md` — Binance-only schema + endpoints
- `docs/REPOSITORY_RESEARCH.md` — 14 research areas; 13 GitHub repo URLs blocker (still open)
- `KNOWN_ISSUES.md` — KI-005 (top-10 eligibility / max-5 cap), KI-010 (13 repo URLs blocker)
- `DEVELOPMENT_PLAN_AND_TODO.md` — Phase C tasks C.1–C.4
- `AGENTS.md` Section 1 — stack + manifest guidance (do not run pip/pytest/make until manifests created)
