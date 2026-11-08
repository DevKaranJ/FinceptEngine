# MASTER ARCHITECTURE: Self-Improving Multi-Paradigm Quantitative Trading Engine

**Subtitle:** A Modular, Strategy-Agnostic System That Researches, Tests, Validates, and Improves Strategies Across Technical Analysis, Quantitative Research Papers, Price Action, and Orderflow.

---

## 1. Executive Architecture Overview & Core Philosophy

This master specification defines a **100% Strategy-Agnostic Self-Improving Trading Engine**. It does **not** revolve around a single trading style: whether a strategy is built from classical indicators (EMA, RSI, ATR, Bollinger Bands), academic research papers (statistical mean-reversion, volatility breakouts), price structure (Trendlines, Pivots, FVG), or orderflow (VWAP, Volume Profile, Footprint), every indicator and signal is treated as an interchangeable **Lego Block**.

### Core Design Principles
1. **Strategy-Agnostic Lego-Block Decoupling (`Indicators` $\rightarrow$ `Signals` $\rightarrow$ `Strategies` $\rightarrow$ `Risk`)**:
   - **Indicators** compute pure math across any paradigm (Technical, Statistical, Structural, or Orderflow).
   - **Signals** convert indicator outputs into reusable `True`/`False` triggers and filters.
   - **Strategies** combine any trigger and filters into versioned recipes (`V1`, `V2`, `V3`).
   - **Risk** enforces universal position sizing, stop-loss rules, and daily circuit breakers.
2. **Paper Trade First & 100% Manual Real Execution**:
   - Candidate strategies (`V1`, `V2`, `V3`) are tested in historical backtests, verified in live **Paper Execution Mode**, and—once promoted—power the **Live Manual Order Ticket** so the human trader always executes real broker orders manually.
3. **Never Let AI Approve Its Own Strategy**:
   - The AI Research Agents can propose and code new candidate versions (`V2`) from any indicator family, but **promotion is strictly gated by an independent mathematical Validation Engine** (Out-of-Sample, Walk-Forward, Parameter Sensitivity Heatmap, and Slippage/Commission stress tests). If `V2` fails any check, it is rejected and `V1` remains the active baseline.

```
+-----------------------------------------------------------------------------------+
|                        THE COMPLETE SELF-IMPROVING ENGINE FLOW                    |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [1. MARKET DATA & FEATURE STORE] (Live + Historical OHLCV, Ticks, On-Chain/News) |
|                 |                                                                 |
|                 v                                                                 |
|  [2. MULTI-PARADIGM LEGO STRATEGY ENGINE]                                         |
|      (Technical TA | Quant/Stat Papers | Price Structure | Orderflow + Risk)      |
|                 |                                                                 |
|                 v                                                                 |
|  [3. TRADE MEMORY & PAPER SIMULATOR] (Logs Entry, Exit, Slippage, Fee, MAE, MFE)  |
|                 |                                                                 |
|                 v                                                                 |
|  [4. EVALUATION ENGINE] (Performance, Risk/VaR, Regime Breakdown, Failure Root)   |
|                 |                                                                 |
|                 v                                                                 |
|  [5. AI RESEARCH AGENTS] (Research -> Hypothesis -> Coding V2 -> Code Review)     |
|                 |                                                                 |
|                 v                                                                 |
|  [6. DETERMINISTIC VALIDATION GATE] (In-Sample -> OOS -> Walk-Forward -> Heatmap) |
|         |                                               |                         |
|    (PASS: Promote V2)                              (FAIL: Reject V2)              |
|         |                                               |                         |
|         v                                               +---> Keep V1 Active &    |
|  [7. PAPER DEPLOYMENT & LIVE MANUAL ORDER TICKET]             Loop Back to Step 5 |
+-----------------------------------------------------------------------------------+
```

---

## 2. Layer-by-Layer System Specification

### Layer 1: Market Data, Clock & Multi-Paradigm Feature Store (`data/` & `indicators/`)
Ingests live streaming market data and historical archives, normalizes timestamps across market sessions, and computes features across **four independent indicator families** so you can build any type of strategy.

