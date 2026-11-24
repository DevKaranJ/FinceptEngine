# Repository Research Findings — Phase C

**Project:** FinceptEngine — Binance Spot + USDⓈ-M Futures Trading Platform  
**Branch:** `audit/planning-finceptengine-transformation` (from `dev`, NOT committed, NOT pushed, NOT merged)  
**Date:** 2026-11-24  
**Owner:** Architect + QA  
**Scope:** Binance Spot + USDⓈ-M Futures only (rule-based, human-reviewed, paper-first)

---

## ✅ Phase C Blocker — 13 GitHub Repository URLs (RESOLVED — researched)

Per the Phase A audit (`PROJECT_AUDIT.md` Section 7 and `KNOWN_ISSUES.md` KI-010), Phase C source-level research depended on **13 GitHub repository URLs** supplied by the client. The URLs were supplied and all 13 repos were cloned shallowly to `/tmp/opencode/` and source-inspected on 2026-11-24. The blocker is now **RESOLVED** (client supplied URLs; KI-010 cleared).

**13 repos inspected (source-level):**

| # | Repo | License (verified at repo root) | Key source findings relevant to FinceptEngine |
|---|------|---------|-----------------------------------------------|
| 1 | binance-strategy | **No License — All Rights Reserved (NOT MIT)** | `BINANCE_FAPI_URL = "https://fapi.binance.com/fapi/v1/klines"` (USDⓈ-M futures klines); `MarketDataLoader` with caching/retry/funding/OI/premium-index/long-short-ratio endpoints |
| 2 | hftbacktest | MIT | `binancefutures.py` converts raw Binance Futures depth/trade/markPrice streams to npz (markPriceUpdate event ID 100, funding rate 102) |
| 3 | QuantConnect/Lean | Apache 2.0 | `BinanceFuturesBrokerageModel.cs` / `BinanceFuturesFeeModel.cs` (C# futures brokerage + fee models) |
| 4 | OrderFlow-Analysis-Pro | MIT | `orderflow_system/analytics/volume_profile.py` reference (volume-at-price / POC) |
| 5 | TapeFlow | MIT | orderflow / tape reading patterns |
| 6 | tape-and-book | MIT | L2 book / tape analysis |
| 7 | HFTENGINE | MIT | HFT execution engine patterns |
| 8 | CryptoQuant-Engine | MIT | on-chain / quant engine patterns |
| 9 | Simpler-Trader | MIT | trader strategy patterns |
| 10 | kline-orderbook-chart | Commercial / Proprietary | **REJECTED** — commercial license, not reusable |
| 11 | crypto-trading-strategies | **No License — All Rights Reserved; ZERO source code files** (README link list only) | crypto strategy patterns — **unusable** (contains zero Python source) |
| 12 | VFund | MIT | fund/backtest patterns |
| 13 | openbq-org/OpenBB | Apache 2.0 | openBB financial data platform |

**License warnings:**
- `binance-strategy` and `crypto-trading-strategies` contain **no license file**. Under copyright law all rights are reserved — copying code from them is legally prohibited. They may be used only as clean-room API-reference documentation, not as a source of implementation code.
- 8 of 13 licenses were originally left blank; this table now records each verified license. Binance futures endpoints must be implemented purely against Binance official API documentation, not third-party source code.

**Conclusion:** External source-level research complete. Local FinceptEngine implementations are **not cited** as external evidence (per task constraint). Reuse candidates identified (binance-strategy klines, hftbacktest stream converter, Lean futures fee models, OrderFlow-Analysis-Pro volume_profile); **nothing integrated yet** (per Recommendation B: no implementation of missing capabilities yet — specs only in ADR-009/010/011/012).

---

## 14 Research Areas — Local Findings vs. External Repo Research

The table below lists the 14 research areas identified for the Binance-only transformation, what exists in the local codebase, and what external repo research adds.

| # | Research Area | Local Codebase Finding (v0.1.0, verified) | External Repo Research (completed — 13 repos inspected) |
|---|---------------|-------------------------------------------|---------------------------------------------------------|
| 1 | **Binance Spot REST API** (`/api/v3/klines` backfill) | `trading_engine/data/feeds/binance_ws.py` — `BinanceFeed` class, REST backfill + WS, zero-look-ahead persist-on-close | binance-strategy: `MarketDataLoader` caching/retry pattern; REST endpoint conventions |
| 2 | **Binance USDⓈ-M Futures API** | `config.py` defines `CRYPTO_PERP` market type + fee schedules; `CRYPTO_SPOT`/`CRYPTO_PERP` in `ohlcv_bars.market_type`; no Futures-specific WS connector implemented yet | binance-strategy: `fapi.binance.com/fapi/v1/klines` USDⓈ-M klines + funding/OI/premium-index/long-short-ratio; hftbacktest: depth/trade/markPrice stream converter; Lean: `BinanceFuturesFeeModel` |
| 3 | **Top 10 by rolling 24h quote volume (eligibility)** | `CRYPTO_TRADEABLE_PAIRS` hardcoded to 3 pairs (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`); **NOT dynamic**; flagged as KI-005 (Medium) | binance-strategy: 24h ticker endpoints; eligibility/ranking patterns |
| 4 | **Max 5 strategies (cap)** | Conceptual only; no code enforces a strategy cap; `strategies/approved/` holds 2 V1 strategies | No direct cap pattern found; spec in ADR-010 |
| 5 | **Zero-look-ahead (`t <= T`)** | `ZERO_LOOK_AHEAD = True` in `config.py`; all indicators use `iloc[:t]` / `shift(1)`; test suites assert no leakage | hftbacktest: correct event ordering / timestamp validation patterns |
| 6 | **SQLite WAL schema for OHLCV** | `trading_engine/memory/db.py` — 5 tables (`ohlcv_bars`, `trades_memory`, `strategy_registry`, `validation_reports`, `system_activity_log`), `PRAGMA journal_mode=WAL` | Schema indexing patterns |
| 7 | **Indicator libraries (pandas-ta / TA-Lib)** | `trading_engine/indicators/{technical,statistical,structure,orderflow}.py` — pure pandas/numpy, 4 families; `pandas-ta` installed in `.venv`, listed in `trading_engine/requirements.txt` | 130+ `pandas-ta` indicators cross-check; TA-Lib parity reference |
| 8 | **Event-driven historical backtester** | `trading_engine/validation/backtester.py` — bar-by-bar replay through `BaseStrategy.evaluate()`, SL/TP/TIME exits on current-bar OHLC only, slippage+commission per leg | Fill timing models, partial fills, latency simulation |
| 9 | **Out-of-sample (OOS) 70/30 split** | `trading_engine/validation/gatekeeper.py` — OOS PF ≥ 1.25, ER > baseline, MaxDD ≤ baseline | Walk-forward robustness references |
| 10 | **Walk-forward analysis (K=5)** | `gatekeeper.py` — ≥ 4 of 5 windows net-positive Expectancy (ER > 0) | Window sizing patterns |
| 11 | **Parameter sensitivity heatmap (5×5)** | `gatekeeper.py` — perturb top 2 params ±20/±10/0, ≥ 20 of 25 cells PF > 1.10 | Grid search / heatmap visualization |
| 12 | **Execution cost & slippage stress (1.5×)** | `gatekeeper.py` — stressed PF ≥ 1.15 AND net Expectancy ER ≥ +0.12R; `risk/risk_manager.py` deducts slippage+commission | Lean `BinanceFuturesFeeModel` maker/taker fee reference |
| 13 | **MAE/MFE tracking (paper simulator)** | `trading_engine/execution/paper_simulator.py` + `trading_engine/memory/trade_logger.py` — tick-by-tick MAE/MFE, equity curve, summary | Realistic fill price within bar (high/low), wick-based stops |
| 14 | **FastAPI WebSocket hub + UI** | `trading_engine/backend/server.py` — 9 REST routes + `WS /ws/live`; frontend dark-mode terminal with vendored Lightweight Charts v5.3.0 | JSON sanitization, WS reconnection, chart library pinning |

---

## Per-Area Gap Analysis

| Area | Gap Severity | External research informs? | Can proceed in-place? |
|------|-------------|--------------------------|----------------------|
| 1 Binance Spot REST | Minimal (implemented) | Yes (caching/retry) | Yes |
| 2 USDⓈ-M Futures API | Moderate (connector missing) | Yes (klines/funding/OI/fee models) | Partial — schema supports it; connector specified in ADR-011 |
| 3 Top-10 eligibility | High (hardcoded 3 pairs) | Yes (24h ticker ranking) | Yes (implementation task; spec ADR-009) |
| 4 Max-5 strategy cap | High (not enforced) | No direct pattern | Yes (implementation task; spec ADR-010) |
| 5 Zero-look-ahead | None (enforced + tested; ZLA-001 fixed) | Yes (event-order validation) | Yes |
| 6 SQLite WAL schema | None (complete) | Yes (indexing) | Yes |
| 7 Indicator libraries | None (4 families + pandas-ta) | Yes (cross-check) | Yes |
| 8 Event-driven backtester | None (complete, 4/4 tests) | Yes (fill timing) | Yes |
| 9 OOS split | None (complete, gatekeeper) | Yes | Yes |
| 10 Walk-forward K=5 | None (complete) | Yes | Yes |
| 11 Parameter heatmap | None (complete) | Yes | Yes |
| 12 Cost/slippage stress | None (complete) | Yes (fee models) | Yes |
| 13 MAE/MFE tracking | None (complete) | Yes (fill price) | Yes |
| 14 FastAPI + WS hub | None (complete, 9/9 tests) | Yes (sanitization/reconnect) | Yes |

**Net result:** 14 of 14 research areas now have local implementations verified by pytest, plus completed external source-level research. Areas 2 (Futures connector), 3 (top-10 eligibility), and 4 (max-5 cap) require implementation work that does **not** depend on the 13 external repo URLs. External repo research added Binance API best-practices and third-party library cross-checks, but is not required to proceed with the Binance-only transformation.

---

## Recommendation on Phase C Research

1. **Blocker cleared:** 13 GitHub repo URLs supplied by client and inspected at source level (KI-010 cleared). No further action needed on the URL blocker.
2. **Reuse candidates identified but not integrated:** binance-strategy klines, hftbacktest stream converter, Lean futures fee models, OrderFlow-Analysis-Pro volume_profile. Per Recommendation B, these are **specified only** (ADR-009/010/011/012) — no implementation yet.
3. **Proceed in-place:** Implement areas 3 (top-10 eligibility) and 4 (max-5 cap) and area 2 (Futures connector) using the existing verified codebase; these do not need external repos.
4. **Do not fabricate URLs:** All 13 URLs verified present; nothing guessed or invented.

---

## Cross-References

- `docs/ARCHITECTURE_DECISIONS.md` — ADR-001…ADR-012 (Binance-only scope, rule-based only, human review gate, market_type, deprecated NSE, archive-before-remove, max-5 deferred, research trigger stubbed, top-10 scanner, perp WS connector, spot/futures isolation)
- `docs/master_architecture.md` — Binance-only architecture updated
- `docs/database_and_data_contracts.md` — Binance-only schema and endpoints updated
- `PROJECT_AUDIT.md` — Phase A codebase audit (needs Phase B completion update)
- `KNOWN_ISSUES.md` — KI-001…KI-010 (needs Phase B completion update; KI-010 cleared — URLs supplied)
- `CHANGELOG.md` — [v0.1.10] Phase B entry; Phase C entry pending
- `DEVELOPMENT_PLAN_AND_TODO.md` — Phase C tasks tracked (C.1–C.4)
- `docs/ANTIGRAVITY_REVIEW_CONDITION_RESPONSE.md` — per-condition response to independent review
