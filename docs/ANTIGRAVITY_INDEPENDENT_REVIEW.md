# ANTIGRAVITY INDEPENDENT ARCHITECTURE REVIEW — FinceptEngine Phase C

**Project:** FinceptEngine — Binance Spot + USDⓈ-M Futures Transformation  
**Branch under review:** `audit/planning-finceptengine-transformation` (from `dev`, NOT committed, NOT pushed, NOT merged)  
**Review date:** Tue Nov 24 2026  
**Reviewer:** Independent Technical Architect & Reviewer  
**Mandate:** Challenge OpenCode's Phase B/C conclusions; do NOT accept them at face value.  
**Constraint honored:** No source code modified, no files deleted, no commits/pushes/merges, no implementation begun.

---

## Executive Summary

OpenCode recommends **in-place evolution** of the existing v0.1.0 codebase (do not rebuild), with three targeted implementation gaps (dynamic top-10 eligibility, max-5 strategy cap, USDⓈ-M Futures WS connector) plus a root `pyproject.toml` manifest.

**My independent assessment: The in-place-evolution direction is reasonable, but the review leading to it is incomplete and one reported verdict (zero-look-ahead PASS) is not justified while a live finding remains unresolved.** Three of the four "gaps" are confirmed absent from the codebase; the external-repository comparison was never performed (13-URL blocker open). I recommend **B — Architecture approved after specified corrections**, with corrections to be completed and re-verified before any implementation begins.

---

## Decision 1: Rebuild vs. In-Place Evolution

### OpenCode's conclusion
**IN-PLACE EVOLUTION (do NOT rebuild).** The codebase is complete through Phase 6, all six phase test suites verified (22/22, 61/61, 24/24, 14/14, 11/11, 9/9), internally consistent, and only documentation cleanup + three targeted implementation gaps are needed. A rebuild would reinvent a working, vetted codebase.

### Independent assessment
**Directionally acceptable, but the comparison is ungrounded.** OpenCode compared "in-place" against "greenfield rebuild" only — it never evaluated the third option it was asked to challenge: **selectively integrating code from external repositories.** The instruction explicitly said "Do not automatically accept OpenCode's recommendation" and "Evaluate whether evolving ... is genuinely better than selectively integrating code from external repositories."

That external-repo evaluation cannot happen because the 13 GitHub repository URLs were never supplied/inspected (see Decision 2). So the rebuild-vs-in-place recommendation rests on a false dichotomy: in-place vs. rebuild, with the external-integration option never examined.

### Supporting source-code evidence
- `docs/REPOSITORY_RESEARCH.md`: "13 GitHub Repository URLs Not Found (STILL OPEN)"; grep for `github.com`/`github.io`/`git.com` across all codebase files returned zero matches; `raw.githubusercontent.com/...` returns 404.
- `KNOWN_ISSUES.md` KI-010: *"The 13 repo URLs are from an external source ... not found anywhere in codebase."*
- All six phase test suites are reported passing (22/22, 61/61, 24/24, 14/14, 11/11, 9/9) — taken from `PROJECT_AUDIT.md` / `PEER_REVIEW_LOG.md`; not independently re-run by this review (no `pytest` execution per AGENTS.md Section 4 until manifests exist; no root manifest exists either).

### Risks / disagreements
- If the 13 external repos contain battle-tested Binance USDM futures connectors, top-10 volume scanners, or execution-realism patterns, in-place evolution may miss them entirely.
- The "all tests pass" claim supports internal consistency but does not validate that the codebase is *correct for the Binance-only scope* (see Decision 5).

### Recommended action
Keep in-place evolution as the working hypothesis, but **do not finalize it** until the 13-URL blocker is resolved (client supplies URLs or formally waives external research). If client waives, document the waiver and proceed.

### Client approval needed?
**Yes** — to supply the 13 repo URLs or formally waive external-repository research before implementation planning is locked.

---

## Decision 2: Repository Research Completeness (13-URL blocker)

### OpenCode's conclusion
Research is "complete" with a honestly-recorded blocker: 12/14 research areas verified via local codebase + tests; 13 GitHub URLs blocker recorded in `docs/REPOSITORY_RESEARCH.md`, `KNOWN_ISSUES.md` KI-007/KI-010.

### Independent assessment
**Incomplete and mischaracterized.** OpenCode reports "12/14 areas verified" but the verification method for those areas is "local codebase + tests" — **local FinceptEngine implementation is not evidence that an external repository was inspected.** The task explicitly warned: *"Do not treat local FinceptEngine implementations as evidence that an external repository was inspected."* No external repo was cloned, read, or diffed. The blocker is not "honestly recorded and manageable"; it is a hard stop on the external-integration comparison.