| Sub-Module | Responsibilities & Data Streams | Supported Markets & Libraries |
| :--- | :--- | :--- |
| **Data Sources (`data/feeds/`)** | • **Live Streams**: 1m/5m/15m/1h/1d OHLCV klines, tick/aggTrade streams, Order Book Depth, Perpetual Funding Rates, Open Interest.<br>• **Historical Backfill**: REST API & CSV downloader for multi-year OHLCV and tick history.<br>• **Optional Alternative Data**: News/Events sentiment, macro calendar, and on-chain metrics. | • **Phase 1 Focus (Crypto 24/7)**: Binance & Bybit Public WebSockets & REST APIs ($0 cost, top 15–25 liquid pairs).<br>• **Phase 2 Expansion (India NSE)**: Dhan / Fyers / Angel One read-only feeds (top 150 F&O intraday stocks). |
| **Clock & Session Manager (`data/clock.py`)** | • Manages market session resets (`00:00 UTC` for Crypto 24/7; `09:15–15:30 IST` for NSE Intraday).<br>• Enforces session time filters and square-off cutoffs. | Python `zoneinfo` / `datetime` UTC & IST synchronization. |
| **Family A: Classical Technical Indicators (`indicators/technical.py`)** | • Standard trend, momentum, and volatility indicators: EMA, SMA, RSI, MACD, ATR, Bollinger Bands, Supertrend, ADX, Stochastic, Donchian Channels, Daily Fibonacci & Classic Pivots. | `pandas-ta`, `numpy`, `pandas`. |
| **Family B: Quantitative & Research-Paper Models (`indicators/statistical.py`)** | • Mathematical & statistical features from academic/online papers: Rolling Z-Score, Hurst Exponent, Linear Regression Slope, Realized Volatility Percentile, Autocorrelation, Keltner Squeeze, and Cross-Asset Relative Strength (`RS`). | `numpy`, `scipy.stats`, `pandas`. |
| **Family C: Price Action & Market Structure (`indicators/structure.py`)** | • Geometric and structural price levels: Prior Day High/Low/Close (`PDH`, `PDL`, `PDC`), Opening Range (`ORH`, `ORL`), 3-Touch Dynamic Trendlines (`TL`), Fair Value Gaps (`FVG`), Order Blocks (`OB`), and Liquidity Sweeps. | Custom vectorized `numpy`/`pandas` modules. |
| **Family D: Volume & Orderflow (`indicators/orderflow.py`)** | • Optional volume and microstructure features: Intraday `VWAP` (+ standard deviation bands), Time-Normalized `RVOL`, Session Volume Profile (`POC`, `VAH`, `VAL`), Cumulative Volume Delta (`CVD`), Bid×Ask Footprint Imbalances, and Iceberg Detection. | Custom vectorized `numpy`/`pandas` modules. |
| **Feature Store (`data/feature_store.py`)** | • Caches and aligns computed indicator series across multiple timeframes (`1m`, `5m`, `15m`, `1h`, `1d`) in SQLite / Parquet so Backtesting, Paper Trading, and Evaluation read identical features with zero look-ahead bias. | `sqlite3` (WAL mode) + `pyarrow`/Parquet. |

---

### Layer 2: Modular Strategy Engine & Paper Execution Simulator (`signals/`, `strategies/`, `risk/`, `execution/`)
Allows you (or the AI Research Agents) to build pure TA strategies, pure Quant/Paper strategies, pure Orderflow strategies, or hybrid combinations using the exact same pipeline.

| Sub-Module | Role in the Pipeline | Examples Across Different Strategy Styles |
| :--- | :--- | :--- |
| **Reusable Signal Conditions (`signals/`)** | Converts raw indicator numbers from any of the 4 families into atomic `True`/`False` building blocks. | • **TA Signals**: `ema_fast_cross_above`, `rsi_oversold_30`, `atr_above_threshold`<br>• **Quant/Stat Signals**: `zscore_below_minus_2`, `hurst_trending_regime`<br>• **Structure Signals**: `orb_breakout_up`, `tl_third_touch_bounce`, `fvg_retest`<br>• **Orderflow Signals**: `above_vwap`, `at_session_poc`, `rvol_above_2x`, `footprint_imbalance` |
| **Versioned Strategy Builder (`strategies/`)** | Combines any 1 Trigger + 1–4 Filter Signals into a versioned strategy class (`EMA_BREAKOUT_V1`, `VWAP_MEAN_REV_V1`, `ORDERFLOW_FVG_V1`). | Supports both active baseline strategies (`strategies/approved/`) and AI-generated candidate strategies (`strategies/candidates/`). |
| **Universal Risk Manager (`risk/`)** | Enforces non-negotiable capital and risk rules across all strategies regardless of indicator type. | • Position sizing based on account equity & max risk `%` per trade.<br>• ATR-based or structural stop-loss placement.<br>• Partial profit-taking & trailing stop rules.<br>• Daily loss circuit breaker & Max Drawdown kill-switch. |
| **Execution Simulator & Paper Engine (`execution/paper_simulator.py`)** | Simulates realistic market fills on live streams and historical backtests (**Paper Trade First**). | • Deducts realistic **Slippage**, **Exchange Commissions**, and **Funding/Spread** costs.<br>• Tracks live open paper positions tick-by-tick and populates the **1-Click Manual Order Ticket** for approved strategies. |

