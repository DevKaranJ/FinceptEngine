# Product Requirements Document (PRD) & Phased Engineering Roadmap

**Project Name:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Document Version:** 1.0  
**Status:** Active Blueprint  

---

## 1. Product Vision & Problem Statement

Most retail and semi-systematic traders fail for two reasons:
1. **Fragile Single-Idea Strategies**: A strategy built from an indicator or online research paper may work in one market regime (e.g., high-volatility trends) and bleed capital when the regime shifts (e.g., low-volatility chop), without the trader knowing *why* it broke.
2. **Unverified Tweaking (Overfitting)**: When a strategy starts losing, traders randomly tweak parameters or add indicators without testing Out-of-Sample (OOS) generalization, Walk-Forward stability, or parameter sensitivity.

**The Solution:**  
Build a modular, strategy-agnostic **Self-Improving Trading Engine** that:
- Lets you plug in **any** type of indicator or strategy (Classical TA, Academic/Online Research Papers, Price Structure, or Orderflow) as reusable **Lego Blocks**.
- Simulates execution in **Paper Trading Mode first** (accounting for real slippage, spread, and fees) and logs rich diagnostic telemetry per trade—including **MAE (Maximum Adverse Excursion)**, **MFE (Maximum Favorable Excursion)**, and **Market Regime Snapshots**.
- Runs an automated **Evaluation Engine** to detect which specific market regimes cause drawdowns.
- Dispatches a **4-Agent AI Research Loop** (`Research` $\rightarrow$ `Hypothesis` $\rightarrow$ `Coding` $\rightarrow$ `Review`) to propose and code a candidate strategy upgrade (`V2`) without overwriting the baseline (`V1`).
- Enforces an independent **Deterministic Validation Gatekeeper** (In-Sample/OOS, Walk-Forward Analysis, Parameter Sensitivity Heatmap, and Cost Stress Test) before any candidate is promoted.
- Keeps **real-money trade execution 100% manual** via a live **1-Click Manual Order Ticket** and audio/Telegram alerts.

---

## 2. Core Functional Requirements (FR)

| ID | Requirement Area | Specification |
| :--- | :--- | :--- |
| **FR-01** | **Multi-Market Data Ingestion** | Must support 24/7 live Crypto Spot & USDT-M Perpetual streams (Binance/Bybit public WebSockets + historical REST backfill) in Phase 1, and modularly support NSE Intraday F&O equity feeds in Phase 2. |
| **FR-02** | **Lego-Block Indicator & Signal Separation** | Indicators (`indicators/`) must only output pure numeric series/levels across 4 families (Technical, Statistical/Paper, Structure, Orderflow). Signals (`signals/`) must convert indicators into reusable `True`/`False` conditions. |
| **FR-03** | **Versioned Strategy Registry** | Every strategy must carry an immutable `strategy_id` and version tag (e.g., `EMA_BREAKOUT_V1`, `EMA_BREAKOUT_V2`). New candidates must be saved in `strategies/candidates/` and never overwrite `strategies/approved/`. |
| **FR-04** | **Paper Simulator & MAE/MFE Tracking** | Must simulate fills with realistic slippage and commissions, tracking live open positions tick-by-tick to record exact `mae_pct`, `mae_r`, `mfe_pct`, and `mfe_r` for every closed trade. |
| **FR-05** | **Regime-Aware Evaluation Engine** | Must segment historical and paper trades by Volatility Regime (ATR percentile), Trend Regime, Volume/RVOL Tier, and Time-of-Day Session to output a structured JSON Weakness Report. |
| **FR-06** | **4-Agent Self-Improvement Loop** | Must coordinate 4 distinct AI roles (`Research`, `Hypothesis`, `Coding`, `Review`) to turn a Weakness Report into an executable candidate strategy file (`V2`) with zero look-ahead bias. |
| **FR-07** | **Independent Validation Gate** | Must never allow AI to self-approve a strategy. Every candidate must pass deterministic OOS, Walk-Forward, Parameter Sensitivity Heatmap, and Transaction Cost tests to be promoted. |
| **FR-08** | **100% Manual Real Execution Ticket** | Approved strategies running live must output a clear Manual Order Ticket (`Entry`, `Stop-Loss`, `Targets`, `Size`, `Net R:R`) with audio chime and optional Telegram notification—zero automated real-money broker orders. |

---

## 3. Strict Non-Goals (What We Will NOT Build)

1. **No Automated Real-Money Order Placement**: The system will never send live `BUY`/`SELL` execution API calls to a real-money brokerage account.
2. **No Mock or Hardcoded Demo Data in Production**: Every chart, metric, backtest, and trade log must come from real market feeds and the persistent SQLite database.
3. **No Heavy Infrastructure Bloat**: No Kubernetes, microservices, Redis clusters, or complex frontend frameworks (React/Next.js/Webpack). Use clean Python (`FastAPI` + `sqlite3`) and Vanilla JavaScript + TradingView Lightweight Charts.
4. **No Black-Box Neural Network Overfitting**: Self-improvement happens via transparent, inspectable rule/filter hypotheses validated by Walk-Forward and Parameter Sensitivity tests.

---

## 4. The 6-Phase Engineering Roadmap & Hard Stop Gates

Each phase must be completed, tested with `pytest`, and signed off by you (the Client) before moving to the next phase.