### Supporting source-code evidence
- `docs/REPOSITORY_RESEARCH.md` lines 13–19: verification performed = grep for github URLs (zero matches), raw.githubusercontent 404s, no repos/submodules/remotes.
- `KNOWN_ISSUES.md`: KI-007 and KI-010 still open (external source must supply URLs).
- No `repos/`, no `.git/` submodules, no git remotes referencing 13 external repos.

### Risks / disagreements
- The rebuild-vs-in-place recommendation (Decision 1) cannot be defended without this comparison.
- KI-010 specifically states the client must supply the URLs; work is blocked on client action, not on OpenCode.

### Recommended action
Do not mark repository research complete. Either (a) client supplies the 13 URLs so they can be inspected, or (b) client formally waives external research and the in-place recommendation is re-justified on internal-merits alone.

### Client approval needed?
**Yes** — supply URLs or waive.

---

## Decision 3: Zero-Look-Ahead — ZLA-001 in session_volume_profile() (CRITICAL)

### OpenCode's conclusion
**PASS — with 1 Medium-severity finding (ZLA-001).** Zero-look-ahead claim (`t <= T`) holds across codebase; all indicators/signals/strategies/backtests use only past-and-current-bar data. ZLA-001 is noted as a Medium finding in `indicators/orderflow.py` `session_volume_profile()`.

### Independent assessment
**The PASS verdict is NOT justified while ZLA-001 remains unresolved.** ZLA-001 is not a minor cosmetic issue — it is genuine look-ahead bias that directly corrupts backtest integrity.

### Supporting source-code evidence (`trading_engine/indicators/orderflow.py`, lines 177–261)

```python
def session_volume_profile(high, low, close, volume, anchor="day", value_area_pct=0.70):
    ...
    df["date"] = tz_naive.date
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0

    for date, group in df.groupby("date"):
        idx = group.index
        tp = typical_price.loc[idx]
        vol = group["volume"]
        ...
        price_min = tp.min()          # <-- min over ENTIRE day (future bars included)
        price_max = tp.max()          # <-- max over ENTIRE day (future bars included)
        bin_size = (price_max - price_min) / 100.0
        bins = np.arange(price_min, price_max + bin_size, bin_size)
        bin_idx = np.digitize(tp.values, bins) - 1
        vol_by_bin = pd.Series(vol.values, index=bin_idx).groupby(level=0).sum()
        total_vol = vol_by_bin.sum()
        target_vol = total_vol * value_area_pct
        poc_bin = vol_by_bin.idxmax()
        ...
    return {
        "poc": pd.Series(poc, index=df.index).ffill(),
        "vah": pd.Series(vah, index=df.index).ffill(),
        "val": pd.Series(val, index=df.index).ffill(),
    }
```

The function groups by date and computes `tp.min()` / `tp.max()` over the **entire day's** typical prices, builds volume-at-price bins from the full day's volume, derives POC/VAH/VAL from that full-day profile, then forward-fills. At bar `t` (mid-day), the returned POC/VAH/VAL reflect the day's high/low and total volume — including bars after `t` (t > T). This is **intra-day look-ahead**.

The docstring claims *"Forward-filled within the session so each bar sees the current session's profile computed from past bars only"* — this is **false**; the profile is computed from the full day group, not an expanding/past-only window.

### Effect on backtesting
- Any strategy using POC/VAH/VAL as signals sees future intraday price extremes and full-day volume distribution at earlier bars.
- Backtest P&L, win rate, and expectancy are inflated and **not replicable in live trading** (the future profile is unknown at bar `t`).
- The validation gatekeeper (OOS, walk-forward, heatmap, cost stress) consumes backtester output, so a biased profile can cause a flawed V2 candidate to pass the gate and displace V1 — directly violating Rule 2 ("Never let AI approve its own strategy").

### Remediation required
Replace the full-day group computation with an **expanding per-session window**: at each bar index `i`, compute POC/VAH/VAL from bars within the same session up to and including `i` only (`df.iloc[:i+1]` filtered to current session), then assign to bar `i`. Do not forward-fill from a full-day calculation. Re-run the look-ahead leakage tests and revalidate ZLA before claiming PASS.

### Risks / disagreements
Disagreement: OpenCode marks ZLA-001 "Medium" and still issues PASS. I assess it as **High** for backtest integrity and **PASS-with-unresolved-High-finding is invalid** — the zero-look-ahead claim cannot be asserted true until ZLA-001 is fixed and re-tested.