---

### Layer 3: The Data & Trade Memory Engine (`memory/trade_logger.py`)
Turns every historical backtest trade, live paper trade, and manual trade into structured learning data stored permanently in SQLite (`trading_engine.db`).

#### What We Store Per Trade (`trades_memory` Table)
Beyond basic entry/exit prices, the engine records **why** the trade was taken, **how** the market regime looked at entry, and **how price behaved during the trade** using **MAE (Maximum Adverse Excursion)** and **MFE (Maximum Favorable Excursion)**:

| Field | Example Value | Diagnostic Purpose for Self-Improvement |
| :--- | :--- | :--- |
| `trade_id` | `TRD_20261108_0042` | Unique primary key. |
| `strategy_id` | `EMA_BREAKOUT_V1` | Links performance to exact strategy version (`V1`, `V2`, etc.). |
| `execution_mode` | `BACKTEST` \| `PAPER_LIVE` \| `MANUAL_LIVE` | Separates backtest simulations from forward paper trading. |
| `symbol` & `timeframe` | `BTCUSDT` (`5m`) | Asset and primary execution timeframe. |
| `entry_time` & `exit_time` | `2026-11-08 09:15:00 UTC` | Detects time-of-day / session-bucket performance leaks. |
| `direction` | `LONG` \| `SHORT` | Evaluates directional bias separately. |
| `entry_price` & `exit_price` | `68420.50` / `68910.00` | Raw execution prices. |
| `stop_loss` & `target_price` | `68180.00` / `68910.00` | Initial planned risk (`1.0 R`) and reward levels. |
| `position_size` | `0.146` | Deployed size. |
| `slippage` & `commission` | `$3.42` / `$4.00` | Measures real execution friction drag. |
| `net_pnl` & `r_multiple` | `+$64.05` (`+1.96 R`) | Net profit after all fees and realized R-multiple. |
| **`mae_pct` / `mae_r`** | `-0.18%` (`-0.52 R`) | **Maximum Adverse Excursion**: Deepest drawdown experienced while the trade was open (identifies if stops are too tight or entries are premature). |
| **`mfe_pct` / `mfe_r`** | `+0.84%` (`+2.40 R`) | **Maximum Favorable Excursion**: Peak unrealized profit reached before exit (identifies if targets are leaving money on the table or giving back gains). |
| `exit_reason` | `TAKE_PROFIT` \| `STOP_LOSS` \| `TRAIL_SL` \| `TIME_EXIT` | Categorizes how trades terminate. |
| `regime_snapshot_json` | `{"volatility_regime": "LOW_ATR", "trend_regime": "RANGE", "rvol": 1.15, "rsi": 54.2}` | Captures the exact market environment at entry so the Evaluation Engine can find which regimes cause losses. |
| `active_signals_json` | `["EMA_FAST_CROSS", "ABOVE_VWAP"]` | Enables component-level attribution across individual Lego blocks. |

---

### Layer 4: The Evaluation Engine (`evaluation/analyzer.py`)
Analyzes trade logs from Layer 3 not merely to calculate returns, but to **automatically diagnose structural weaknesses and fragility** in any strategy (`V1`).

#### Three-Pillar Diagnostic Scorecard
1. **A. Performance Metrics**:
   - Net Return (after slippage & commissions), Win Rate (`%`), Profit Factor ($\frac{\text{Gross Profit}}{|\text{Gross Loss}|}$), Mathematical Expectancy in $R$ ($E = W \cdot \overline{R}_{\text{win}} - (1-W) \cdot \overline{R}_{\text{loss}}$), and annualized Sharpe / Sortino Ratio.
2. **B. Risk & Excursion Metrics**:
   - Maximum Drawdown (`%` and `$`), Longest Losing Streak, Exposure/Leverage utilization, Tail Risk ($\text{VaR}_{95\%}$ and $\text{CVaR}_{95\%}$), and **MAE/MFE Efficiency**.
