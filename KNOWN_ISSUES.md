# KNOWN_ISSUES.md — Phase A Audit Findings

**Project:** FinceptEngine  
**Branch:** `audit/planning-finceptengine-transformation`  
**Date:** 2026-11-24  
**Status:** Open (KI-005 remains open as a specified-not-implemented feature; all others resolved)  
**Last Updated:** 2026-11-24 (Phase C task execution)

---

## Format

Each issue: ID | Severity | Description | Location | Recommended Action | Scope for Binance-Only Transformation

---

## Issues

### KI-001 — NSE/IST references out of scope for Binance-only project
**Severity:** High  
**Status:** RESOLVED (Phase B)  
**Resolution:** Phase B converted all NSE/IST references to Binance-only scope. `config.py` NSE constants marked DEPRECATED (retained for Phase 1 tests). `data/clock.py` NSE methods marked DEPRECATED. `docs/database_and_data_contracts.md` `market_type` → `'CRYPTO_SPOT', 'CRYPTO_PERP'` (`NSE_EQUITY` removed). `server.py` line 301 `NSE_EQUITY` fallback → `CRYPTO_SPOT`. `docs/master_architecture.md` scoped to Binance Spot + USDⓈ-M Futures only. Source preserved (not deleted); removal reasons recorded in `archive/documentation/DOCUMENTATION_CLEANUP_REPORT.md`.  
**Description:** Codebase contains NSE Equities session config (09:15–15:30 IST, Mon–Fri) alongside Binance crypto config. The intended project is Binance Spot + USDⓈ-M Futures only; NSE references are out of scope.  
**Location:** `config.py` (lines 26–33), `data/clock.py` (NSE session methods), `docs/database_and_data_contracts.md` (`market_type` allows `NSE_EQUITY`), `readme.md`, `master_architecture.md`  
**Recommended Action:** Phase B — classify NSE docs as UPDATE (remove NSE sections) or ARCHIVE. Convert `clock.py` to crypto-only or mark NSE methods as deprecated/unused. Do NOT delete source files — archive before removal.  
**Scope:** Required for Binance-only transformation.

### KI-002 — `agents/research_loop.py` conflicts with rule-based-only restriction
**Severity:** High  
**Status:** RESOLVED (Phase B)  
**Resolution:** `agents/research_loop.py` removed from active code; archived to `archive/research_loop_archive/research_loop.py` (not deleted). `tests/test_phase5_research_agents.py` archived to `archive/research_artifacts/test_phase5_research_agents.py`. `POST /api/research/trigger` replaced with removed-stub (`ok: false`). `docs/master_architecture.md` Layer 5 → "Human Review & Validation Gate". Validation Gatekeeper remains (deterministic, never lets AI self-approve).  
**Description:** Project restrictions forbid ML/DL/RL/LLM trading decisions, multi-agent systems, sentiment/news prediction. `agents/research_loop.py` is a 4-role AI self-improvement loop (Research→Hypothesis→Coding→Review) that generates V2 candidates. Although offline/template-based (no LLM SDK), it is conceptually an agent-based system.  
**Location:** `trading_engine/agents/research_loop.py`, `tests/test_phase5_research_agents.py`, `readme.md` (Section 4), `master_architecture.md` (Layer 5)  
**Recommended Action:** Flag for client decision — either remove the agent loop and keep rule-based V1 strategies only, or retain it as a non-trading research aid (no execution authority).  
**Scope:** Required decision before Binance-only transformation.

### KI-003 — ~300+ candidate strategy files in `strategies/candidates/`
**Severity:** Medium  
**Status:** RESOLVED (Phase B)  
**Resolution:** ~566 `v2_candidate_hyp_*.py` candidate files + `strategies/candidates/__init__.py` archived to `archive/research_artifacts/` (not deleted). None are imported by active code or tests. Removal reason recorded in `archive/documentation/DOCUMENTATION_CLEANUP_REPORT.md`.  
**Description:** Working tree contains ~300+ untracked `v2_candidate_hyp_*.py` research artifacts plus `v2_candidate_hyp_test01/02/03.py`. None are committed. These are Phase 5 research-loop outputs awaiting archive/remove decision.  
**Location:** `trading_engine/strategies/candidates/`  
**Recommended Action:** Audit a sample, then archive (not delete) before any removal. Record removal reason in `DOCUMENTATION_CLEANUP_REPORT.md`.  
**Scope:** Cleanup target for Phase B.

