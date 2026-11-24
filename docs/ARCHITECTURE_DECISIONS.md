# Architecture Decision Records — Binance-Only Transformation

**Project:** FinceptEngine — Binance Spot + USDⓈ-M Futures Trading Platform  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`, NOT committed, NOT pushed, NOT merged)  
**Date:** 2026-11-24  
**Owner:** Architect  
**Scope:** Binance Spot + USDⓈ-M Futures only (rule-based, human-reviewed, paper-first)

---

## Purpose

This document records every Architecture Decision Record (ADR) made during the Binance Spot + USDⓈ-M Futures transformation (Phase B documentation cleanup + Phase C planning). Each ADR states:

- **Decision** — what was decided
- **Context / Rationale** — why it was decided
- **Consequences** — what changes in code, docs, and behavior
- **Status** — Proposed / Accepted / Superseded

Per AGENTS.md Rule 2 (two-way sync), every ADR is cross-referenced from `docs/master_architecture.md`, `docs/database_and_data_contracts.md`, `CHANGELOG.md`, and `DEVELOPMENT_PLAN_AND_TODO.md`.

---

## ADR-001 — Binance Spot + USDⓈ-M Futures only (remove NSE/Equities scope)

**Status:** Accepted  
**Date:** 2026-11-24  
**Decision:** The platform supports **only** Binance Spot and USDⓈ-M Futures. All NSE Equities / IST session references are out of scope.

### Context
The codebase previously targeted both Crypto (Binance Spot + USDⓈ-M Perpetuals) **and** NSE Equities (IST sessions, 09:15–15:30, Mon–Fri). The intended transformation narrows scope to Binance Spot + USDⓈ-M Futures only, per the project brief.

### Consequences
- `docs/master_architecture.md`: Title/subtitle → Binance Spot + USDⓈ-M Futures; removed NSE expansion references (Dhan/Fyers/Angel One Phase 2); removed `nse_broker_ws.py` from folder structure; roadmap Phase 5 → Human Review & Validation Gate (no AI self-improvement).
- `docs/database_and_data_contracts.md`: `market_type` column → `'CRYPTO_SPOT', 'CRYPTO_PERP'` (`NSE_EQUITY` removed).
- `trading_engine/config.py`: NSE session constants (`NSE_SESSION_IST_START`, `NSE_SESSION_IST_END`, `NSE_SESSION_IST_WINDOW`, `NSE_TRADING_DAYS`) marked **DEPRECATED** but retained so `clock.py` and Phase 1 tests keep importing.
- `trading_engine/data/clock.py`: NSE methods (`is_nse_session_open`, `nse_next_session_open_utc`, `nse_square_off_utc`) marked DEPRECATED; retained only so Phase 1 tests keep passing.
- `trading_engine/backend/server.py`: `market_snapshot` fallback `NSE_EQUITY` → `CRYPTO_SPOT`; unused `CRYPTO_TRADEABLE_PAIRS` import removed.
- `trading_engine/memory/db.py`: `market_type` comment updated to `'CRYPTO_SPOT', 'CRYPTO_PERP' (Binance only)`.
- `readme.md`: Still mentions "Indian Intraday Equities (NSE F&O)" — retained as-is pending client decision (not part of code-change scope).
- Nothing deleted — archive-before-remove rule applies.

---

## ADR-002 — Rule-based only (no ML/DL/RL/LLM trading decisions, no multi-agent systems)

**Status:** Accepted  
**Date:** 2026-11-24  
**Decision:** All trading decisions must be rule-based. No ML/DL/RL/LLM trading decisions, no multi-agent systems, no sentiment/news prediction, no autonomous strategy generation.

### Context
The prior design included a `Layer 5: AI Research Agents` (`agents/research_loop.py`) — a 4-role loop (Research → Hypothesis → Coding V2 → Review) that generated `V2` candidate strategies autonomously. This conflicts with the rule-based-only restriction (AGENTS.md Hard Constraint #2).

### Consequences
- `agents/research_loop.py` removed from active code; archived to `archive/research_loop_archive/research_loop.py` (not deleted).
- `tests/test_phase5_research_agents.py` removed from active test suite; archived to `archive/research_artifacts/test_phase5_research_agents.py`.
- `strategies/candidates/` (~566 `v2_candidate_hyp_*.py` AI-generated candidates) archived to `archive/research_artifacts/`; none are imported by active code or tests.
- `POST /api/research/trigger` replaced with a removed-stub returning `ok: false` + exclusion reason.
- `docs/master_architecture.md`: Layer 5 AI Research Agents removed; replaced with **Layer 5: Human Review & Validation Gate**; `agents/` entry replaced with "REMOVED: AI self-improvement agents layer".
- `docs/database_and_data_contracts.md`: `POST /api/research/trigger` removed from endpoint table; weakness report now passed to Human Strategy Reviewer (not AI Research Agent).
- The Validation Gatekeeper (`validation/gatekeeper.py`) remains — it is deterministic (OOS, WFA, heatmap, cost stress) and never lets AI self-approve.

---

## ADR-003 — Human Review & Validation Gate replaces AI self-improvement layer

**Status:** Accepted  
**Date:** 2026-11-24  
**Decision:** `V1` strategies are human-defined, human-reviewed, human-tested, and human-approved. `V2` candidates require human review plus all 4 Validation Gate tests (OOS, Walk-Forward, Parameter Sensitivity Heatmap, Cost Stress). AI never self-approves.

### Context
To satisfy AGENTS.md Hard Constraint #2 ("Never let AI approve its own strategy"), the autonomous research loop is replaced by a human gate. The independent Validation Gatekeeper runs 4 deterministic tests before any candidate can be promoted.

### Consequences
- `docs/master_architecture.md` Section 3 / layer table: Layer 5 = "Human Strategy Review & Validation Gate"; Layer 6 = FastAPI Backend.
- `docs/database_and_data_contracts.md` Contract B: weakness report passed to Human Strategy Reviewer.
- `docs/strategy_and_validation_spec.md` Section 3: gatekeeper math unchanged (OOS PF ≥ 1.25, WFA ≥ 4/5 windows, heatmap ≥ 20/25 cells PF > 1.10, cost stress PF ≥ 1.15 & ER ≥ +0.12R).
- `frontend/js/system_monitor_ui.js` "Agent status" panel updated to "Paper PnL" (agent status removed).
- `V1` stays active on any `V2` failure; `V1` is never overwritten.

---

## ADR-004 — Market type restricted to `CRYPTO_SPOT` / `CRYPTO_PERP`

**Status:** Accepted  
**Date:** 2026-11-24  
**Decision:** The `ohlcv_bars.market_type` column accepts only `'CRYPTO_SPOT'` and `'CRYPTO_PERP'`. `NSE_EQUITY` is removed.

### Context
The SQLite schema previously allowed `market_type` values `'CRYPTO_SPOT'`, `'CRYPTO_PERP'`, `'NSE_EQUITY'`. With NSE out of scope, `NSE_EQUITY` must be removed to prevent accidental mixed-market data.

### Consequences
- `docs/database_and_data_contracts.md` Table 1: comment updated to `-- 'CRYPTO_SPOT', 'CRYPTO_PERP'`.
- `trading_engine/memory/db.py`: `market_type` comment updated to `'CRYPTO_SPOT', 'CRYPTO_PERP' (Binance only)`.
- `trading_engine/backend/server.py`: `_ohlcv_query` default `market_type="CRYPTO_SPOT"`; snapshot fallback now always `CRYPTO_SPOT`.
- No data migration needed — existing `trading_engine.db` has no `NSE_EQUITY` rows (Phase 1 verified crypto-only ingestion).

---

## ADR-005 — Deprecated NSE constants retained (not deleted)

**Status:** Accepted  
**Date:** 2026-11-24  
**Decision:** NSE session constants in `config.py` and NSE methods in `clock.py` are marked **DEPRECATED** but **retained** so Phase 1 tests keep passing. They are not part of the active Binance scope and must not be used by new code.

### Context
AGENTS.md Hard Constraint / project constraint: "Do not delete source code." NSE constants are referenced by `clock.py` imports and Phase 1 tests (`test_nse_session_open_*`). Deleting them would break the test suite. Instead, they are deprecated in place.

### Consequences
- `trading_engine/config.py`: NSE constants kept with `# ⚠️ DEPRECATED — ... (deprecated)` comments; `IST = ZoneInfo("Asia/Kolkata")` retained (used by `clock.py`).
- `trading_engine/data/clock.py`: Docstring updated with DEPRECATION NOTICE; NSE methods retained and import `IST`, `NSE_SESSION_IST_END`, `NSE_SESSION_IST_START`, `NSE_TRADING_DAYS`.
- New code must not import or call NSE methods.
- Phase 1 tests (`test_phase1_data_db.py` 22/22) continue to pass unchanged.