3. **C. Robustness & Automated Weakness Detection**:
   - **Market Regime Segmentation**: Slices strategy performance across **Volatility Regimes** (Low, Normal, High ATR), **Trend Regimes** (Trending vs. Choppy/Range-bound), **Volume/RVOL Tiers**, and **Time-of-Day Sessions**.
   - **Automated Weakness Report Output**: Generates a structured JSON diagnosis whenever a sub-regime exhibits Profit Factor $< 1.0$ or elevated drawdown:
     ```json
     {
       "strategy_id": "EMA_BREAKOUT_V1",
       "weakness_detected": true,
       "problem_regime": "LOW_VOLATILITY (ATR_PCT < 25th Percentile)",
       "symptom": "Win rate drops from 56.8% to 31.4%; Max Drawdown spikes by +4.8%",
       "root_cause": "Breakout signals in low-ATR compression fail due to lack of follow-through (MFE < 0.6R)",
       "recommended_investigation": "Test adding an ATR volatility filter, Volume Profile POC filter, or RVOL gate"
     }
     ```

---

### Layer 5: The 4-Role AI Research Agent Loop (`agents/research_loop.py`)
Triggered on schedule or on demand, the 4 specialized AI agents convert the Evaluation Engine's weakness report into a testable candidate strategy (`V2`) by drawing from **any** of the 4 indicator families (`Technical`, `Statistical`, `Structural`, or `Orderflow`).

| Agent Role | Input Received | Action Taken | Output Produced |
| :--- | :--- | :--- | :--- |
| **1. Research Agent** | Evaluation Engine JSON + Trade Memory (`MAE`/`MFE` & Regime logs). | Investigates the exact losing trades in the flagged regime and isolates the root cause of failure. | Root-Cause Diagnostic Brief. |
| **2. Hypothesis Agent** | Root-Cause Diagnostic Brief + Full Catalog of `indicators/` and `signals/` (TA, Quant, Structure, Orderflow). | Formulates a concrete, testable improvement hypothesis (e.g., *"Add `atr_volatility_filter` to `EMA_BREAKOUT_V1`"* or *"Combine `Orderflow` with `Volume Profile POC`"*). | Structured Hypothesis Spec (`V1` $\rightarrow$ `V2` diff plan). |
| **3. Coding Agent** | Hypothesis Spec + `V1` source code. | Writes the new candidate strategy file `strategies/candidates/EMA_BREAKOUT_V2.py` without modifying `V1`. | Executable Python strategy candidate `V2`. |
| **4. Review Agent** | `V2` source code + System Risk Rules. | Audits the code for syntax safety, **zero look-ahead bias**, and strict compliance with `risk/` rules. | Approved Candidate `V2` ready for Layer 6 Validation. |

---

### Layer 6: Independent Validation & Robustness Gate (`validation/gatekeeper.py`)
**Rule: Never let AI approve its own strategy.** Every candidate strategy (`V2`) generated by the AI Research Agents—or written manually from an online research paper—must pass four independent, deterministic mathematical tests before it is allowed into Paper Execution:

| Validation Stage | What It Tests | Pass / Fail Promotion Criteria |
| :--- | :--- | :--- |
| **1. In-Sample vs. Out-of-Sample (OOS) Split** | Trains/tunes on the first $70\%$ of historical data and tests blindly on the unseen final $30\%$ Out-of-Sample window. | **PASS** if OOS Profit Factor $\ge 1.25$, OOS Expectancy $> 0.15R$, and OOS Win Rate degrades by no more than $15\%$ relative to In-Sample. |
| **2. Walk-Forward Analysis (WFA)** | Rolling anchored or sliding windows (e.g., Train $\rightarrow$ Validate) across the historical dataset. | **PASS** if at least $70\%$ of Walk-Forward windows are net profitable after fees and no single window breaches Max Drawdown limits. |
| **3. Parameter Sensitivity Heatmap** | Tests a $5 \times 5$ grid of neighboring parameter values (e.g., `ATR Multiplier 1.0–3.0` $\times$ `EMA Length 10–60`) to detect curve-fitting cliffs. | **PASS** if $\ge 80\%$ of neighboring parameter combinations remain profitable (smooth plateau, not an isolated lucky spike). |
| **4. Execution Realism Stress Test** | Re-runs the backtest with $1.5\times$ normal slippage and full taker commissions. | **PASS** if Net Profit Factor remains $> 1.15$ under stressed execution costs. |

