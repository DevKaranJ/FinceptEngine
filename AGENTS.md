# AGENTS.md — FinceptEngine

**Project:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Full spec:** `docs/master_architecture.md` — read it before building.  
**Version:** v0.1.0 (Project Initiation Baseline)  
**Status:** Active — Multi-agent governance enforced (see Section 3)

---

## 1. Stack (from `docs/master_architecture.md` `requirements.txt` plan)

- Python, FastAPI, uvicorn, pandas, numpy, pandas-ta, scipy, websockets, pytest
- SQLite WAL mode (`trading_engine.db`); `pyarrow`/Parquet for feature caching
- No `pyproject.toml`, `package.json`, `Makefile`, or `requirements.txt` exists yet. Do **not** run `pip install -r requirements.txt`, `pytest`, `make`, etc. until the manifests are created.

## 2. Entry Points & Ownership

- `config.py` — market sessions, fee/slippage schedules, risk constants
- `backend/server.py` — FastAPI REST + WebSocket hub to frontend
- `trading_engine/` owns all layers: `data/`, `indicators/`, `signals/`, `strategies/`, `risk/`, `execution/`, `memory/`, `evaluation/`, `agents/`, `validation/`, `tests/`, `frontend/`
- Tests live in `trading_engine/tests/`; runner is `pytest` from repo root

## 3. MANDATORY REAL-WORLD ENGINEERING GOVERNANCE (ENFORCED ON EVERY TASK)

All agents must strictly obey these 5 permanent rules before writing or modifying any code.

### Rule 1 — Read-Before-Act (Read Documentation & Codebase First)
At the start of every task or phase, read and cross-check:
`README.md` / `readme.md`, `MASTER_ARCHITECTURE.md` (root or `docs/`), `PRD_AND_ROADMAP.md`, `DATABASE_AND_DATA_CONTRACTS.md`, `STRATEGY_AND_VALIDATION_SPEC.md`, `AGENTS.md`, `DEVELOPMENT_PLAN_AND_TODO.md`, `CHANGELOG.md`.
Inspect the existing directory tree and files so you never duplicate logic, mismatch schemas, or break existing modules.

### Rule 2 — Two-Way Synchronization Between Code, To-Do List & Docs
- Whenever code changes, update the documentation and trackers immediately.
- Whenever documentation or requirements change, update the development plan and to-do list immediately.
- If a new helper function, database column, API route, or edge-case requirement is added during coding, document it immediately in `DATABASE_AND_DATA_CONTRACTS.md` or `MASTER_ARCHITECTURE.md` so documentation is never out of date.

### Rule 3 — Maintain `DEVELOPMENT_PLAN_AND_TODO.md`
Maintain it in the project root and update it at the start and end of every task across four explicit sections:
- `[x] COMPLETED & VERIFIED` — finished, tested with `pytest`, signed off by Reviewer
- `[/] IN PROGRESS (CURRENT SPRINT)` — exact tasks and owning agent role
- `[ ] REMAINING BACKLOG (BY PHASE)` — all pending tasks across Phases 1–6
- `[+] NEWLY ADDED / DISCOVERED ITEMS` — new sub-tasks, bug fixes, edge cases, refinements (with date and reason)

### Rule 4 — Record Every Change in `CHANGELOG.md`
Maintain a production `CHANGELOG.md` in the project root. Every time files are created, updated, refactored, or fixed, log a timestamped entry before ending the turn:
- Timestamp & Phase/Version ID
- Agent Role(s) Involved (Architect, Backend, Frontend, QA, Reviewer)
- Added / Modified / Removed Files
- Why the Change Was Made
- Test & Verification Status (pytest command run and pass/fail count)

### Rule 5 — Mandatory Internal Peer Review Before Client Sign-Off
No coder agent may declare its own work finished. Every completed task must pass through **04_qa_tester** (automated testing) and **05_reviewer** (code quality, look-ahead bias check, risk compliance, documentation sync check). Record the review outcome in `PEER_REVIEW_LOG.md` (Issues Found → Fixes Applied → Final Sign-Off) before presenting the result to the Client.

## 4. Testing & Verification

- Test framework: **pytest**. Run `pytest` from the repo root (once tests/ exists).
- Each phase has a hard stop gate (see `docs/master_architecture.md` Section 4): run `pytest` for that phase, verify pass, then STOP. Do not proceed to the next phase without client approval.
- No fixtures, integration services, or snapshot workflows exist yet.

## 5. Hard Constraints (Non-Negotiable, from the spec)

1. **Zero look-ahead protection** — indicators/transforms/backtests must use only past data (`t <= T`). Prevent future leakage across train/validation splits.
2. **Never let AI approve its own strategy** — candidate strategies (`V2`) must pass the independent Validation Gate (OOS split, Walk-Forward, Parameter Sensitivity Heatmap, Execution Realism Stress Test) before promotion. `V1` stays active on any failure.
3. **Paper trade first** — strategies go historical backtest → live paper → manual real order ticket (human executes broker orders manually).
4. **Surgical diffs** — modify only code tied to the current ticket; no unprompted refactoring or reformatting.

## 6. What to Add as the Codebase Gains Structure

Exact install/lint/typecheck/test/run commands, single-test invocation, required command order, env loading, dev server URL (`http://127.0.0.1:8765`), and flaky/expensive suites. Keep this file short; add only verified, repo-specific facts.
