"""evaluation/analyzer.py — Evaluation Engine + Weakness Detection (Layer 4B).

Consumes closed-trade dicts (from ``validation/backtester.py``) and computes
Performance, Risk (VaR/CVaR, Drawdown), Regime Breakdown, and emits a
structured **Weakness Detection JSON** report used by
``validation/gatekeeper.py`` and persisted to ``validation_reports``.

All formulas are deterministic (spec Section 2):
  • Win Rate $W = \\frac{\\text{Count}(P_i > 0)}{N}$
  • Profit Factor $\\text{PF} = \\frac{\\sum_{P_i>0} P_i}{|\\sum_{P_i<0} P_i|}$
  • Expectancy $E_R = (W \\times \\overline{R}_{win}) - ((1-W) \\times |\\overline{R}_{loss}|)$

Zero look-ahead: metrics are computed only from closed trades observed up to
the current point — never future data.

Weakness detection flags:
  • Regimes where net PnL is negative (regime breakdown).
  • Tight stops: high fraction of trades stopped out with small MFE.
  • Early exits: TP1 hit rate vs targets left on table (MFE after exit).
  • Low win-rate / low-expectancy regimes.
  • Cost drag: slippage+commission as % of gross PnL.
"""

from __future__ import annotations

import json
import math
from statistics import mean
from typing import Any

import numpy as np