---

## ADR-006 — Archived artifacts not deleted (archive-before-remove)

**Status:** Accepted  
**Date:** 2026-11-24  
**Decision:** All removed source/code artifacts are archived (not deleted), with removal reasons recorded.

### Context
Project constraint: "Do not implement new trading features... Do not delete source code." Archive-before-remove rule applies to every removal.

### Consequences
| Item | Destination | Reason |
|------|-------------|--------|
| `trading_engine/agents/research_loop.py` | `archive/research_loop_archive/research_loop.py` | Conflicts with rule-based-only restriction (autonomous agent loop) |
| `trading_engine/tests/test_phase5_research_agents.py` | `archive/research_artifacts/test_phase5_research_agents.py` | Imports removed `research_loop`; not in active V1 workflow |
| `trading_engine/strategies/candidates/*.py` (~566) | `archive/research_artifacts/` | AI-generated V2 candidates; none imported by active code/tests |
| `trading_engine/strategies/candidates/__init__.py` | `archive/research_artifacts/` | Package init for archived candidates |
| 8 `.whl` files (root) | `archive/untracked_artifacts/` | Untracked pip wheel caches; non-source |
| `graphify-out/` | `archive/untracked_artifacts/graphify-out` | Untracked knowledge-graph output (~12 MB); regenerable |
| `UII/` (4 PNG screenshots) | `archive/untracked_artifacts/UII` | Untracked UI screenshots; non-source |
| `docs/prd_and_roadmap.md` | `archive/documentation/prd_and_roadmap.md` | Conflicting with Binance-only scope (NSE/FR-01, 6-phase roadmap, AI loop) |