### Recommended action
Fix `session_volume_profile()` to be past-only (expanding window per session), add/extend a unit test asserting no intra-day look-ahead (POC/VAH/VAL at bar `i` invariant to bars `i+1..end-of-day`), re-run the full test suite, then reissue the ZLA verdict.

### Client approval needed?
No for the fix itself (bug remediation), but **yes** if the fix changes indicator output contracts consumed by strategies/UI (document in DATABASE_AND_DATA_CONTRACTS.md per Rule 2).

---

## Decision 4: Cleanup Safety

### OpenCode's conclusion
Cleanup followed the archive-before-remove rule; nothing permanently deleted; deletion reasons recorded in `archive/documentation/DOCUMENTATION_CLEANUP_REPORT.md`.

### Independent assessment
**Largely confirmed, with one caveat.** Deleted source files were preserved in the archive and verified byte-identical:
- `trading_engine/agents/research_loop.py` deleted → `archive/research_loop_archive/research_loop.py` (diff confirms IDENTICAL).
- `trading_engine/tests/test_phase5_research_agents.py` deleted → `archive/research_artifacts/test_phase5_research_agents.py`.
- `docs/prd_and_roadmap.md` → `archive/documentation/prd_and_roadmap.md`.
- `trading_engine/strategies/candidates/__init__.py` deleted (1 line); 566 candidate files were already archived to `archive/research_artifacts/` (per cleanup report).

### Supporting source-code evidence
- `git status`: deleted files are `D` in working tree (research_loop.py, test_phase5_research_agents.py, strategies/candidates/__init__.py); nothing staged or committed (Rule 6 followed — no commits on this branch).
- `diff <(git show HEAD:...) archive/...` → IDENTICAL for research_loop.py.
- `archive/` is untracked (`??` in git status) — preserved but not yet versioned.

### Caveat
The `.planning/` directory and `archive/` are new untracked additions to the working tree. They are not source deletions, but they are working-tree changes on the phase branch that should be committed (with client approval) before merging to `dev`, per Rule 6 ("feature or modification gets its own commits within the phase branch"). Currently nothing is committed.

### Risks / disagreements
Low risk. The only concern is that `archive/` contains ~35MB of `graphify-out/` cache and 8 `.whl` files plus 4 screenshots — large binary artifacts in an untracked directory. If committed, they bloat the repo. Recommend excluding binaries (`.whl`, `graphify-out/cache`, screenshots) from the commit, keeping only textual archives (research_loop.py, test file, docs, research artifacts).

### Recommended action
Cleanup safety is acceptable pending client approval to commit the archived changes (excluding binaries). No source was permanently deleted.

### Client approval needed?
**Yes** — to commit archived changes to the phase branch (Rule 6), excluding binary bloat.

---

## Decision 5: Technical Completeness — Reported Gaps

OpenCode reports exactly three implementation gaps remain: (1) dynamic top-10-by-24h-quote-volume eligibility, (2) max-5 strategy cap enforcement, (3) USDⓈ-M Futures WS connector. I independently verified each, plus spot/futures isolation, backtesting realism, and risk correctness.

### 5a. Dynamic top-10 Binance volume scanner — CONFIRMED NOT IMPLEMENTED

**OpenCode:** Lists it as a gap to implement.
**Independent:** Confirmed absent.
- `config.py` line 25: `CRYPTO_TRADEABLE_PAIRS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")` — hardcoded 3 pairs, not top-10 by rolling 24h quote volume.
- No `top_10`, `top10`, `eligible_universe`, `quote_volume_rank` symbols anywhere in `trading_engine/` (grep returned no matches).
- `server.py` line 198 queries `quote_volume` from DB but the universe is fixed; no 24h rolling ranker or eligibility filter exists.
- **Risk:** Without it, the engine trades only 3 hardcoded pairs, violating the "top 10 eligible crypto by rolling 24h quote volume" requirement.

### 5b. Maximum five-strategy cap — CONFIRMED NOT IMPLEMENTED

**OpenCode:** Lists it as a gap; ADR-007 defers enforcement to implementation.
**Independent:** Confirmed absent.
- No `STRATEGY_LIMIT`, `MAX_STRATEGIES`, `strategy_count`, `active_strategies` anywhere (grep returned no matches).
- `strategies/candidates/` was archived (566 candidate files removed from active tree); no cap logic guards the active strategy set.
- **Risk:** Unlimited candidate strategies could be loaded/approved, violating the max-5 rule. ADR-007 explicitly defers this — acceptable only if documented as pre-implementation work.