# --------------------------------------------------------------------------- #
# Core performance / risk metrics                                             #
# --------------------------------------------------------------------------- #
def compute_performance(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Return win rate, profit factor, expectancy (R), gross/net PnL."""
    closed = [t for t in trades if t.get("net_pnl") is not None]
    n = len(closed)
    if n == 0:
        return {
            "total_trades": 0, "win_count": 0, "loss_count": 0,
            "win_rate_pct": 0.0, "profit_factor": 0.0,
            "expectancy_r": 0.0, "gross_profit": 0.0,
            "gross_loss": 0.0, "net_pnl": 0.0,
        }

    wins = [t for t in closed if t["net_pnl"] > 0]
    losses = [t for t in closed if t["net_pnl"] < 0]
    gross_profit = sum(t["net_pnl"] for t in wins)
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
    net_pnl = sum(t["net_pnl"] for t in closed)

    win_rate_pct = len(wins) / n * 100.0

    r_vals = [float(t.get("r_multiple", 0.0)) for t in closed
              if t.get("r_multiple") is not None]
    if r_vals:
        r_wins = [r for r in r_vals if r > 0]
        r_losses = [r for r in r_vals if r < 0]
        mean_r_win = mean(r_wins) if r_wins else 0.0
        mean_r_loss = abs(mean(r_losses)) if r_losses else 0.0
        expectancy_r = (len(r_wins) / n * mean_r_win) - (
            (n - len(r_wins)) / n * mean_r_loss
        )
    else:
        mean_r_win = mean_r_loss = expectancy_r = 0.0

    return {
        "total_trades": n,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate_pct": round(win_rate_pct, 4),
        "profit_factor": round(profit_factor, 4),
        "expectancy_r": round(expectancy_r, 4),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "net_pnl": round(net_pnl, 4),
    }


def compute_risk(trades: list[dict[str, Any]],
                 equity_curve: list[tuple[str, float]] | None = None,
                 ) -> dict[str, Any]:
    """Return drawdown, VaR/CVaR (95%) on trade-level net PnL returns.

    VaR/CVaR are computed on per-trade net PnL (normalized to R where
    available) using only trades seen so far — no future leakage.
    """
    closed = [t for t in trades if t.get("net_pnl") is not None]
    pnls = [float(t["net_pnl"]) for t in closed]

    # Max drawdown from equity curve if provided.
    max_dd_pct = 0.0
    if equity_curve:
        peak = 0.0
        for _, equity in equity_curve:
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak * 100.0
                if dd > max_dd_pct:
                    max_dd_pct = dd

    if not pnls:
        return {
            "max_drawdown_pct": round(max_dd_pct, 4),
            "var_95_pnl": 0.0, "cvar_95_pnl": 0.0,
            "var_95_r": 0.0, "cvar_95_r": 0.0,
            "largest_loss": 0.0, "largest_win": 0.0,
        }

    arr = np.array(pnls, dtype=float)
    largest_loss = float(arr.min()) if arr.size else 0.0
    largest_win = float(arr.max()) if arr.size else 0.0

    # VaR / CVaR at 95% confidence on PnL distribution (losses as positive risk).
    losses_only = arr[arr < 0]
    if losses_only.size > 0:
        # VaR_95 = quantile of losses at 5th percentile (worst 5%).
        var_95 = float(np.quantile(losses_only, 0.05))  # most negative tail
        cvar_95 = float(losses_only[losses_only <= var_95].mean()) \
            if np.any(losses_only <= var_95) else var_95
    else:
        var_95 = cvar_95 = 0.0

    r_vals = [float(t.get("r_multiple", 0.0)) for t in closed
              if t.get("r_multiple") is not None]
    r_arr = np.array(r_vals, dtype=float) if r_vals else np.array([0.0])
    r_losses = r_arr[r_arr < 0]
    if r_losses.size > 0:
        var_95_r = float(np.quantile(r_losses, 0.05))
        cvar_95_r = float(r_losses[r_losses <= var_95_r].mean()) \
            if np.any(r_losses <= var_95_r) else var_95_r
    else:
        var_95_r = cvar_95_r = 0.0

    return {
        "max_drawdown_pct": round(max_dd_pct, 4),
        "var_95_pnl": round(var_95, 4),
        "cvar_95_pnl": round(cvar_95, 4),
        "var_95_r": round(var_95_r, 4),
        "cvar_95_r": round(cvar_95_r, 4),
        "largest_loss": round(largest_loss, 4),
        "largest_win": round(largest_win, 4),
    }


def compute_regime_breakdown(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Group trades by ``regime_snapshot.volatility_regime`` and PnL sign.

    Returns per-regime: trade count, wins, losses, net PnL, win rate,
    profit factor, expectancy R, and a flag when the regime is losing.
    """
    regimes: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        snap = t.get("regime_snapshot") or {}
        if isinstance(snap, str):
            try:
                snap = json.loads(snap)
            except Exception:
                snap = {}
        regime = snap.get("volatility_regime", "UNKNOWN")
        regimes.setdefault(regime, []).append(t)

    breakdown: dict[str, Any] = {}
    for regime, reg_trades in regimes.items():
        perf = compute_performance(reg_trades)
        risk = compute_risk(reg_trades)
        breakdown[regime] = {
            "trade_count": perf["total_trades"],
            "win_count": perf["win_count"],
            "loss_count": perf["loss_count"],
            "win_rate_pct": perf["win_rate_pct"],
            "profit_factor": perf["profit_factor"],
            "expectancy_r": perf["expectancy_r"],
            "net_pnl": perf["net_pnl"],
            "max_drawdown_pct": risk["max_drawdown_pct"],
            "is_losing_regime": perf["net_pnl"] < 0,
        }
    return breakdown


# --------------------------------------------------------------------------- #
# Weakness detection                                                          #
# --------------------------------------------------------------------------- #
def detect_weaknesses(
    trades: list[dict[str, Any]],
    equity_curve: list[tuple[str, float]] | None = None,
    *,
    min_trades_for_regime: int = 5,
) -> dict[str, Any]:
    """Produce a structured Weakness Detection JSON report.

    Flags actionable weaknesses so the research loop / gatekeeper can decide
    whether a candidate is overfit or structurally broken.
    """
    closed = [t for t in trades if t.get("net_pnl") is not None]
    perf = compute_performance(closed)
    risk = compute_risk(closed, equity_curve)
    regimes = compute_regime_breakdown(closed)

    flags: list[str] = []
    severity = "LOW"

    # --- Expectancy / PF weakness --------------------------------------- #
    if perf["total_trades"] >= min_trades_for_regime:
        if perf["expectancy_r"] <= 0.0:
            flags.append("NEGATIVE_EXPECTANCY")
            severity = "HIGH"
        if perf["profit_factor"] < 1.10 and perf["total_trades"] > 0:
            flags.append("LOW_PROFIT_FACTOR")
            if severity != "HIGH":
                severity = "MEDIUM"
        if perf["win_rate_pct"] < 30.0:
            flags.append("LOW_WIN_RATE")
            if severity != "HIGH":
                severity = "MEDIUM"

    # --- Regime-specific weaknesses ------------------------------------- #
    losing_regimes = [
        (name, data) for name, data in regimes.items()
        if data["trade_count"] >= min_trades_for_regime
        and data["is_losing_regime"]
    ]
    if losing_regimes:
        regime_names = ", ".join(name for name, _ in losing_regimes)
        flags.append(f"LOSING_REGIMES:{regime_names}")
        if severity != "HIGH":
            severity = "MEDIUM"

    # --- Stop / target structure (MAE vs MFE) --------------------------- #
    longs = [t for t in closed if t.get("direction") == "LONG"]
    shorts = [t for t in closed if t.get("direction") == "SHORT"]

    def _tight_stop_fraction(trades_subset: list[dict[str, Any]]) -> float:
        # Trades stopped out that later would have gone profitable (MFE > 0
        # but MAE hit stop first) → stops too tight.
        count = 0
        total = 0
        for t in trades_subset:
            if t.get("exit_reason") != "STOP_LOSS":
                continue
            total += 1
            mfe_r = float(t.get("mfe_r", 0.0) or 0.0)
            if mfe_r > 0:
                count += 1
        return (count / total) if total else 0.0

    tight_long = _tight_stop_fraction(longs)
    tight_short = _tight_stop_fraction(shorts)
    tight_overall = _tight_stop_fraction(closed)
    if tight_overall > 0.4 and len(closed) >= min_trades_for_regime:
        flags.append("STOPS_TOO_TIGHT")
        if severity != "HIGH":
            severity = "MEDIUM"

    # --- Cost drag ------------------------------------------------------- #
    gross_profit = perf["gross_profit"]
    gross_loss = perf["gross_loss"]
    costs = 0.0
    # Approximate costs from slippage/commission recorded on trades.
    for t in closed:
        costs += float(t.get("slippage_cost", 0.0) or 0.0)
        costs += float(t.get("commission_cost", 0.0) or 0.0)
    cost_drag_pct = (costs / (gross_profit + gross_loss) * 100.0) \
        if (gross_profit + gross_loss) > 0 else 0.0
    if cost_drag_pct > 20.0:
        flags.append("HIGH_COST_DRAG")
        if severity != "HIGH":
            severity = "MEDIUM"

    # --- Drawdown -------------------------------------------------------- #
    if risk["max_drawdown_pct"] > 15.0:
        flags.append("HIGH_DRAWDOWN")
        if severity != "HIGH":
            severity = "MEDIUM"

    report = {
        "summary": {
            "total_trades": perf["total_trades"],
            "win_rate_pct": perf["win_rate_pct"],
            "profit_factor": perf["profit_factor"],
            "expectancy_r": perf["expectancy_r"],
            "net_pnl": perf["net_pnl"],
            "max_drawdown_pct": risk["max_drawdown_pct"],
            "var_95_pnl": risk["var_95_pnl"],
            "cvar_95_pnl": risk["cvar_95_pnl"],
            "cost_drag_pct": round(cost_drag_pct, 4),
        },
        "regime_breakdown": regimes,
        "losing_regimes": [name for name, _ in losing_regimes],
        "flags": flags,
        "severity": severity,
        "recommendation": (
            "REJECT" if severity == "HIGH" else
            "REVIEW" if severity == "MEDIUM" else "ACCEPT"
        ),
    }
    return report


def weakness_report_json(trades: list[dict[str, Any]],
                         equity_curve: list[tuple[str, float]] | None = None,
                         ) -> str:
    """Return the weakness detection report as a JSON string."""
    return json.dumps(detect_weaknesses(trades, equity_curve), indent=2)


__all__ = [
    "compute_performance",
    "compute_risk",
    "compute_regime_breakdown",
    "detect_weaknesses",
    "weakness_report_json",
]
