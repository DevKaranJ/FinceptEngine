# Self-Improving Multi-Paradigm Quantitative Trading Engine

A modular, feedback-driven quantitative trading engine that researches, backtests, evaluates, and improves its own strategies across **Crypto (24/7 Spot & USDT-M Perpetuals)** and **Indian Intraday Equities (NSE F&O)**—while keeping real-money trade execution **100% manual**.

---

## Core Capabilities

1. **Strategy-Agnostic "Lego Block" Architecture**:
   - Build and combine strategies across four independent indicator families:
     - **Classical Technical Analysis (`indicators/technical.py`)**: EMA, SMA, RSI, ATR, Bollinger Bands, MACD, Supertrend, Daily Fibonacci Pivots.
     - **Quantitative & Research-Paper Models (`indicators/statistical.py`)**: Rolling Z-Score, Hurst Exponent, Volatility Percentiles, Linear Regression Slope, Relative Strength (`RS`).
     - **Price Action & Market Structure (`indicators/structure.py`)**: `PDH`/`PDL`/`PDC`, Opening Range (`ORH`/`ORL`), 3-Touch Dynamic Trendlines (`TL`), Fair Value Gaps (`FVG`), Order Blocks (`OB`), Liquidity Sweeps.
     - **Volume & Orderflow (`indicators/orderflow.py`)**: Intraday `VWAP`, Time-Normalized `RVOL`, Session Volume Profile (`POC`/`VAH`/`VAL`), `CVD`, Bid×Ask Footprint Imbalances (`300%`), Iceberg Detection.
2. **Trade Memory with `MAE` & `MFE` Diagnostics (`memory/`)**:
   - Every backtest, paper trade, and manual trade is logged in SQLite (`WAL` mode) with **Maximum Adverse Excursion (`MAE`)**, **Maximum Favorable Excursion (`MFE`)**, slippage, commissions, active signals, and the exact market regime snapshot at entry.
3. **Automated Regime Weakness Detection (`evaluation/`)**:
   - Segments strategy results across Volatility Regimes, Trend Regimes, RVOL Tiers, and Session Hours to pinpoint where and why a strategy loses money.
4. **4-Role AI Self-Improvement Loop (`agents/`)**:
   - **Research Agent** (diagnoses root cause) $\rightarrow$ **Hypothesis Agent** (proposes testable filter/signal upgrades) $\rightarrow$ **Coding Agent** (implements candidate `V2` in `strategies/candidates/`) $\rightarrow$ **Review Agent** (audits for look-ahead bias and risk rules).
5. **Independent Validation Gatekeeper (`validation/`)**:
   - **Never lets AI approve its own strategy.** Candidate `V2` is promoted only if it passes **In-Sample/Out-of-Sample (`70/30`)**, **Walk-Forward Analysis**, **$5\times 5$ Parameter Sensitivity Heatmap**, and **Slippage/Commission Stress Tests**. If rejected, Baseline `V1` stays untouched.
6. **Paper First & 1-Click Manual Order Ticket (`execution/` & `frontend/`)**:
   - Approved strategies run in live **Paper Execution Mode** first and generate a real-time **1-Click Manual Order Ticket** (with ATR-buffered Stop-Loss, slippage pad, and audio/Telegram alerts) for manual execution.

---

## Project Documentation Index

Keep these documentation files in the root (or `docs/`) of your repository so both human developers and OpenCode AI agents share the exact same specifications:

| Document File | Description |
| :--- | :--- |
| **`MASTER_ARCHITECTURE.md`** | Complete 6-layer system architecture, data flow diagram, and unified folder structure. |
| **`PRD_AND_ROADMAP.md`** | Product Requirements Document, strict non-goals, and the 6-phase engineering roadmap with hard stop gates. |
| **`DATABASE_AND_DATA_CONTRACTS.md`** | SQLite WAL database schema (`ohlcv_bars`, `trades_memory`, `strategy_registry`, `validation_reports`), JSON data contracts, and FastAPI endpoints. |
| **`STRATEGY_AND_VALIDATION_SPEC.md`** | Developer guide for authoring Lego-block `indicators/`, `signals/`, and `strategies/`, plus the exact math for `MAE`/`MFE` and the 4-stage Validation Gatekeeper. |
| **`AGENTS.md`** | *(Generated via `opencode_ecc_multiagent_setup_prompt.md`)* Multi-agent role definitions (`Architect`, `Backend`, `Frontend`, `QA`, `Reviewer`) and phase stop-gate rules. |

---

## Quick Start (Once Phase 1–6 Are Built)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Automated Test Suite (`pytest`)
```bash
pytest -v
```

### 3. Launch the Full-Stack Engine & Terminal UI
```bash
uvicorn backend.server:app --host 127.0.0.1 --port 8765 --reload
```
Open **`http://127.0.0.1:8765`** in your browser to access the Live Charting Terminal, Trade Memory & Evaluation Diagnostics, and the AI Self-Improvement & Validation Gatekeeper Lab.
