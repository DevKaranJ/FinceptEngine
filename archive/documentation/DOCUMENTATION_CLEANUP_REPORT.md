# Documentation Cleanup Report — Phase B

**Project:** FinceptEngine  
**Branch:** `audit/planning-finceptengine-transformation`  
**Date:** 2026-11-24  
**Owner:** Architect  
**Scope:** Binance Spot + USDⓈ-M Futures only (rule-based, human-reviewed, paper-first)

---

## 1. Classification of `docs/` markdown files

| File | Classification | Reason | Disposition |
|------|---------------|--------|-------------|
| `docs/prd_and_roadmap.md` | Conflicting with new scope | References NSE/FR-01, Indian equities, 6-phase crypto+NSE roadmap, "Self-Improving Multi-Paradigm" vision that conflicts with rule-based-only restriction | **ARCHIVE** → `archive/documentation/prd_and_roadmap.md` |
| `docs/master_architecture.md` | Conflicting (partial) | References NSE expansion (Phase 2 Dhan/Fyers/Angel One), Layer 5 AI agents, `nse_broker_ws.py` folder entry | **UPDATE** — keep, strip NSE/agent sections |
| `docs/database_and_data_contracts.md` | Outdated (partial) | `market_type` column allows `NSE_EQUITY`; endpoint table references `/api/research/trigger` (agent loop) | **UPDATE** — keep, scope to Binance Spot + USDⓈ-M Futures |
| `docs/strategy_and_validation_spec.md` | Current and relevant | Validation gatekeeper math (OOS, WFA, heatmap, cost stress) is valid; rule-based Lego-block pattern applies to crypto | **KEEP** — minor Binance-only wording updates |
| `docs/contributing_indicators.md` | Current and relevant | Indicator family structure + zero-look-ahead rules are valid for crypto indicators | **KEEP** — minor Binance-only wording updates |

---

## 2. Archives created (empty, awaiting client approval to move)

- `archive/documentation/` — outdated docs moved here (not deleted)
- `archive/research_artifacts/` — candidate strategy files + research_loop artifacts
- `archive/untracked_artifacts/` — `.whl`, `UII/`, `graphify-out/`
- `archive/research_loop_archive/` — `agents/research_loop.py` preserved here

**Rule:** Nothing is permanently deleted. Every archived item records its removal reason.

---

## 3. Research loop exclusion documentation

`agents/research_loop.py` (4-role AI self-improvement loop) is excluded from the active V1 workflow because:

- It implements autonomous strategy generation (Research→Hypothesis→Coding→Review), which conflicts with the rule-based-only restriction (no ML/DL/RL/LLM trading decisions, no multi-agent systems).
- V1 strategies must be explicitly human-defined, reviewed, tested, and approved.
- It must NOT be replaced by another autonomous agent system.

**Active runtime references removed:**
- `trading_engine/backend/server.py` — lazy import `from trading_engine.agents.research_loop import ResearchLoop` inside `/api/research/trigger` (line 596) → removed/replaced
- `trading_engine/tests/test_phase5_research_agents.py` — imports `ResearchLoop`, `ResearchAgent`, `HypothesisAgent`, `CodingAgent`, `ReviewAgent` → test suite no longer runs against active code

**Preserved (not deleted):**
- Source file `trading_engine/agents/research_loop.py` archived to `archive/research_loop_archive/`
- `test_phase5_research_agents.py` archived as historical test artifact

---

## 4. Next steps pending client approval

1. Move `docs/prd_and_roadmap.md` → `archive/documentation/`
2. Remove `research_loop` runtime import from `server.py` and document exclusion
3. Archive candidate files + `test_phase5_research_agents.py`
4. Archive `.whl`, `graphify-out/`; decide on `UII/` screenshots
5. Update `DEVELOPMENT_PLAN_AND_TODO.md`, `PROJECT_AUDIT.md`, `KNOWN_ISSUES.md`

No commits, pushes, merges, or permanent deletions without explicit client approval.
