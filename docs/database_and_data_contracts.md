# Database Schema, Data Contracts & API Specification

**Project Name:** Self-Improving Multi-Paradigm Quantitative Trading Engine  
**Database Engine:** SQLite 3 (`trading_engine.db` with `PRAGMA journal_mode=WAL;`)  

---

## 1. SQLite Database Schema (`memory/db.py`)

All persistent state is stored in `trading_engine.db` using Write-Ahead Logging (`WAL`) so concurrent live WebSocket writes and backtest/evaluation reads never block each other.

### Table 1: `ohlcv_bars` (Historical & Live Candle Store)
Stores multi-timeframe candlestick data across Crypto and Equities.
```sql
CREATE TABLE IF NOT EXISTS ohlcv_bars (
    symbol          TEXT NOT NULL,
    market_type     TEXT NOT NULL, -- 'CRYPTO_SPOT', 'CRYPTO_PERP', 'NSE_EQUITY'
    timeframe       TEXT NOT NULL, -- '1m', '5m', '15m', '1h', '1d'
    open_time_utc   TEXT NOT NULL, -- ISO-8601 UTC timestamp
    open            REAL NOT NULL,
    high            REAL NOT NULL,
    low             REAL NOT NULL,
    close           REAL NOT NULL,
    volume          REAL NOT NULL,
    quote_volume    REAL DEFAULT 0.0,
    taker_buy_vol   REAL DEFAULT 0.0, -- Used for true Bid x Ask delta calculation
    trade_count     INTEGER DEFAULT 0,
    PRIMARY KEY (symbol, timeframe, open_time_utc)
);
```

### Table 2: `trades_memory` (The Data & Trade Memory Engine)
Stores every backtest trade, live paper trade, and manual live trade along with `MAE`, `MFE`, and market regime snapshots.
```sql
CREATE TABLE IF NOT EXISTS trades_memory (
    trade_id                TEXT PRIMARY KEY,
    strategy_id             TEXT NOT NULL, -- e.g., 'EMA_BREAKOUT_V1'
    execution_mode          TEXT NOT NULL, -- 'BACKTEST', 'PAPER_LIVE', 'MANUAL_LIVE'
    symbol                  TEXT NOT NULL,
    timeframe               TEXT NOT NULL,
    direction               TEXT NOT NULL, -- 'LONG' or 'SHORT'
    status                  TEXT NOT NULL, -- 'OPEN', 'CLOSED', 'CANCELLED'
    entry_time_utc          TEXT NOT NULL,
    exit_time_utc           TEXT,
    entry_price             REAL NOT NULL,
    exit_price              REAL,
    stop_loss               REAL NOT NULL,
    target_1_price          REAL NOT NULL,
    target_2_price          REAL,
    position_size           REAL NOT NULL,
    slippage_cost           REAL DEFAULT 0.0,
    commission_cost         REAL DEFAULT 0.0,
    gross_pnl               REAL DEFAULT 0.0,
    net_pnl                 REAL DEFAULT 0.0,
    r_multiple              REAL DEFAULT 0.0,
    mae_pct                 REAL DEFAULT 0.0, -- Max Adverse Excursion (%)
    mae_r                   REAL DEFAULT 0.0, -- Max Adverse Excursion (R units)
    mfe_pct                 REAL DEFAULT 0.0, -- Max Favorable Excursion (%)
    mfe_r                   REAL DEFAULT 0.0, -- Max Favorable Excursion (R units)
    exit_reason             TEXT,             -- 'TAKE_PROFIT', 'STOP_LOSS', 'TRAIL_SL', 'TIME_EXIT', 'MANUAL'
    regime_snapshot_json    TEXT NOT NULL,    -- JSON of ATR percentile, Trend, RVOL, Funding, Session
    active_signals_json     TEXT NOT NULL,    -- JSON list of boolean signals active at entry
    notes                   TEXT
);
```

### Table 3: `strategy_registry` (Model & Strategy Version Control)
Tracks baseline strategies (`V1`) and AI-generated candidate upgrades (`V2`, `V3`).
```sql
CREATE TABLE IF NOT EXISTS strategy_registry (
    strategy_id         TEXT PRIMARY KEY, -- e.g., 'EMA_BREAKOUT_V2'
    parent_strategy_id  TEXT,             -- e.g., 'EMA_BREAKOUT_V1'
    file_path           TEXT NOT NULL,
    status              TEXT NOT NULL,    -- 'CANDIDATE', 'APPROVED_PAPER', 'REJECTED', 'ARCHIVED'
    paradigm_tags_json  TEXT NOT NULL,    -- e.g., '["TECHNICAL", "VOLATILITY_FILTER"]'
    parameters_json     TEXT NOT NULL,    -- Default tunable parameters for sensitivity testing
    hypothesis_summary  TEXT,             -- Why this version was created
    created_at_utc      TEXT NOT NULL,
    promoted_at_utc     TEXT
);
```