#### The Promotion Decision (`Approve` vs. `Reject`)
- **If ANY test FAILS (`FINAL STATUS: REJECTED`)**:
  - `V2` is archived in the database with its failure scorecard.
  - **`V1` remains the active strategy untouched.**
  - The failure report (e.g., *"Parameter Stability: FAIL"*) is fed back to the Research Agent for the next iteration.
- **If ALL 4 tests PASS (`FINAL STATUS: APPROVED`)**:
  - `V2` is promoted to `strategies/approved/`, registered in the **Strategy & Model Registry**, and deployed to **Live Paper Execution** (and the Manual Order Ticket).

---

## 3. Unified Folder Structure of the Project

```text
trading_engine/
├── AGENTS.md                        # Multi-agent coding harness & phase stop-gate rules
├── config.py                        # Market sessions, fee/slippage schedules, risk constants
├── requirements.txt                 # FastAPI, uvicorn, pandas, numpy, pandas-ta, scipy, websockets, pytest
│
├── data/                            # LAYER 1: MARKET DATA & FEATURE STORE
│   ├── clock.py                     # Session manager (UTC 24/7 Crypto & IST NSE hours)
│   ├── feature_store.py             # SQLite + Parquet feature caching (zero look-ahead)
│   └── feeds/
│       ├── binance_ws.py            # Live 24/7 Crypto Spot & USDT-M Futures WebSocket + REST backfill
│       └── nse_broker_ws.py         # (Phase 2) NSE Intraday F&O WebSocket connector
│
├── indicators/                      # LAYER 1B: MULTI-PARADIGM PURE MATH LEGO BLOCKS
│   ├── technical.py                 # Family A: RSI, EMA, SMA, ATR, Bollinger, MACD, Supertrend, Pivots
│   ├── statistical.py               # Family B: Rolling Z-Score, Hurst, Volatility Percentile, Reg Slope, RS
│   ├── structure.py                 # Family C: PDH/PDL, ORB, Dynamic Trendlines (TL), FVG, Order Blocks
│   └── orderflow.py                 # Family D: VWAP, Volume Profile (POC/VAH/VAL), RVOL, CVD, Footprint
│
├── signals/                         # LAYER 2A: REUSABLE TRUE/FALSE TRIGGERS & FILTERS
│   ├── technical_signals.py         # ema_crossover, rsi_extremes, atr_volatility_gate, bb_squeeze
│   ├── statistical_signals.py       # zscore_reversion, hurst_trend_filter, rs_leader_filter
│   ├── structure_signals.py         # orb_breakout, tl_3rd_touch, fvg_retest, key_level_sweep
│   └── orderflow_signals.py         # above_vwap, at_poc_filter, footprint_300_imbalance, rvol_gate
│
├── strategies/                      # LAYER 2B: VERSIONED STRATEGY RECIPES (ANY PARADIGM)
│   ├── base_strategy.py             # Abstract interface enforcing standard signal + risk output
│   ├── approved/                    # Active validated strategies (e.g., ema_breakout_v1.py, vwap_fvg_v1.py)
│   └── candidates/                  # AI-generated or research-paper candidates awaiting validation (v2.py)
│
├── risk/                            # LAYER 2C: UNIVERSAL RISK & SIZING GOVERNANCE
│   └── risk_manager.py              # Position sizing, ATR stop buffer, slippage pad, daily circuit breaker
│
├── execution/                       # LAYER 2D & 6: PAPER SIMULATOR & MANUAL TICKET DISPATCHER
│   ├── paper_simulator.py           # Live paper trading fills, MAE/MFE real-time tracker, fee deduction
│   └── alert_dispatcher.py          # 1-Click Manual Order Ticket generator + Web Audio / Telegram alerts
│
├── memory/                          # LAYER 3: DATA & TRADE MEMORY ENGINE
│   ├── db.py                        # SQLite WAL-mode schema (trades_memory, strategy_registry, logs)
│   └── trade_logger.py              # Persists every trade with MAE, MFE, Regime & Signal snapshots
│
├── evaluation/                      # LAYER 4: EVALUATION & WEAKNESS DETECTION ENGINE
│   └── analyzer.py                  # Computes Return/Risk/Sharpe, MAE/MFE efficiency & Regime failures
│
├── agents/                          # LAYER 5: IN-APP AI SELF-IMPROVEMENT AGENTS
│   └── research_loop.py             # Research -> Hypothesis -> Coding -> Review pipeline (Gemini/OpenRouter)
│
├── validation/                      # LAYER 6: INDEPENDENT ROBUSTNESS & APPROVAL GATE
│   ├── backtester.py                # Fast vectorized & event-driven historical backtest engine
│   └── gatekeeper.py                # OOS split, Walk-Forward Analysis, Parameter Heatmap & Approve/Reject
│
├── backend/                         # FASTAPI SERVER & WEBSOCKET HUB
│   └── server.py                    # REST endpoints + real-time WebSocket stream to Frontend UI
│
├── frontend/                        # DARK-MODE INSTITUTIONAL TERMINAL UI
│   ├── index.html                   # Unified terminal layout shell
│   ├── css/styles.css               # Custom dark terminal styling
│   └── js/
│       ├── main.js                  # State & WebSocket orchestration
│       ├── chart_engine.js          # TradingView Lightweight Charts (unlimited TA/Structure/Orderflow layers)
│       ├── footprint_ui.js          # Optional Footprint & Order Book Depth inspection panel
│       ├── lab_evaluation_ui.js     # V1 vs V2 comparison charts, Parameter Heatmap & WFA viewer
│       └── system_monitor_ui.js     # System Status, Recent Activity log, Agent status & Paper PnL
│
└── tests/                           # DETERMINISTIC PYTEST VERIFICATION SUITE
    ├── test_indicators.py
    ├── test_signals_strategies.py
    └── test_validation_gate.py
```