### KI-004 — Untracked non-source artifacts in working tree
**Severity:** Low  \n**Status:** RESOLVED (Phase B)  \n**Resolution:** 8 `.whl` files → `archive/untracked_artifacts/`, `graphify-out/` → `archive/untracked_artifacts/graphify-out`, `UII/` (4 PNG screenshots) → `archive/untracked_artifacts/UII`. Not deleted; removal reasons recorded in `archive/documentation/DOCUMENTATION_CLEANUP_REPORT.md`.  \n**Description:** Root contains 8 `.whl` pip wheel files, `UII/` (4 screenshot PNGs), `graphify-out/` directory. `.venv/`, `.pytest_cache/`, `__pycache__/` are gitignored.  \n**Location:** Root (`*.whl`, `UII/`, `graphify-out/`)  \n**Recommended Action:** Remove `.whl` caches and `graphify-out/` (non-source, regenerable). Decide on `UII/` screenshots. Do not touch `.venv`.  \n**Scope:** General repo hygiene.

### KI-005 — `CRYPTO_TRADEABLE_PAIRS` hardcoded to 3 pairs; no dynamic top-10 eligibility; no max-5 cap; no perp WS connector; no spot/futures isolation
**Severity:** Medium  
**Status:** OPEN (SPECIFIED, NOT IMPLEMENTED)  
**Description:** `config.py` defines `CRYPTO_TRADEABLE_PAIRS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")` (3 pairs). Intended project requires top 10 eligible cryptocurrencies by rolling 24-hour quote volume, max 5 strategies. No dynamic eligibility logic, no strategy cap, no USDⓈ-M futures WS connector, no spot/futures isolation enforced in code.  
**Location:** `config.py` line 24; `data/feeds/binance_ws.py` (spot only); `memory/db.py`, `server.py` (isolation partial)  
**Recommended Action:** Implement per ADR-009 (top-10 scanner), ADR-010 (max-5 cap), ADR-011 (USDM futures WS connector), ADR-012 (spot/futures isolation). All four are specified in `docs/ARCHITECTURE_DECISIONS.md`; implementation awaits explicit client approval (new trading-relevant features).  
**Scope:** Feature work for Binance-only transformation.

### KI-006 — No `requirements.txt` / `pyproject.toml` at repo root
**Severity:** Medium  
**Status:** RESOLVED (Phase C Task 3)  
**Resolution:** Root `pyproject.toml` (PEP 621) + root `requirements.txt` created (8 deps: fastapi, uvicorn, pandas, numpy, pandas-ta, scipy, websockets, pytest). `trading_engine/requirements.txt` left unchanged. Fresh-env `pip install -r requirements.txt` verified; `pytest` runs from repo root — all phase suites pass.

### KI-007 — 13 GitHub repository URLs not found anywhere
**Severity:** High (blocker)  
**Status:** RESOLVED (Phase C Task 1)  
**Resolution:** Client supplied the 13 GitHub repo URLs; all 13 repos cloned shallowly to `/tmp/opencode/` and source-inspected (binance-strategy, hftbacktest, Lean, OrderFlow-Analysis-Pro, TapeFlow, tape-and-book, HFTENGINE, CryptoQuant-Engine, Simpler-Trader, kline-orderbook-chart [REJECTED — commercial], crypto-trading-strategies, VFund, QuantConnect/Lean, OpenBB). Findings documented in `docs/REPOSITORY_RESEARCH.md`. Reuse candidates identified; nothing integrated yet (per Recommendation B).  
**Location:** None (external input — now supplied)

### KI-008 — Phase 6 not merged to `dev`
**Severity:** Info  
**Description:** `backend/server.py` + frontend are committed to `phase6/fastapi-backend-ui` and pushed to origin, but not merged to `dev` — awaiting explicit client approval (AGENTS.md Rule 6).  
**Location:** Git branches  
**Recommended Action:** Do not merge without explicit client approval. Commit only into phase branch.  
**Scope:** Governance.

### KI-009 — `readme.md` (lowercase) exists but no `README.md`
**Severity:** Low  
**Description:** Root has `readme.md` but no conventional `README.md`.  
**Location:** Root  
**Recommended Action:** Keep as-is (no duplicate created per prior decision) or rename to `README.md` with client approval.  
**Scope:** Minor hygiene.

### KI-010 — `claude-mem` unavailable (credentials refused)
**Severity:** Info  
**Description:** Durable memory saves not possible this session (credentials expired since ~2026-11-08). No cross-session memory.  
**Location:** N/A (environment)  
**Recommended Action:** Track all work in conversation context and project docs (`CHANGELOG.md`, `DEVELOPMENT_PLAN_AND_TODO.md`, `PEER_REVIEW_LOG.md`).  
**Scope:** Operational.

---