### Table 4: `validation_reports` (Independent Gatekeeper Results)
Stores the full scorecard comparing Candidate `V2` against Baseline `V1`.
```sql
CREATE TABLE IF NOT EXISTS validation_reports (
    report_id                   TEXT PRIMARY KEY,
    candidate_strategy_id       TEXT NOT NULL,
    baseline_strategy_id        TEXT NOT NULL,
    symbol                      TEXT NOT NULL,
    timeframe                   TEXT NOT NULL,
    in_sample_metrics_json      TEXT NOT NULL,
    out_of_sample_metrics_json  TEXT NOT NULL,
    walk_forward_summary_json   TEXT NOT NULL,
    parameter_heatmap_json      TEXT NOT NULL,
    cost_stress_metrics_json    TEXT NOT NULL,
    oos_passed                  INTEGER NOT NULL, -- 1 = PASS, 0 = FAIL
    walk_forward_passed         INTEGER NOT NULL,
    param_stability_passed      INTEGER NOT NULL,
    cost_stress_passed          INTEGER NOT NULL,
    final_status                TEXT NOT NULL,    -- 'APPROVED' or 'REJECTED'
    rejection_reason            TEXT,
    evaluated_at_utc            TEXT NOT NULL
);
```

### Table 5: `system_activity_log` (Live Engine & Agent Audit Trail)
Powers the `RECENT ACTIVITY` timeline in the dashboard (`Data synced`, `Backtest completed`, `Weakness detected`, `V2 generated`, `Validation passed/failed`).
```sql
CREATE TABLE IF NOT EXISTS system_activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc   TEXT NOT NULL,
    component       TEXT NOT NULL, -- 'DATA_FEED', 'STRATEGY_ENGINE', 'EVALUATION', 'RESEARCH_AGENT', 'GATEKEEPER'
    event_type      TEXT NOT NULL,
    summary         TEXT NOT NULL,
    details_json    TEXT
);
```

---

## 2. Internal Python Data Contracts (JSON Schemas)

To ensure that modules built by different AI agents never clash, all layers communicate using these strict dictionary schemas:

### Contract A: Strategy Signal Output (`strategies/base_strategy.py`)
Every strategy's `evaluate()` method must return either `None` (no trade) or this exact dictionary:
```json
{
  "strategy_id": "EMA_BREAKOUT_V1",
  "symbol": "BTCUSDT",
  "timeframe": "5m",
  "timestamp_utc": "2026-11-08T12:05:00Z",
  "direction": "LONG",
  "entry_price": 68420.50,
  "stop_loss_raw": 68180.00,
  "target_1_raw": 68910.00,
  "target_2_raw": 69350.00,
  "active_signals": ["EMA_20_50_BULL_CROSS", "ABOVE_VWAP"],
  "regime_snapshot": {
    "volatility_regime": "LOW_VOLATILITY",
    "atr_percentile": 18.4,
    "trend_regime": "BULLISH",
    "rvol": 1.42,
    "session_bucket": "LONDON_OPEN"
  }
}
```

### Contract B: Evaluation Engine Weakness Report (`evaluation/analyzer.py`)
Passed from the Evaluation Engine to the AI Research Agent:
```json
{
  "strategy_id": "EMA_BREAKOUT_V1",
  "symbol": "BTCUSDT",
  "timeframe": "5m",
  "overall_metrics": {
    "total_trades": 240,
    "win_rate_pct": 52.4,
    "profit_factor": 1.32,
    "expectancy_r": 0.18,
    "max_drawdown_pct": 13.6,
    "sharpe_ratio": 1.08
  },
  "weaknesses_detected": [
    {
      "regime_dimension": "volatility_regime",
      "regime_value": "LOW_VOLATILITY",
      "trade_count": 68,
      "win_rate_pct": 31.2,
      "profit_factor": 0.64,
      "avg_mae_r": -0.92,
      "avg_mfe_r": 0.45,
      "issue_summary": "Breakout signals in low-ATR compression suffer high false-breakout rate and increase max drawdown by +4.8%.",
      "suggested_action": "Test adding an ATR volatility expansion filter or minimum RVOL threshold."
    }
  ]
}
```

---

## 3. FastAPI REST & WebSocket Endpoints (`backend/server.py`)

| Method & Route | Purpose |
| :--- | :--- |
| `WS /ws/live` | Streams real-time candle updates, footprint ladders, active paper positions, system status badges, and manual order tickets to the UI. |
| `GET /api/system/status` | Returns engine status (`RUNNING`/`IDLE`), connected feeds, total strategies tested, approved count, uptime, and the `RECENT ACTIVITY` timeline. |
| `GET /api/market/Snapshot` | Returns historical OHLCV + computed multi-paradigm indicator overlays (`EMA`, `VWAP`, `POC`, `PDH`/`PDL`, `FVG`, `TL`) for the active symbol/timeframe. |
| `GET /api/trades/memory` | Returns paginated trade logs from `trades_memory` with `MAE`, `MFE`, fees, and regime snapshots. |
| `POST /api/trades/manual` | Logs a human-executed trade from the 1-Click Manual Order Ticket into `trades_memory`. |
| `GET /api/evaluation/{strategy_id}` | Runs `EvaluationEngine` on a strategy and returns Performance, Risk, Regime Breakdown, and detected weaknesses. |
| `POST /api/research/trigger` | Triggers the 4-Agent AI Research Loop (`Research` $\rightarrow$ `Hypothesis` $\rightarrow$ `Coding` $\rightarrow$ `Review` $\rightarrow$ `Validation Gate`) for a target strategy. |
| `GET /api/validation/reports` | Returns the V1 vs. V2 comparison scorecard, Walk-Forward curves, and Parameter Sensitivity Heatmap JSON for the UI. |