---

## 4. Phased Implementation Roadmap (With Strict Stop Gates)

| Phase | Deliverable Scope | Hard Stop Verification Gate |
| :--- | :--- | :--- |
| **Phase 1: Core Data Feed, Clock & SQLite Trade Memory** | Build `config.py`, `data/clock.py`, `data/feeds/binance_ws.py`, and `memory/db.py` (`trades_memory` + `strategy_registry` tables). Stream live Crypto OHLCV + ticks and backfill historical bars. | `pytest` confirms live Binance WebSocket ingestion and SQLite WAL table creation. **STOP.** |
| **Phase 2: Multi-Paradigm Lego Indicators & Signals** | Build all 4 indicator families (`technical.py`, `statistical.py`, `structure.py`, `orderflow.py`) and corresponding reusable boolean conditions in `signals/`. | `pytest` verifies exact math across TA (RSI, EMA, ATR, Pivots), Quant/Stat, Structure (TL, FVG), and Orderflow (VWAP, POC, Footprint). **STOP.** |
| **Phase 3: Strategy Builder (`V1`), Risk Manager & Paper Simulator** | Build `strategies/base_strategy.py`, baseline strategies (e.g., `EMA_BREAKOUT_V1` and `VWAP_FVG_V1`), `risk/risk_manager.py`, and `execution/paper_simulator.py` (logging `MAE`, `MFE`, slippage, and regime snapshots). | `pytest` runs a simulated trade lifecycle and verifies `MAE`/`MFE` and net PnL are recorded accurately in `trades_memory`. **STOP.** |
| **Phase 4: Backtester, Evaluation Engine & Validation Gatekeeper** | Build `validation/backtester.py`, `evaluation/analyzer.py` (regime weakness detector), and `validation/gatekeeper.py` (OOS split, Walk-Forward, Parameter Sensitivity Heatmap, and Approve/Reject logic). | `pytest` runs `V1` through the backtester, outputs a Regime Weakness JSON, and runs the 4-stage Validation Gate. **STOP.** |
| **Phase 5: The 4 AI Research Agents (Self-Improvement Loop)** | Build `agents/research_loop.py` (`Research` $\rightarrow$ `Hypothesis` $\rightarrow$ `Coding V2` $\rightarrow$ `Review`) wired to `evaluation/analyzer.py` and `validation/gatekeeper.py`. | End-to-end test confirms the agents read a weakness report, generate `V2` in `strategies/candidates/`, and submit `V2` to the Validation Gate without touching `V1`. **STOP.** |
| **Phase 6: FastAPI Backend & Unified Dark-Mode Terminal UI** | Build `backend/server.py` and `frontend/` (TradingView Lightweight Charts + Strategy Lab V1 vs V2 comparison + Parameter Heatmap + System Status Monitor). | Browser opens `http://127.0.0.1:8765` displaying live charts, paper trades, and the Self-Improvement Lab tabs. **COMPLETE.** |