### 5c. Binance USDⓈ-M Futures (perpetual) WS connector — CONFIRMED NOT IMPLEMENTED

**OpenCode:** Lists it as a gap.
**Independent:** Confirmed absent.
- `data/feeds/binance_ws.py` connects only to `wss://stream.binance.com:9443/ws` (Spot public WS). Zero references to `futures`, `usdm`, `perp`, `dstream`, `fapi`, `binance-futures`, or `mark_price` (grep exit 1 = no matches).
- `config.py` defines `BINANCE_PERP_MAKER_BP = 2.0` / `BINANCE_PERP_TAKER_BP = 4.0` fee constants and `DB_PATH`, but no perpetual feed, mark-price stream, or funding-rate logic.
- `server.py` line 304 hardcodes `market_type = "CRYPTO_SPOT"`; the `CRYPTO_PERP` slice in `memory/db.py` (line 26: `market_type TEXT NOT NULL -- 'CRYPTO_SPOT', 'CRYPTO_PERP'`) is never populated by a live feed.
- **Risk:** The USDⓈ-M Futures half of the transformation has no data path. Spot-only engine cannot trade perps.

### 5d. Spot/Futures data isolation — PARTIALLY IMPLEMENTED (schema only)

- Schema: `memory/db.py` line 26 supports `CRYPTO_SPOT` / `CRYPTO_PERP`; `server.py` line 201 filters by `market_type`.
- Reality: `server.py` hardcodes `market_type = "CRYPTO_SPOT"` everywhere; no perp feed writes to `CRYPTO_PERP`. Isolation exists at the schema layer but not at the ingestion layer. Until the perp connector (5c) is built, futures data is isolated-by-absence.

### 5e. Backtesting execution realism — BASIC / PARTIAL

- `backtester.py` deducts slippage + commission per leg via `RiskManager`, models stop/target exits on current-bar OHLC (`low <= stop_loss`, `high >= target`), records MAE/MFE, slippage, commission, net P&L, R-multiple. Deterministic, no future leakage in exits. Reasonable for a v0.1.0.
- Gatekeeper (Decision 3 aside) applies a 1.5x slippage cost stress (PF_OOS >= 1.15, ER >= +0.12R) — a good execution-realism guard.
- **Gaps vs production realism:** no latency modeling, no partial fills, no slippage scaling with size/volatility, no perp liquidation/bankruptcy modeling, no funding-cost deduction for perps, no maker/taker distinction in fill simulation (uses single `slippage_bp` per leg). Acceptable for paper-first v0.1, but should be flagged before live paper trading.

### 5f. Risk-management correctness — APPEARS SOUND (not deeply audited)

- `risk/risk_manager.py`: position sizing from equity × max risk %, ATR stop buffer, slippage/commission cost deduction, daily loss circuit breaker (3%), max consecutive losses (2), max drawdown kill-switch, min R:R (1.5) validation.
- `backtester.py` line 253: `risk.validate_rr(entry_price, stop_loss, target_1, direction)` gates entries on R:R.
- **Note:** Not independently executed or stress-tested by this review; correctness claim rests on reported phase tests. Should be included in pre-implementation verification.

### Summary table

| Gap | OpenCode says | Independent finding | Status |
|-----|---------------|---------------------|--------|
| Dynamic top-10 volume scanner | Gap to implement | NOT implemented (3 hardcoded pairs) | ❌ Absent |
| Max-5 strategy cap | Gap; ADR-007 deferred | NOT implemented (no cap logic) | ❌ Absent |
| USDⓈ-M Futures WS connector | Gap to implement | NOT implemented (Spot WS only) | ❌ Absent |
| Spot/Futures isolation | Schema supports it | Schema only; no perp ingestion | ⚠️ Partial |
| Backtesting execution realism | Implemented | Basic slippage/commission + cost-stress gate | ⚠️ Partial |
| Risk-management correctness | Implemented | Appears sound, unaudited by this review | ⚠️ Unverified |

### Recommended action
Treat the three "absent" items as required pre-implementation work, not optional gaps. Do not begin implementation planning until they are specified (and ZLA-001 fixed).

### Client approval needed?
**Yes** — these are new trading-relevant features (top-10 scanner, perp connector, strategy cap); per Rule 6 and the project constraints, client approval is required before implementation.

---

## Decision 6: Manifest (pyproject.toml + requirements.txt)