### Phase 1: Market Data Pipeline, Session Clock & SQLite Database Foundation
- **Allowed Files**: `config.py`, `requirements.txt`, `data/clock.py`, `data/feeds/binance_ws.py`, `memory/db.py`, `tests/test_phase1_data_db.py`.
- **Deliverables**:
  - SQLite WAL database initialization (`ohlcv_bars`, `trades_memory`, `strategy_registry`, `validation_reports`, `system_activity_log`).
  - Historical REST backfill + live 24/7 Binance WebSocket streamer for top Crypto Spot/Futures pairs (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, etc.).
  - Session clock handling UTC resets (`00:00 UTC`) and IST market windows (`09:15–15:30 IST`).
- **Definition of Done (Stop Gate)**: `pytest tests/test_phase1_data_db.py` passes; historical candles and live ticks write cleanly into SQLite.

### Phase 2: The 4-Family Lego Indicator & Signal Library
- **Allowed Files**: `data/feature_store.py`, `indicators/technical.py`, `indicators/statistical.py`, `indicators/structure.py`, `indicators/orderflow.py`, `signals/*.py`, `tests/test_phase2_indicators_signals.py`.
- **Deliverables**:
  - Family A (`technical.py`): EMA, SMA, RSI, ATR, Bollinger Bands, MACD, Supertrend, Fibonacci Pivots.
  - Family B (`statistical.py`): Rolling Z-Score, Volatility Percentile, Linear Regression Slope, Relative Strength (`RS`).
  - Family C (`structure.py`): `PDH`/`PDL`/`PDC`, Opening Range (`ORH`/`ORL`), 3-Touch Dynamic Trendlines (`TL`), Fair Value Gaps (`FVG`), Order Blocks (`OB`), Liquidity Sweeps.
  - Family D (`orderflow.py`): Intraday `VWAP`, Time-Normalized `RVOL`, Session Volume Profile (`POC`/`VAH`/`VAL`), `CVD`, Bid×Ask Footprint Imbalance (`300%`), Iceberg Detector.
  - Reusable boolean signal wrappers in `signals/`.
- **Definition of Done (Stop Gate)**: `pytest tests/test_phase2_indicators_signals.py` verifies all 4 indicator families and confirms zero look-ahead leakage.

### Phase 3: Strategy Builder (`V1`), Risk Manager & Paper Execution Simulator
- **Allowed Files**: `strategies/base_strategy.py`, `strategies/approved/ema_breakout_v1.py`, `strategies/approved/vwap_fvg_v1.py`, `risk/risk_manager.py`, `execution/paper_simulator.py`, `memory/trade_logger.py`, `tests/test_phase3_execution_memory.py`.
- **Deliverables**:
  - Standard `BaseStrategy` class + two initial baseline strategies (`EMA_BREAKOUT_V1` and `VWAP_FVG_V1`).
  - Universal `RiskManager` (position sizing, ATR stop-loss buffer, slippage pad, 2-consecutive-loss daily circuit breaker).
  - `PaperSimulator` tracking tick-by-tick open trade excursions (`MAE` and `MFE`), deducting realistic slippage and commissions, and writing closed trades + regime snapshots to `trades_memory`.
- **Definition of Done (Stop Gate)**: `pytest tests/test_phase3_execution_memory.py` verifies full paper trade lifecycle and exact `MAE`/`MFE` logging in SQLite.

### Phase 4: Vectorized/Event Backtester, Evaluation Engine & Validation Gatekeeper
- **Allowed Files**: `validation/backtester.py`, `evaluation/analyzer.py`, `validation/gatekeeper.py`, `tests/test_phase4_eval_validation.py`.
- **Deliverables**:
  - Historical backtest runner generating trade logs in `trades_memory`.
  - `EvaluationEngine` computing Performance, Risk ($\text{VaR}/\text{CVaR}$, Drawdown), and Regime Breakdown to automatically output structured Weakness Detection JSON reports.
  - `ValidationGatekeeper` executing the 4 independent tests: In-Sample/OOS Split (`70/30`), Rolling Walk-Forward Analysis, $5\times 5$ Parameter Sensitivity Heatmap, and $1.5\times$ Cost Stress Test, outputting `APPROVED` or `REJECTED`.
- **Definition of Done (Stop Gate)**: `pytest tests/test_phase4_eval_validation.py` confirms accurate weakness detection and gatekeeper approval/rejection logic.

### Phase 5: The 4-Role AI Self-Improvement Research Loop
- **Allowed Files**: `agents/research_loop.py`, `tests/test_phase5_research_agents.py`.
- **Deliverables**:
  - `ResearchAgent` $\rightarrow$ `HypothesisAgent` $\rightarrow$ `CodingAgent` $\rightarrow$ `ReviewAgent` pipeline using Gemini / OpenRouter.
  - Reads a Weakness Report for `V1`, generates a new candidate strategy file (`V2`) in `strategies/candidates/`, audits it for look-ahead bias, runs it through `ValidationGatekeeper`, and either promotes `V2` or rejects it while keeping `V1` safe.
- **Definition of Done (Stop Gate)**: `pytest tests/test_phase5_research_agents.py` verifies end-to-end candidate generation, code review, and validation gating.

### Phase 6: FastAPI Server & Unified Dark-Mode Web Terminal UI
- **Allowed Files**: `backend/server.py`, `execution/alert_dispatcher.py`, `frontend/index.html`, `frontend/css/styles.css`, `frontend/js/*.js`.
- **Deliverables**:
  - FastAPI REST + WebSocket server serving the frontend at `http://127.0.0.1:8765`.
  - Dark-mode terminal with TradingView Lightweight Charts (unlimited indicator overlays), Footprint Ladder panel, Paper Trade & 1-Click Manual Order Ticket, V1 vs. V2 Equity Comparison, Parameter Sensitivity Heatmap, Walk-Forward chart, and Live System Activity Monitor.
- **Definition of Done (Stop Gate)**: Full end-to-end launch verification in the browser with zero console errors.