---

## ADR-007 — Max 5 strategies; hardcoded 3-pair list not yet dynamic

**Status:** Accepted (deferred to implementation)  
**Date:** 2026-11-24  
**Decision:** Max 5 strategies enforced conceptually; `CRYPTO_TRADEABLE_PAIRS` remains hardcoded to 3 pairs (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`) pending implementation of dynamic top-10-by-rolling-24h-quote-volume eligibility.

### Context
The intended project scans the top 10 eligible crypto by rolling 24h quote volume and supports max 5 strategies. Currently `CRYPTO_TRADEABLE_PAIRS` is hardcoded to 3 pairs and no strategy cap is enforced in code.

### Consequences
- `KNOWN_ISSUES.md` KI-005 records this as a Medium-severity feature item for the Binance-only transformation.
- `DEVELOPMENT_PLAN_AND_TODO.md` Phase C / backlog should track implementing dynamic eligibility + strategy cap.
- Not blocked by documentation cleanup; flagged for implementation phase.

---

## ADR-008 — `/api/research/trigger` replaced with removed-stub

**Status:** Accepted  
**Date:** 2026-11-24  
**Decision:** `POST /api/research/trigger` no longer triggers the 4-Agent AI Research Loop. It returns `ok: false` with an exclusion reason and archival location.

### Context
With `agents/research_loop.py` archived (ADR-002), the lazy import `from trading_engine.agents.research_loop import ResearchLoop` inside the endpoint would raise `ModuleNotFoundError`. The endpoint is intentionally disabled.

### Consequences
- `trading_engine/backend/server.py`: endpoint replaced with removed-stub docstring + `{"ok": false, "removed": true, "reason": "...", ...}`.
- `docs/database_and_data_contracts.md`: endpoint row removed; ⚠️ note added under endpoint table.
- `docs/master_architecture.md`: module docstring updated (`POST /api/research/trigger` → REMOVED).

---

## ADR-009 — Dynamic top-10 eligibility scanner (rolling 24h quote volume)

**Status:** Proposed (specification only — not implemented)  
**Date:** 2026-11-24  
**Decision:** Replace the hardcoded 3-pair `CRYPTO_TRADEABLE_PAIRS` list with a dynamic eligibility scanner that ranks all Binance USDⓈ-M perpetuals / spot pairs by rolling 24h quote volume and keeps the top 10 eligible symbols as the tradeable universe.

### Context
`config.py` currently hardcodes `CRYPTO_TRADEABLE_PAIRS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")` (3 pairs, see KI-005). The master architecture intent is "top 10 eligible crypto by rolling 24-hour quote volume". No scanner exists yet; this ADR specifies (not implements) it per the Recommendation B constraint "no unrelated new features / no implementation of the four missing platform capabilities yet" — this is the architecture spec for a future implementation phase.

### Interfaces (specified, not implemented)

**`trading_engine/data/scanner.py` — `Top10EligibilityScanner`**

```python
class Top10EligibilityScanner:
    def __init__(self, rest_client, quote_asset: str = "USDT", top_n: int = 10):
        ...

    async def refresh_eligible_symbols(self) -> list[str]:
        """Fetch rolling 24h quote volume for all USDT-quoted spot + perp symbols,
        filter to eligible (active, not delisted, min volume), sort desc, return
        top_n symbol strings."""
        ...

    def eligible_symbols(self) -> tuple[str, ...]:
        """Last refreshed eligible universe (cached)."""
        ...
```

**`config.py` additions (specified, not implemented)**

```python
# Dynamic eligibility (replaces hardcoded 3-pair list once implemented)
ELIGIBILITY_QUOTE_ASSET = "USDT"
ELIGIBILITY_TOP_N = 10
ELIGIBILITY_MIN_24H_QUOTE_VOLUME_USDT = 0.0  # tunable floor
CRYPTO_TRADEABLE_PAIRS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")  # retained until scanner implemented
```

### Acceptance Criteria
1. Scanner uses only Binance public REST `/api/v3/ticker/24hr` (spot) and `/fapi/v1/ticker/24hr` (perp) — no private endpoints, no signed requests.
2. Eligibility filter excludes delisted/leveraged/undefined symbols; universe capped at `top_n` (10).
3. Deterministic ordering by descending 24h quote volume; ties broken by symbol name.
4. Cache invalidation: refresh interval configurable (default 1 hour); stale cache never used for execution decisions without refresh.
5. Scan results are read-only advisory — no auto-trading on newly eligible symbols (per rule-based-only, paper-first).

### Testing
- Unit test: `test_scanner_ranks_by_quote_volume` — mock 24hr ticker responses, assert top-N selection and descending order.
- Unit test: `test_scanner_excludes_ineligible` — delisted / non-USDT / zero-volume symbols excluded.
- No integration test against live Binance (network) in CI.

### Consequences
- `KNOWN_ISSUES.md` KI-005 remains open until scanner + cap implemented.
- `DEVELOPMENT_PLAN_AND_TODO.md` Phase C backlog updated with scanner + cap tasks.
- No code in `config.py`, `server.py`, or strategies is changed by this ADR.

---

## ADR-010 — Max-5 strategy cap enforcement

**Status:** Proposed (specification only — not implemented)  
**Date:** 2026-11-24  
**Decision:** Enforce a hard runtime cap of 5 concurrently active strategies, with explicit human approval required to add/replace any strategy in the active set.

### Context
Master architecture: "supports a maximum of 5 independent, deterministic, rule-based strategies." No cap is currently enforced in code; `strategies/approved/` is directory-based without a count guard. This ADR specifies (not implements) the cap per Recommendation B constraints.

### Interfaces (specified, not implemented)

**`trading_engine/strategies/strategy_registry.py` — `StrategyRegistry`**

```python
class StrategyRegistry:
    MAX_ACTIVE_STRATEGIES = 5

    def __init__(self, approval_gate):  # human review gate callback
        ...

    def register(self, strategy_id: str, strategy, approved_by: str) -> bool:
        """Add strategy to active set. Returns False if cap reached or not
        human-approved."""
        ...

    def active_strategies(self) -> dict[str, object]:
        ...

    def can_add(self) -> bool:
        """True iff len(active) < MAX_ACTIVE_STRATEGIES."""
        ...
```

### Acceptance Criteria
1. Cap enforced at registration time, not just UI — programmatic bypass impossible without modifying source.
2. Adding a 6th strategy returns `False` with reason `"cap_reached"`; no silent drop.
3. Replacement (deactivate old, activate new) allowed within cap; requires human `approved_by` attribution.
4. `V1` baseline strategies never auto-deployed; cap applies equally to `V1` and `V2`.
5. Cap value (`MAX_ACTIVE_STRATEGIES = 5`) is a single source-of-truth constant, not duplicated.

### Testing
- Unit test: `test_strategy_cap_max_5` — registering >5 rejects the 6th.
- Unit test: `test_strategy_cap_replacement_within_cap` — swap within cap succeeds.
- No auto-enrollment test (prohibited: no autonomous strategy generation).

### Consequences
- `KNOWN_ISSUES.md` KI-005 remains open until cap + scanner implemented.
- No changes to `strategies/approved/` V1 strategies by this ADR.

---

## ADR-011 — USDⓈ-M Futures WebSocket connector (spot/futures isolation)

**Status:** Proposed (specification only — not implemented)  
**Date:** 2026-11-24  
**Decision:** Add a dedicated USDⓈ-M Futures WebSocket connector distinct from the existing Spot WS (`wss://stream.binance.com:9443/ws`), using `wss://fstream.binance.com/ws` (USDM futures base stream), with spot and futures data strictly isolated per market type (`CRYPTO_SPOT` / `CRYPTO_PERP`).

### Context
`data/feeds/binance_ws.py` is spot-only (`wss://stream.binance.com:9443/ws`, REST `https://api.binance.com/api/v3`). No USDM futures WS exists (KI-005 / missing capability #3). This ADR specifies (not implements) the connector per Recommendation B.

### Interfaces (specified, not implemented)

**`trading_engine/data/feeds/binance_usdm_ws.py` — `BinanceUsdmWsFeed`**

```python
class BinanceUsdmWsFeed:
    def __init__(self, symbols: list[str], on_bar, on_tick, on_depth,
                 base_url: str = "wss://fstream.binance.com/ws"):
        ...

    async def connect(self) -> None: ...
    async def subscribe_kline(self, symbol: str, interval: str) -> None: ...
    async def subscribe_aggtrade(self, symbol: str) -> None: ...
    async def subscribe_depth(self, symbol: str, level: str = "0ms") -> None: ...
    async def subscribe_mark_price(self, symbol: str) -> None: ...
    async def subscribe_funding_rate(self, symbol: str) -> None: ...
    async def subscribe_open_interest(self, symbol: str) -> None: ...
    async def run_forever(self) -> None: ...
```

### Isolation rules (specified)
1. Spot feeds write `market_type='CRYPTO_SPOT'`; USDM feeds write `market_type='CRYPTO_PERP'`. Never mixed in the same stream or table row.
2. Symbol namespace isolation: spot symbol `BTCUSDT` ≠ perp symbol `BTCUSDT` in cache/feature store keyed by `(symbol, market_type, timeframe)`.
3. No cross-market signal leakage: a strategy subscribed to spot never reads perp book depth or funding; and vice versa, unless explicitly configured as a cross-market pair strategy (human-reviewed).
4. Reconciliation: on restart, spot and perp backfill independently via their respective REST endpoints (`/api/v3/klines` vs `/fapi/v1/klines`).

### Acceptance Criteria
1. Connector persists only finalized klines (`x == True`) — same zero-look-ahead rule as spot (candle completion).
2. Funding rate / open interest / mark price streams stored in separate tables keyed by `market_type='CRYPTO_PERP'`.
3. Reconnection with backoff; subscription resume on reconnect.
4. Unit-tested with mocked websockets (no live network in CI).

### Consequences
- `data/feeds/binance_ws.py` spot connector unchanged (no refactoring).
- `KNOWN_ISSUES.md` KI-005 remains open until connector implemented.
- No cross-market aggregation added by this ADR.

---

## ADR-012 — Spot / USDⓈ-M Futures isolation

**Status:** Proposed (specification only — not implemented)  
**Date:** 2026-11-24  
**Decision:** Spot and USDⓈ-M Futures are isolated execution domains throughout the stack: config, data feed, feature store, strategy, risk, and paper simulator each carry an explicit `market_type` and never implicitly share state.

### Context
With both spot and perp in scope, implicit sharing (e.g., a spot price used for a perp stop, or a shared symbol cache) would corrupt PnL and risk math. This ADR specifies (not implements) isolation boundaries.

### Isolation boundaries (specified)

| Layer | Isolation rule |
|-------|---------------|
| `config.py` | Separate fee schedules already exist (`BINANCE_SPOT_*_BP` vs `BINANCE_PERP_*_BP`). New market-scoped constants keyed by `market_type`. |
| `data/feeds/` | `binance_ws.py` (spot) and `binance_usdm_ws.py` (perp) are separate classes; no shared subscription state. |
| `memory/db.py` | `ohlcv_bars.market_type ∈ {CRYPTO_SPOT, CRYPTO_PERP}`; all queries filter by `market_type`; no implicit defaulting across markets. |
| `data/feature_store.py` | Feature cache keyed by `(symbol, market_type, timeframe)`; no cross-market feature reuse. |
| `strategies/` | A strategy declares its `market_type` at registration; it only subscribes to feeds of that type. |
| `risk/` | Position sizing / circuit breakers computed per `market_type`; no cross-market netting. |
| `execution/paper_simulator.py` | Fills tagged with `market_type`; spot and perp paper positions tracked separately. |

### Acceptance Criteria
1. Any function taking a symbol must also take (or resolve) a `market_type`; no symbol-only lookups that return mixed-market data.
2. Querying `ohlcv_bars` for `BTCUSDT` without `market_type` returns an error or empty set (never silently merges spot+perp).
3. Unit test `test_market_type_isolation` asserts spot write is invisible to perp query and vice versa.
4. No automatic conversion/arbitrage between spot and perp (rule-based only; any cross-market strategy is human-defined).

### Consequences
- Existing spot-only behavior unchanged (backward compatible).
- `KNOWN_ISSUES.md` KI-005 remains open until isolation implemented in code.

---

## Cross-References

| Document | Section | ADRs Referenced |
|----------|---------|-----------------|
| `docs/master_architecture.md` | §1–§4 | ADR-001, ADR-002, ADR-003, ADR-009, ADR-010, ADR-011, ADR-012 |
| `docs/database_and_data_contracts.md` | §1 Table 1; §3 | ADR-001, ADR-004, ADR-008, ADR-011, ADR-012 |
| `docs/strategy_and_validation_spec.md` | §3 | ADR-002, ADR-003, ADR-010 |
| `CHANGELOG.md` | [v0.1.10] | ADR-001…ADR-012 |
| `DEVELOPMENT_PLAN_AND_TODO.md` | IN PROGRESS / Phase C | ADR-001…ADR-012 |
| `archive/documentation/DOCUMENTATION_CLEANUP_REPORT.md` | §1–§3 | ADR-001, ADR-002, ADR-006 |
| `KNOWN_ISSUES.md` | KI-005 | ADR-007, ADR-009, ADR-010, ADR-011, ADR-012 |

---

## Governance Note

Nothing is committed, pushed, merged, or permanently deleted (AGENTS.md Rule 6). All changes live on branch `audit/planning-finceptengine-transformation` awaiting explicit client approval before merge to `dev`.