### OpenCode's conclusion
Root `pyproject.toml` (new) + keep existing `trading_engine/requirements.txt`; both required before `pip install` / `pytest` per AGENTS.md Section 1.

### Independent assessment
**Not done.** `git status` and `ls` confirm **no `pyproject.toml`, no `requirements.txt` at repo root.** Only `trading_engine/requirements.txt` exists (8 pinned deps: fastapi, uvicorn, pandas, numpy, pandas-ta, scipy, websockets, pytest). AGENTS.md Section 1 explicitly prohibits running `pytest`, `pip install -r`, etc. until manifests exist — yet OpenCode reports tests were run. This is inconsistent: either tests were run outside the repo root (unverifiable) or the "verified" test counts are not reproducible from the current tree.

### Recommended action
Create root `pyproject.toml` + `requirements.txt` before any further test execution or implementation. This is a prerequisite, not a gap.

### Client approval needed?
No (manifest creation is non-trading, non-DB-changing), but document per Rule 2.

---

## Overall Recommendation

### OpenCode's final posture (reported)
Architecture approved for implementation planning (PEER_REVIEW_LOG: "SIGN-OFF READY").

### My independent recommendation: **B — Architecture approved after specified corrections**

**Rationale:** In-place evolution is the right direction and the codebase is internally consistent through Phase 6. However, approval for implementation planning is premature because:

1. **ZLA-001 is unresolved** and invalidates the zero-look-ahead PASS verdict — a core hard constraint (Constraint 1). Must be fixed and re-validated first.
2. **The 13-URL external-repo research blocker is open** — the rebuild-vs-in-place comparison was never completed; the external-integration alternative was not evaluated.
3. **Three implementation gaps are confirmed absent** (top-10 scanner, max-5 cap, perp WS connector) and must be specified before implementation planning.
4. **No root manifest exists** — test counts are not reproducible; `pytest` cannot be run per AGENTS.md until manifests exist.
5. **No cleanup changes are committed** (Rule 6) — the branch is all working-tree, nothing staged.

### Conditions to move to recommendation A
Before implementation planning begins, the following must be complete and client-approved:

| # | Correction | Owner | Client approval? |
|---|------------|-------|------------------|
| 1 | Fix `session_volume_profile()` to past-only expanding window; add look-ahead regression test; re-run full suite; reissue ZLA verdict | Backend/QA | No (bug fix), yes if output contract changes |
| 2 | Resolve 13-URL blocker: client supplies URLs for inspection, or formally waives external research | Client | **Yes** |
| 3 | Specify (not implement) top-10 scanner, max-5 cap, perp WS connector, root manifest | Architect | **Yes** (new trading features) |
| 4 | Commit archived cleanup changes to phase branch (exclude binaries) | Architect | **Yes** (Rule 6) |
| 5 | Re-run `pytest` from root after manifests exist; verify all phase suites | QA | No |

### Final recommendation statement
**B.** Approve the in-place-evolution architecture **after** the above corrections are made and verified. Do not proceed to implementation planning while ZLA-001 is open, the 13-URL blocker is unresolved, or the three confirmed-absent gaps are unspecified.

---

## Appendix: Files reviewed (read in full or part)

- `PROJECT_AUDIT.md`, `KNOWN_ISSUES.md`, `DEVELOPMENT_PLAN_AND_TODO.md`, `PEER_REVIEW_LOG.md`, `CHANGELOG.md`
- `docs/ARCHITECTURE_DECISIONS.md`, `docs/REBUILD_RECOMMENDATION.md`, `docs/REPOSITORY_RESEARCH.md`, `docs/ZERO_LOOK_AHEAD_REVALIDATION.md`, `docs/master_architecture.md`, `docs/database_and_data_contracts.md`
- `archive/documentation/DOCUMENTATION_CLEANUP_REPORT.md`
- `trading_engine/indicators/orderflow.py` (ZLA-001 evidence)
- `trading_engine/config.py` (hardcoded pairs, fee schedules, no scanner/cap)
- `trading_engine/data/feeds/binance_ws.py` (Spot-only WS, no perp)
- `trading_engine/validation/backtester.py`, `trading_engine/validation/gatekeeper.py`, `trading_engine/risk/risk_manager.py`, `trading_engine/execution/paper_simulator.py`
- `trading_engine/backend/server.py` (market_type hardcoded CRYPTO_SPOT)
- `trading_engine/memory/db.py` (market_type schema)
- `.planning/work_state.json`, `git status`, `git diff`, `git log`
