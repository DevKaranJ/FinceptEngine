"""config.py — Market sessions, fee/slippage schedules, risk constants.

Single source of truth for all engine-wide constants. No look-ahead data lives here.
All timestamps are UTC unless explicitly marked IST.
"""

from __future__ import annotations

from datetime import time, timedelta, timezone
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------
UTC = timezone.utc
IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Market sessions (PRD FR-01 / master_architecture Section 2)
# ---------------------------------------------------------------------------
# Crypto: 24/7 continuous, daily session resets at 00:00 UTC
CRYPTO_SESSION_UTC_START = time(0, 0, 0, tzinfo=UTC)
CRYPTO_SESSION_UTC_END = time(23, 59, 59, tzinfo=UTC)
CRYPTO_TRADEABLE_PAIRS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")

# NSE Equities (Phase 2): 09:15–15:30 IST, Monday–Friday
NSE_SESSION_IST_START = time(9, 15, 0)  # naive IST
NSE_SESSION_IST_END = time(15, 30, 0)   # naive IST
NSE_SESSION_IST_WINDOW = (
    timedelta(hours=9, minutes=15),
    timedelta(hours=15, minutes=30),
)
NSE_TRADING_DAYS = (0, 1, 2, 3, 4)  # Mon–Fri

# Binance public WebSocket & REST endpoints
BINANCE_WS_BASE_URL = "wss://stream.binance.com:9443/ws"
BINANCE_REST_BASE_URL = "https://api.binance.com/api/v3"
BINANCE_KLINE_INTERVALS = ("1m", "5m", "15m", "1h", "1d")

# ---------------------------------------------------------------------------
# Fee & slippage schedules (execution realism)
# ---------------------------------------------------------------------------
# Binance Spot maker/taker (basis points) — updated from public fee schedule
BINANCE_SPOT_MAKER_BP = 1.0   # 0.01%
BINANCE_SPOT_TAKER_BP = 1.0   # 0.01%
BINANCE_PERP_MAKER_BP = 2.0   # 0.02%
BINANCE_PERP_TAKER_BP = 4.0   # 0.04%

# Default slippage pad added per leg (basis points) for paper simulation
DEFAULT_SLIPPAGE_BP = 1.0   # 0.01%

# ---------------------------------------------------------------------------
# Risk constants (used by risk/risk_manager.py)
# ---------------------------------------------------------------------------
MAX_RISK_PER_TRADE_PCT = 1.0       # max 1% of account equity risked per trade
DAILY_LOSS_CIRCUIT_BREAKER_PCT = 3.0  # halt trading after 3% daily loss
MAX_CONSECUTIVE_LOSSES = 2         # 2-consecutive-loss daily circuit breaker
ATR_STOP_BUFFER_MULTIPLIER = 1.5   # ATR-based stop-loss buffer
MIN_RISK_REWARD_RATIO = 1.5        # minimum R:R before a trade is taken

# ---------------------------------------------------------------------------
# SQLite database (memory/db.py)
# ---------------------------------------------------------------------------
DB_PATH = "trading_engine.db"
DB_WAL_MODE = "PRAGMA journal_mode=WAL;"
DB_BUSY_TIMEOUT_MS = 5000

# ---------------------------------------------------------------------------
# Feature / look-ahead guard
# ---------------------------------------------------------------------------
# Indicators/transforms must only use t <= T. This constant is referenced by
# zero-look-ahead validation in Phase 2+ but declared here for central control.
ZERO_LOOK_AHEAD = True
