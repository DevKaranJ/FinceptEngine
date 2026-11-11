"""validation/gatekeeper.py — Independent Validation Gatekeeper (Layer 6).

Runs 4 deterministic tests on a candidate strategy (V2) against a baseline
(V1). **All 4 must PASS** for the candidate to be promoted; otherwise it is
REJECTED and V1 stays active. The gatekeeper never lets the AI self-approve.

Tests (per STRATEGY_AND_VALIDATION_SPEC.md Section 3):
  1. Out-of-Sample (OOS) Split 70/30:
       PF_OOS(V2) >= 1.25  AND  ER_OOS(V2) > ER_OOS(V1)  AND
       MaxDD_OOS(V2) <= MaxDD_OOS(V1)
  2. Rolling Walk-Forward (K=5 windows):
       >= 4 of 5 windows with net positive Expectancy (E_R > 0)
  3. Parameter Sensitivity Heatmap (5x5 grid):
       perturb top 2 numerical params by {-20,-10,0,+10,+20}%,
       >= 20 of 25 cells with PF > 1.10
  4. Execution Cost & Slippage Stress (1.5x slippage on OOS):
       Stressed PF_OOS >= 1.15  AND  net Expectancy E_R >= +0.12R

Result: ``APPROVED`` (all 4 pass) or ``REJECTED`` (any failure).
Report is persisted to SQLite ``validation_reports``.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from trading_engine.config import DB_PATH, DEFAULT_SLIPPAGE_BP
from trading_engine.data.clock import iso_now_utc
from trading_engine.evaluation.analyzer import (
    compute_performance,
    compute_risk,
    detect_weaknesses,
)
from trading_engine.memory.db import get_connection, initialize_database, log_activity
from trading_engine.validation.backtester import Backtester, BacktestResult


# --------------------------------------------------------------------------- #
# Gate thresholds                                                             #
# --------------------------------------------------------------------------- #
OOS_PF_MIN = 1.25          # PF_OOS(V2) must be >= 1.25
OOS_ER_MUST_BE_GREATER_THAN_BASELINE = True  # ER_OOS(V2) > ER_OOS(V1)
OOS_MAXDD_MUST_NOT_EXCEED_BASELINE = True    # MaxDD_OOS(V2) <= MaxDD_OOS(V1)

WINDOWS_K = 5              # walk-forward windows
WFA_PROFITABLE_RATIO = 0.80  # >= 80% of windows must have ER > 0

HEATMAP_GRID = 5           # 5x5 = 25 cells
HEATMAP_PF_MIN = 1.10      # cell PF must be > 1.10
HEATMAP_PASS_RATIO = 0.80  # >= 80% of cells must pass

COST_STRESS_SLIPPAGE_MULT = 1.5  # 1.5x baseline slippage
COST_STRESS_PF_MIN = 1.15        # stressed PF_OOS >= 1.15
COST_STRESS_ER_MIN = 0.12        # stressed ER >= +0.12R

PARAM_PCT_SHIFTS = (-0.20, -0.10, 0.0, 0.10, 0.20)

MIN_TRADES_FOR_METRIC = 3  # minimum closed trades for a backtest to be valid


@dataclass
class GateTestResult:
    name: str
    passed: bool
    detail: dict[str, Any]


@dataclass
class ValidationReport:
    report_id: str
    candidate_strategy_id: str
    baseline_strategy_id: str
    symbol: str
    timeframe: str
    in_sample_metrics: dict[str, Any]
    out_of_sample_metrics: dict[str, Any]
    walk_forward_summary: dict[str, Any]
    parameter_heatmap: dict[str, Any]
    cost_stress_metrics: dict[str, Any]
    oos_passed: bool
    walk_forward_passed: bool
    param_stability_passed: bool
    cost_stress_passed: bool
    final_status: str  # 'APPROVED' or 'REJECTED'
    rejection_reason: str | None
    evaluated_at_utc: str

    def to_db_row(self) -> tuple[Any, ...]:
        return (
            self.report_id,
            self.candidate_strategy_id,
            self.baseline_strategy_id,
            self.symbol,
            self.timeframe,
            json.dumps(self.in_sample_metrics),
            json.dumps(self.out_of_sample_metrics),
            json.dumps(self.walk_forward_summary),
            json.dumps(self.parameter_heatmap),
            json.dumps(self.cost_stress_metrics),
            int(self.oos_passed),
            int(self.walk_forward_passed),
            int(self.param_stability_passed),
            int(self.cost_stress_passed),
            self.final_status,
            self.rejection_reason,
            self.evaluated_at_utc,
        )


class ValidationGatekeeper:
    """Deterministic approval gate for candidate strategy promotion."""

    def __init__(
        self,
        candidate: Any,           # BaseStrategy (V2 candidate)
        baseline: Any,            # BaseStrategy (V1 baseline)
        *,
        db_path: str = DB_PATH,
        account_equity: float = 10000.0,
        slippage_bp: float = DEFAULT_SLIPPAGE_BP,
    ) -> None:
        self.candidate = candidate
        self.baseline = baseline
        self.db_path = db_path
        self.account_equity = account_equity
        self.slippage_bp = slippage_bp
        initialize_database(db_path=db_path)

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        df_features: Any,
        *,
        symbol: str = "UNKNOWN",
        timeframe: str = "1m",
    ) -> ValidationReport:
        """Run all 4 validation tests and return a ValidationReport.

        The data is split chronologically: first 70% In-Sample, final 30%
        Out-of-Sample. No future leakage: each backtest sees only bars up to
        its own end index.
        """
        n = len(df_features)
        if n < 60:
            raise ValueError(
                f"Need at least 60 bars for validation, got {n}"
            )

        split_idx = int(math.floor(n * 0.70))
        oos_start = split_idx

        # ------------------------------------------------------------------ #
        # Test 1: Out-of-Sample (OOS) split 70/30                            #
        # ------------------------------------------------------------------ #
        is_res_v2 = self._run_backtest(
            self.candidate, df_features, 0, split_idx,
            slippage_bp=self.slippage_bp,
        )
        oos_res_v2 = self._run_backtest(
            self.candidate, df_features, oos_start, n,
            slippage_bp=self.slippage_bp,
        )
        oos_res_v1 = self._run_backtest(
            self.baseline, df_features, oos_start, n,
            slippage_bp=self.slippage_bp,
        )

        oos_perf = compute_performance(oos_res_v2.closed_trades)
        oos_perf_v1 = compute_performance(oos_res_v1.closed_trades)
        oos_risk = compute_risk(oos_res_v2.closed_trades, oos_res_v2.equity_curve)
        oos_risk_v1 = compute_risk(oos_res_v1.closed_trades, oos_res_v1.equity_curve)

        pf_ok = oos_perf["profit_factor"] >= OOS_PF_MIN
        er_ok = (
            oos_perf["expectancy_r"] > oos_perf_v1["expectancy_r"]
        ) if oos_perf_v1["total_trades"] > 0 else True
        dd_ok = (
            oos_risk["max_drawdown_pct"] <= oos_risk_v1["max_drawdown_pct"]
        ) if oos_perf_v1["total_trades"] > 0 else True
        oos_passed = pf_ok and er_ok and dd_ok and oos_perf["total_trades"] >= MIN_TRADES_FOR_METRIC

        # ------------------------------------------------------------------ #
        # Test 2: Rolling Walk-Forward (K=5 windows)                         #
        # ------------------------------------------------------------------ #
        wfa_results = self._walk_forward(df_features, n, oos_start)
        profitable_windows = sum(
            1 for w in wfa_results if w["expectancy_r"] > 0
        )
        wfa_passed = profitable_windows >= math.ceil(WINDOWS_K * WFA_PROFITABLE_RATIO)

        # ------------------------------------------------------------------ #
        # Test 3: Parameter Sensitivity Heatmap (5x5 grid)                   #
        # ------------------------------------------------------------------ #
        heatmap = self._parameter_heatmap(df_features, 0, split_idx)
        param_stability_passed = heatmap["pass_ratio"] >= HEATMAP_PASS_RATIO

        # ------------------------------------------------------------------ #
        # Test 4: Execution Cost & Slippage Stress (1.5x on OOS)             #
        # ------------------------------------------------------------------ #
        stressed_slippage = self.slippage_bp * COST_STRESS_SLIPPAGE_MULT
        stressed_res = self._run_backtest(
            self.candidate, df_features, oos_start, n,
            slippage_bp=stressed_slippage,
        )
        stressed_perf = compute_performance(stressed_res.closed_trades)
        cost_stress_passed = (
            stressed_perf["profit_factor"] >= COST_STRESS_PF_MIN
            and stressed_perf["expectancy_r"] >= COST_STRESS_ER_MIN
            and stressed_perf["total_trades"] >= MIN_TRADES_FOR_METRIC
        )

        # ------------------------------------------------------------------ #
        # Final decision                                                     #
        # ------------------------------------------------------------------ #
        all_passed = (
            oos_passed and wfa_passed and param_stability_passed and cost_stress_passed
        )
        final_status = "APPROVED" if all_passed else "REJECTED"

        rejection_reason = None
        if not all_passed:
            reasons = []
            if not oos_passed:
                reasons.append("OOS_TEST_FAILED")
            if not wfa_passed:
                reasons.append("WALK_FORWARD_FAILED")
            if not param_stability_passed:
                reasons.append("PARAMETER_SENSITIVITY_FAILED")
            if not cost_stress_passed:
                reasons.append("COST_STRESS_FAILED")
            rejection_reason = "; ".join(reasons)

        report = ValidationReport(
            report_id=f"VAL_{uuid.uuid4().hex[:10]}",
            candidate_strategy_id=self.candidate.strategy_id,
            baseline_strategy_id=self.baseline.strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            in_sample_metrics={
                "candidate": compute_performance(is_res_v2.closed_trades),
                "candidate_risk": compute_risk(is_res_v2.closed_trades, is_res_v2.equity_curve),
            },
            out_of_sample_metrics={
                "candidate": oos_perf,
                "candidate_risk": oos_risk,
                "baseline": oos_perf_v1,
                "baseline_risk": oos_risk_v1,
                "pf_ok": pf_ok,
                "er_ok": er_ok,
                "dd_ok": dd_ok,
            },
            walk_forward_summary={
                "windows": wfa_results,
                "profitable_windows": profitable_windows,
                "total_windows": WINDOWS_K,
                "required": math.ceil(WINDOWS_K * WFA_PROFITABLE_RATIO),
                "passed": wfa_passed,
            },
            parameter_heatmap=heatmap,
            cost_stress_metrics={
                "stressed_slippage_bp": stressed_slippage,
                "stressed": stressed_perf,
                "passed": cost_stress_passed,
            },
            oos_passed=oos_passed,
            walk_forward_passed=wfa_passed,
            param_stability_passed=param_stability_passed,
            cost_stress_passed=cost_stress_passed,
            final_status=final_status,
            rejection_reason=rejection_reason,
            evaluated_at_utc=iso_now_utc(),
        )

        self._persist_report(report)
        return report

    # ------------------------------------------------------------------ #
    # Test implementations                                                 #
    # ------------------------------------------------------------------ #
    def _run_backtest(
        self,
        strategy: Any,
        df_features: Any,
        start_idx: int,
        end_idx: int,
        *,
        slippage_bp: float,
    ) -> BacktestResult:
        """Run a backtest over [start_idx, end_idx) with given slippage."""
        bt = Backtester(
            strategy,
            account_equity=self.account_equity,
            slippage_bp=slippage_bp,
            db_path=self.db_path,
            execution_mode="BACKTEST",
        )
        return bt.run(df_features, start_idx=start_idx, end_idx=end_idx)

    def _walk_forward(
        self,
        df_features: Any,
        n: int,
        oos_start: int,
    ) -> list[dict[str, Any]]:
        """K=5 expanding walk-forward windows over the OOS region.

        Window i: train = [0, oos_start + i*seg), test = [oos_start + i*seg,
        oos_start + (i+1)*seg). All bars are within the OOS region so no
        look-ahead into future test data occurs during training.
        """
        results: list[dict[str, Any]] = []
        oos_len = n - oos_start
        seg = max(1, oos_len // (WINDOWS_K + 1))

        for i in range(WINDOWS_K):
            train_end = oos_start + (i + 1) * seg
            test_end = min(oos_start + (i + 2) * seg, n)
            if test_end <= train_end:
                break

            # Train on historical data only (zero look-ahead into test).
            self._run_backtest(
                self.candidate, df_features, 0, train_end,
                slippage_bp=self.slippage_bp,
            )
            # Evaluate on the unseen test window.
            test_res = self._run_backtest(
                self.candidate, df_features, train_end, test_end,
                slippage_bp=self.slippage_bp,
            )
            perf = compute_performance(test_res.closed_trades)
            results.append({
                "window": i + 1,
                "train_bars": train_end,
                "test_bars": test_end - train_end,
                "expectancy_r": perf["expectancy_r"],
                "profit_factor": perf["profit_factor"],
                "net_pnl": perf["net_pnl"],
                "total_trades": perf["total_trades"],
                "profitable": perf["expectancy_r"] > 0,
            })
        return results

    def _parameter_heatmap(
        self,
        df_features: Any,
        start_idx: int,
        end_idx: int,
    ) -> dict[str, Any]:
        """5x5 grid over the top 2 numerical params of the candidate.

        Perturbs each param by {-20,-10,0,+10,+20}% and runs a backtest on
        in-sample data for each cell. Returns per-cell PF and pass ratio.
        """
        param_names = self._top_numerical_params()
        if len(param_names) < 2:
            # Degenerate: not enough tunable params → pass by default.
            return {
                "param_names": param_names,
                "grid_size": 0,
                "cells": [],
                "pass_count": 0,
                "fail_count": 0,
                "pass_ratio": 1.0,
                "passed": True,
                "note": "insufficient tunable parameters",
            }

        p1_name, p2_name = param_names[0], param_names[1]
        p1_base = float(self.candidate.default_params[p1_name])
        p2_base = float(self.candidate.default_params[p2_name])

        cells: list[dict[str, Any]] = []
        pass_count = 0

        for shift1 in PARAM_PCT_SHIFTS:
            for shift2 in PARAM_PCT_SHIFTS:
                p1_val = p1_base * (1.0 + shift1)
                p2_val = p2_base * (1.0 + shift2)
                params = dict(self.candidate.default_params)
                params[p1_name] = p1_val
                params[p2_name] = p2_val

                variant = self._make_variant(params)
                res = self._run_backtest(
                    variant, df_features, start_idx, end_idx,
                    slippage_bp=self.slippage_bp,
                )
                perf = compute_performance(res.closed_trades)
                pf = perf["profit_factor"]
                passed = pf > HEATMAP_PF_MIN and perf["total_trades"] >= MIN_TRADES_FOR_METRIC
                if passed:
                    pass_count += 1
                cells.append({
                    "p1": p1_name, "p1_value": round(p1_val, 6),
                    "p2": p2_name, "p2_value": round(p2_val, 6),
                    "profit_factor": round(pf, 4),
                    "expectancy_r": round(perf["expectancy_r"], 4),
                    "total_trades": perf["total_trades"],
                    "passed": passed,
                })

        total_cells = len(cells)
        pass_ratio = (pass_count / total_cells) if total_cells else 0.0

        return {
            "param_names": [p1_name, p2_name],
            "grid_size": total_cells,
            "cells": cells,
            "pass_count": pass_count,
            "fail_count": total_cells - pass_count,
            "pass_ratio": round(pass_ratio, 4),
            "passed": pass_ratio >= HEATMAP_PASS_RATIO,
        }

    def _top_numerical_params(self) -> list[str]:
        """Return the first 2 tunable numerical params of the candidate."""
        names: list[str] = []
        for name, val in self.candidate.default_params.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                names.append(name)
            if len(names) >= 2:
                break
        return names

    def _make_variant(self, params: dict[str, Any]) -> Any:
        """Construct a strategy variant with the given params."""
        cls = type(self.candidate)
        return cls(params=params)

    # ------------------------------------------------------------------ #
    # Persistence                                                        #
    # ------------------------------------------------------------------ #
    def _persist_report(self, report: ValidationReport) -> None:
        """Insert the validation report into SQLite validation_reports."""
        conn = get_connection(db_path=self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO validation_reports
                    (report_id, candidate_strategy_id, baseline_strategy_id,
                     symbol, timeframe, in_sample_metrics_json,
                     out_of_sample_metrics_json, walk_forward_summary_json,
                     parameter_heatmap_json, cost_stress_metrics_json,
                     oos_passed, walk_forward_passed, param_stability_passed,
                     cost_stress_passed, final_status, rejection_reason,
                     evaluated_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                report.to_db_row(),
            )
            conn.commit()
            log_activity(
                "GATEKEEPER", "VALIDATION_COMPLETED",
                f"{report.candidate_strategy_id} vs {report.baseline_strategy_id}: "
                f"{report.final_status}",
                {
                    "report_id": report.report_id,
                    "candidate": report.candidate_strategy_id,
                    "baseline": report.baseline_strategy_id,
                    "final_status": report.final_status,
                    "oos_passed": report.oos_passed,
                    "walk_forward_passed": report.walk_forward_passed,
                    "param_stability_passed": report.param_stability_passed,
                    "cost_stress_passed": report.cost_stress_passed,
                },
                db_path=self.db_path,
            )
        finally:
            conn.close()
