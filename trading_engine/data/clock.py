"""data/clock.py — Session manager for UTC (Crypto 24/7) & IST (NSE) market windows.

Responsibilities (PRD Phase 1 / master_architecture Section 2):
  • Determine whether a given UTC timestamp falls inside an active market session.
  • Compute the next session reset / open boundary for alignment of bar boundaries.
  • Enforce session time filters and IST square-off cutoffs.

All timestamps are UTC unless explicitly marked IST.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..config import (
    CRYPTO_SESSION_UTC_END,
    CRYPTO_SESSION_UTC_START,
    IST,
    NSE_SESSION_IST_END,
    NSE_SESSION_IST_START,
    NSE_TRADING_DAYS,
)

UTC = timezone.utc


class MarketSession:
    """Tracks active market sessions and session boundaries."""

    def __init__(self) -> None:
        self.crypto_start_utc = CRYPTO_SESSION_UTC_START
        self.crypto_end_utc = CRYPTO_SESSION_UTC_END
        self.nse_start_ist = NSE_SESSION_IST_START
        self.nse_end_ist = NSE_SESSION_IST_END
        self.nse_trading_days = NSE_TRADING_DAYS

    # ------------------------------------------------------------------ #
    # Crypto (24/7) helpers
    # ------------------------------------------------------------------ #
    def is_crypto_session_open(self, ts_utc: datetime) -> bool:
        """Crypto trades 24/7 — always open. Returns True for any valid UTC ts."""
        return True

    def crypto_session_reset_utc(self, ts_utc: datetime) -> datetime:
        """Next 00:00 UTC daily reset boundary on/after `ts_utc`."""
        ts_utc = self._ensure_utc(ts_utc)
        reset = ts_utc.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC)
        if reset < ts_utc:
            reset += timedelta(days=1)
        return reset

    # ------------------------------------------------------------------ #
    # NSE (IST) helpers
    # ------------------------------------------------------------------ #
    def is_nse_session_open(self, ts_utc: datetime) -> bool:
        """True if `ts_utc` falls within 09:15–15:30 IST on a Mon–Fri."""
        ts_ist = ts_utc.astimezone(IST)
        if ts_ist.weekday() not in self.nse_trading_days:
            return False
        t = ts_ist.time()
        return self.nse_start_ist <= t <= self.nse_end_ist

    def nse_next_session_open_utc(self, ts_utc: datetime) -> datetime:
        """Next NSE open (09:15 IST Mon–Fri) on/after `ts_utc`."""
        ts_utc = self._ensure_utc(ts_utc)
        candidate = ts_utc.astimezone(IST).replace(
            hour=self.nse_start_ist.hour,
            minute=self.nse_start_ist.minute,
            second=0,
            microsecond=0,
        )
        # If candidate is before/equal now, roll forward day by day until a trading day.
        if candidate <= ts_utc.astimezone(IST):
            candidate += timedelta(days=1)
        while candidate.weekday() not in self.nse_trading_days:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC)

    def nse_square_off_utc(self, ts_utc: datetime) -> datetime:
        """NSE square-off boundary (15:30 IST) for the current trading day."""
        ts_utc = self._ensure_utc(ts_utc)
        soff = ts_utc.astimezone(IST).replace(
            hour=self.nse_end_ist.hour,
            minute=self.nse_end_ist.minute,
            second=0,
            microsecond=0,
        )
        return soff.astimezone(UTC)

    # ------------------------------------------------------------------ #
    # Bar alignment
    # ------------------------------------------------------------------ #
    @staticmethod
    def align_bar_open_utc(ts_utc: datetime, timeframe: str) -> datetime:
        """Floor a UTC timestamp to the start of its `timeframe` bar.

        Supported timeframes: 1m, 5m, 15m, 1h, 1d (per config.BINANCE_KLINE_INTERVALS).
        """
        ts_utc = MarketSession._ensure_utc(ts_utc)
        minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}[timeframe]
        minute_of_day = ts_utc.hour * 60 + ts_utc.minute
        floored_minute = (minute_of_day // minutes) * minutes
        return ts_utc.replace(
            hour=floored_minute // 60,
            minute=floored_minute % 60,
            second=0,
            microsecond=0,
            tzinfo=UTC,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ensure_utc(ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)


def now_utc() -> datetime:
    """Current wall-clock time in UTC."""
    return datetime.now(UTC)


def iso_now_utc() -> str:
    """Current UTC time as ISO-8601 with Z suffix (used for DB timestamps)."""
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_utc(ts: datetime) -> str:
    """Format an aware datetime as ISO-8601 UTC with Z suffix."""
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "MarketSession",
    "now_utc",
    "iso_now_utc",
    "iso_utc",
    "UTC",
    "IST",
]
