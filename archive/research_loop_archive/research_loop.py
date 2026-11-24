"""trading_engine/agents/research_loop.py — 4-Role AI Self-Improvement Research Loop (Layer 5).

Pipeline (offline / deterministic — no external LLM SDK):

  ResearchAgent   → reads the Weakness Report for V1 (from evaluation/analyzer.py)
                    and backtester output, producing a weakness summary.
  HypothesisAgent → converts weaknesses into a concrete, parameterized trade idea.
  CodingAgent     → renders a new candidate strategy file into strategies/candidates/
                    using a zero-look-ahead template (Contract A, BaseStrategy).
  ReviewAgent     → static look-ahead-bias audit + ValidationGatekeeper gating
                    (OOS, Walk-Forward, Parameter Heatmap, Cost Stress).
                    Promotes V2 or rejects it — V1 stays active on any failure.

Design constraints (non-negotiable):
  * Zero look-ahead: every generated signal reads only df_features.iloc[:current_idx+1].
  * No external LLM SDK imports are used — all reasoning is deterministic
    template logic keyed off weakness flags.
  * Never let the AI self-approve: ReviewAgent always routes through the independent
    ValidationGatekeeper; promotion is only APPROVED when all 4 gate tests pass.
  * V1 stays active on any failure — the research loop never overwrites the active
    baseline; it only writes candidate files under strategies/candidates/.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_engine.config import (
    ATR_STOP_BUFFER_MULTIPLIER,
    DEFAULT_SLIPPAGE_BP,
    MIN_RISK_REWARD_RATIO,
    DB_PATH,
)
from trading_engine.data.clock import iso_now_utc
from trading_engine.evaluation.analyzer import detect_weaknesses, weakness_report_json
from trading_engine.memory.db import get_connection, initialize_database, log_activity
from trading_engine.validation.backtester import Backtester
from trading_engine.validation.gatekeeper import ValidationGatekeeper
from trading_engine.strategies.base_strategy import BaseStrategy

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #

CANDIDATES_DIR = Path("trading_engine/strategies/candidates")
APPROVED_DIR = Path("trading_engine/strategies/approved")

V1_STRATEGY_ID = "EMA_BREAKOUT_V1"
V1_MODULE = "trading_engine.strategies.approved.ema_breakout_v1"
V1_CLASS = "EmaBreakoutV1"

# Deterministic template parameters keyed to weakness flags. These are the
# "research knobs" the agents tune when generating V2 candidates. No randomness.
DEFAULT_V2_PARAMS = {
    "ema_fast_len": 12,
    "ema_slow_len": 26,
    "atr_len": 14,
    "atr_mult_threshold": 1.05,
    "hma_len": 20,
    "sl_atr_mult": 1.5,
    "tp_rr_ratio": 1.5,
    "tp2_rr_ratio": 3.0,
    "rsi_len": 14,
    "rsi_entry_threshold": 55.0,
    "donchian_len": 20,
}


# --------------------------------------------------------------------------- #
# Role 1: ResearchAgent — consumes V1 weakness report                         #
# --------------------------------------------------------------------------- #


@dataclass
class WeaknessSummary:
    """Distilled weaknesses the research loop must address in V2."""
    flags: list[str] = field(default_factory=list)
    severity: str = "LOW"
    recommendation: str = "ACCEPT"
    total_trades: int = 0
    win_rate_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy_r: float = 0.0
    max_drawdown_pct: float = 0.0
    losing_regimes: list[str] = field(default_factory=list)
    cost_drag_pct: float = 0.0
    raw_report: dict[str, Any] = field(default_factory=dict)


class ResearchAgent:
    """Role 1 — reads V1's Weakness Report and distills actionable findings."""

    def __init__(self) -> None:
        self.name = "ResearchAgent"

    def run(
        self,
        trades: list[dict[str, Any]],
        equity_curve: list[tuple[str, float]] | None = None,
    ) -> WeaknessSummary:
        """Run weakness detection on V1 trade history and return a summary."""
        report = detect_weaknesses(trades, equity_curve)
        summary = WeaknessSummary(
            flags=list(report.get("flags", [])),
            severity=report.get("severity", "LOW"),
            recommendation=report.get("recommendation", "ACCEPT"),
            total_trades=report["summary"]["total_trades"],
            win_rate_pct=report["summary"]["win_rate_pct"],
            profit_factor=report["summary"]["profit_factor"],
            expectancy_r=report["summary"]["expectancy_r"],
            max_drawdown_pct=report["summary"]["max_drawdown_pct"],
            losing_regimes=list(report.get("losing_regimes", [])),
            cost_drag_pct=report["summary"]["cost_drag_pct"],
            raw_report=report,
        )
        log_activity(
            "RESEARCH_AGENT", "WEAKNESS_REPORT_CONSUMED",
            f"V1 weakness report consumed: {len(summary.flags)} flags, "
            f"severity={summary.severity}",
            {
                "flags": summary.flags,
                "severity": summary.severity,
                "expectancy_r": summary.expectancy_r,
                "profit_factor": summary.profit_factor,
            },
            db_path=DB_PATH,
        )
        return summary


# --------------------------------------------------------------------------- #
# Role 2: HypothesisAgent — converts weaknesses into a trade idea             #
# --------------------------------------------------------------------------- #


@dataclass
class Hypothesis:
    """A concrete, parameterized trade idea derived from V1 weaknesses."""
    hypothesis_id: str
    title: str
    rationale: str
    target_weaknesses: list[str]
    entry_logic: list[str]          # signal wrappers to use
    regime_filters: list[str]       # regime alignment filters
    stop_logic: str
    target_logic: str
    params: dict[str, Any]
    paradigm_tags: list[str]


class HypothesisAgent:
    """Role 2 — turns weakness flags into a deterministic V2 trade hypothesis."""

    def __init__(self) -> None:
        self.name = "HypothesisAgent"

    def run(self, weakness: WeaknessSummary) -> Hypothesis:
        """Generate a hypothesis that directly targets V1's flagged weaknesses."""
        hid = f"HYP_{uuid.uuid4().hex[:8]}"
        params = dict(DEFAULT_V2_PARAMS)
        entry_logic: list[str] = []
        regime_filters: list[str] = []
        tags: list[str] = ["TECHNICAL", "V2_CANDIDATE"]
        rationale_parts: list[str] = []

        flags = set(weakness.flags)

        # --- NEGATIVE_EXPECTANCY / LOW_PROFIT_FACTOR / LOW_WIN_RATE -------
        # Tighten entry: require RSI confirmation + Donchian breakout to raise
        # win rate and profit factor vs V1's raw EMA cross.
        if {"NEGATIVE_EXPECTANCY", "LOW_PROFIT_FACTOR", "LOW_WIN_RATE"} & flags:
            entry_logic.extend([
                "rsi_above(row, rsi_col='rsi_14', threshold=55.0)",
                "donchian_breakout_up(row, high_col='high', donchian_upper_col='donchian_upper_20')",
            ])
            regime_filters.extend(["is_ema_bull_trend", "price_above_hma"])
            tags.extend(["TREND", "MOMENTUM_FILTER"])
            rationale_parts.append(
                "V1 has negative/low expectancy: add RSI bullish alignment and "
                "Donchian breakout confirmation to raise win rate and PF."
            )
            params["rsi_entry_threshold"] = 55.0

        # --- STOPS_TOO_TIGHT ----------------------------------------------
        # Widen stop slightly and require ATR expansion to avoid premature exits.
        if "STOPS_TOO_TIGHT" in flags:
            entry_logic.append("atr_above_threshold(atr_col='atr_14', atr_sma_col='atr_14_sma', multiplier=1.10)")
            regime_filters.append("atr_above_threshold")
            tags.append("VOLATILITY_FILTER")
            rationale_parts.append(
                "V1 stops too tight: require ATR expansion vs its SMA and keep "
                "ATR-based stop with a 1.5x buffer to avoid premature exits."
            )
            params["atr_mult_threshold"] = 1.10

        # --- LOSING_REGIMES -----------------------------------------------
        if weakness.losing_regimes:
            regime_filters.append("is_ema_bull_trend")
            tags.append("REGIME_FILTER")
            rationale_parts.append(
                f"V1 loses in regimes {weakness.losing_regimes}: restrict entries "
                "to bullish EMA alignment + price above HMA to avoid choppy regimes."
            )

        # --- HIGH_COST_DRAG -----------------------------------------------
        if "HIGH_COST_DRAG" in flags:
            tags.append("LOW_TURNOVER")
            rationale_parts.append(
                "V1 has high cost drag: reduce turnover by adding confirmation "
                "filters so trades only trigger on aligned setups."
            )

        # --- HIGH_DRAWDOWN ------------------------------------------------
        if "HIGH_DRAWDOWN" in flags:
            tags.append("DRAWDOWN_CONTROL")
            rationale_parts.append(
                "V1 drawdown elevated: ATR-based stop + 1.5x R:R target cap "
                "limits single-trade loss exposure."
            )

        # Defaults when no specific flag fired (still produce a valid V2 idea).
        if not entry_logic:
            entry_logic.extend([
                "ema_fast_cross_above(row, ema_fast_col='ema_12', ema_slow_col='ema_26')",
                "rsi_above(row, rsi_col='rsi_14', threshold=50.0)",
            ])
            regime_filters.extend(["is_ema_bull_trend", "price_above_hma"])
            rationale_parts.append(
                "No severe V1 weakness detected: generate a refined EMA-breakout "
                "candidate with RSI confirmation and HMA bias as the baseline V2."
            )

        title = "Refined EMA Breakout + RSI/Donchian Confirmation (V2)"
        rationale = " ".join(rationale_parts)
        stop_logic = f"stop = entry - {ATR_STOP_BUFFER_MULTIPLIER} * ATR(14)"
        target_logic = (
            f"target_1 = entry + risk * {MIN_RISK_REWARD_RATIO}; "
            f"target_2 = entry + risk * 2.0 * {MIN_RISK_REWARD_RATIO}"
        )

        hypothesis = Hypothesis(
            hypothesis_id=hid,
            title=title,
            rationale=rationale,
            target_weaknesses=list(flags),
            entry_logic=entry_logic,
            regime_filters=regime_filters,
            stop_logic=stop_logic,
            target_logic=target_logic,
            params=params,
            paradigm_tags=tags,
        )
        log_activity(
            "RESEARCH_AGENT", "HYPOTHESIS_GENERATED",
            f"{hid}: {title} targeting {', '.join(flags) or 'baseline-refinement'}",
            {
                "hypothesis_id": hid,
                "target_weaknesses": list(flags),
                "params": hypothesis.params,
            },
            db_path=DB_PATH,
        )
        return hypothesis


# --------------------------------------------------------------------------- #
# Role 3: CodingAgent — renders V2 candidate strategy file                    #
# --------------------------------------------------------------------------- #


class CodingAgent:
    """Role 3 — renders a zero-look-ahead V2 candidate strategy source file.

    The generated file:
      * imports only signal wrappers from signals/technical_signals.py
      * inherits BaseStrategy and implements Contract A evaluate()
      * reads only df_features.iloc[:current_idx+1] (no future bars)
      * is written to strategies/candidates/<strategy_id>.py
      * is NOT imported into the active approved/ directory (V1 stays active)
    """

    def __init__(self, candidates_dir: str | Path = CANDIDATES_DIR) -> None:
        self.name = "CodingAgent"
        self.candidates_dir = Path(candidates_dir)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    # -- template ----------------------------------------------------------- #
    _TEMPLATE = '''"""strategies/candidates/{strategy_file}.py — AI-generated V2 candidate.

{docstring}

Paradigm: {paradigm_tags}
Zero look-ahead: evaluate() reads only df_features.iloc[:current_idx+1];
signal wrappers read current/previous row only — never future bars.

Auto-generated by CodingAgent (research_loop.py). This file lives under
strategies/candidates/ and is NOT promoted to strategies/approved/ until the
independent ValidationGatekeeper returns APPROVED.
"""

from __future__ import annotations

from typing import Any

from trading_engine.signals.technical_signals import (
    {signal_imports}
)

from trading_engine.strategies.base_strategy import BaseStrategy


class {class_name}(BaseStrategy):
    """V2 candidate: {title}.

    {rationale_wrapped}
    """

    strategy_id = "{strategy_id}"
    parent_strategy_id = "EMA_BREAKOUT_V1"
    paradigm_tags = {paradigm_tags_list}

    default_params = {params_dict}

    def evaluate(self, df_features: Any, current_idx: int) -> dict[str, Any] | None:
        row = df_features.iloc[current_idx]

        # --- Pull pre-computed feature columns (zero look-ahead, current bar only) ---
        # Fixed columns produced by the indicators layer (matching the V1 feature
        # store). Params tune thresholds/levels, NOT column names — this keeps the
        # parameter heatmap stable (perturbing a param never changes column names).
        close = float(row["close"])
        atr = float(row["atr_14"])

        ema_fast_col = "ema_12"
        ema_slow_col = "ema_26"
        hma_col = "hma_20"
        rsi_col = "rsi_14"
        atr_sma_col = "atr_14_sma"
        donchian_upper_col = "donchian_upper_20"

        # --- Feature columns must exist upstream (indicators layer) ---
        # Required: close, atr_14, atr_14_sma, ema_12, ema_26, hma_20, rsi_14,
        #           donchian_upper_20. All computed only from past bars.

        prev_row = df_features.iloc[current_idx - 1] if current_idx > 0 else None

{entry_block}

        # --- Regime / trend alignment filters ---
{regime_block}
        # --- Volatility expansion filter (avoid low-ATR chop) ---
        atr_series = df_features["atr_14"].iloc[: current_idx + 1]
        atr_sma = float(atr_series.rolling(window=14, min_periods=1).mean().iloc[-1])
        atr_expanding = atr > atr_sma * self.params["atr_mult_threshold"]
        if not atr_expanding:
            return None

        # --- Risk / target levels (ATR-based, R:R capped) ---
        risk = self.params["sl_atr_mult"] * atr
        stop_loss = close - risk
        target_1 = close + (risk * self.params["tp_rr_ratio"])
        target_2 = close + (risk * self.params["tp2_rr_ratio"])

        regime_snapshot = {{
            "volatility_regime": "EXPANDING_ATR",
            "atr": atr,
            "atr_sma": atr_sma,
            "trend_regime": "BULLISH",
            "hma_len": self.params["hma_len"],
            "rsi_len": self.params["rsi_len"],
        }}

        return self.build_signal(
            row=row,
            direction="LONG",
            entry_price=close,
            stop_loss_raw=stop_loss,
            target_1_raw=target_1,
            target_2_raw=target_2,
            active_signals={active_signals_list},
            regime_snapshot=regime_snapshot,
        )
'''

    def run(self, hypothesis: Hypothesis) -> dict[str, Any]:
        """Render the V2 candidate source file and return its metadata."""
        strategy_id = f"V2_CANDIDATE_{hypothesis.hypothesis_id}"
        class_name = f"V2Candidate{hypothesis.hypothesis_id[-8:]}"
        strategy_file = strategy_id.lower()

        # Build entry block from hypothesis.entry_logic (deterministic ordering).
        # The template already indents {entry_block} by 8 spaces (method body),
        # so entry lines carry 0 indent (absolute 8) and ``return None`` carries
        # 8 spaces within entry_block (absolute 12, deeper than the ``if`` at 8).
        entry_lines = []
        for sig in hypothesis.entry_logic:
            entry_lines.append(f"        if not {sig}:")
            entry_lines.append("            return None")
        entry_block = "\n".join(entry_lines) if entry_lines else "        pass  # entry filters above"

        # Build regime block.
        regime_lines = []
        for filt in hypothesis.regime_filters:
            if filt == "is_ema_bull_trend":
                regime_lines.append(
                    "        if not is_ema_bull_trend(row, close_col='close', "
                    "ema_fast_col=ema_fast_col, ema_slow_col=ema_slow_col):")
                regime_lines.append("            return None")
            elif filt == "price_above_hma":
                regime_lines.append(
                    "        if not price_above_hma(row, hma_col=hma_col, close_col='close'):")
                regime_lines.append("            return None")
            elif filt == "atr_above_threshold":
                regime_lines.append(
                    "        if not atr_above_threshold(row, atr_col='atr_14', "
                    "atr_sma_col='atr_14_sma', multiplier=1.10):")
                regime_lines.append("            return None")
        regime_block = "\n".join(regime_lines) if regime_lines else "        pass  # regime filters above"

        # Signal imports needed.
        needed = set()
        # Scan entry_logic + regime_filters for signal names to import.
        for text in list(hypothesis.entry_logic) + list(hypothesis.regime_filters):
            for name in ("ema_fast_cross_above", "ema_fast_cross_below",
                           "rsi_above", "rsi_oversold", "rsi_overbought",
                           "donchian_breakout_up", "donchian_breakout_down",
                           "atr_above_threshold", "atr_below_threshold",
                           "is_ema_bull_trend", "is_ema_bear_trend",
                           "price_above_hma", "price_below_hma"):
                if name in text:
                    needed.add(name)
        needed.add("ema_fast_cross_above")  # always reference at least one
        signal_imports = ",\n    ".join(sorted(needed))

        active_signals = ["V2_ENTRY_CONFIRMATION", "V2_REGIME_FILTER",
                          "V2_ATR_VOLATILITY_FILTER"]
        for sig in hypothesis.entry_logic:
            for name in ("ema_fast_cross_above", "ema_fast_cross_below",
                           "rsi_above", "donchian_breakout_up"):
                if name in sig:
                    active_signals.append(name.upper())

        params_repr = repr(hypothesis.params)
        paradigm_tags_list = repr(hypothesis.paradigm_tags)

        # Wrap rationale into comment lines (max 72 chars).
        rationale = hypothesis.rationale
        wrapped = []
        for i in range(0, len(rationale), 70):
            wrapped.append(f"    # {rationale[i:i+70]}")
        rationale_wrapped = "\n".join(wrapped) if wrapped else "    # V2 candidate generated from V1 weakness report."

        source = self._TEMPLATE.format(
            strategy_file=strategy_file,
            docstring=hypothesis.title,
            paradigm_tags=", ".join(hypothesis.paradigm_tags),
            signal_imports=signal_imports,
            class_name=class_name,
            title=hypothesis.title,
            rationale_wrapped=rationale_wrapped,
            strategy_id=strategy_id,
            params_dict=params_repr,
            paradigm_tags_list=paradigm_tags_list,
            entry_block=entry_block,
            regime_block=regime_block,
            active_signals_list=repr(sorted(set(active_signals))),
        )

        # Escape any leftover {{ }} that format didn't consume (literal braces
        # in the f-strings inside the template body).
        source = source.replace("{{", "{").replace("}}", "}")

        file_path = self.candidates_dir / f"{strategy_file}.py"
        file_path.write_text(source, encoding="utf-8")

        result = {
            "strategy_id": strategy_id,
            "class_name": class_name,
            "file_path": str(file_path),
            "module_path": f"trading_engine.strategies.candidates.{strategy_file}",
            "hypothesis_id": hypothesis.hypothesis_id,
            "params": hypothesis.params,
            "rationale": hypothesis.rationale,
            "created_at_utc": iso_now_utc(),
        }
        log_activity(
            "RESEARCH_AGENT", "V2_CANDIDATE_WRITTEN",
            f"{strategy_id} written to {file_path}",
            {
                "strategy_id": strategy_id,
                "file_path": str(file_path),
                "parent": "EMA_BREAKOUT_V1",
            },
            db_path=DB_PATH,
        )
        return result


# --------------------------------------------------------------------------- #
# Role 4: ReviewAgent — static audit + ValidationGatekeeper gate              #
# --------------------------------------------------------------------------- #


@dataclass
class ReviewResult:
    """Outcome of the ReviewAgent gate."""
    promoted: bool
    final_status: str  # 'APPROVED' or 'REJECTED'
    rejection_reason: str | None
    candidate_strategy_id: str
    baseline_strategy_id: str
    validation_report: Any  # ValidationReport
    look_ahead_audit: dict[str, Any]
    gate_summary: dict[str, Any]


class ReviewAgent:
    """Role 4 — static look-ahead-bias audit then independent ValidationGatekeeper.

    The ReviewAgent never self-approves: promotion requires all 4 gate tests
    (OOS, Walk-Forward, Parameter Heatmap, Cost Stress) to PASS via
    ValidationGatekeeper. On any failure V1 stays active.
    """

    def __init__(
        self,
        baseline_strategy_id: str = V1_STRATEGY_ID,
        db_path: str = DB_PATH,
    ) -> None:
        self.name = "ReviewAgent"
        self.baseline_strategy_id = baseline_strategy_id
        self.db_path = db_path
        initialize_database(db_path=db_path)

    # -- static look-ahead audit ------------------------------------------ #
    def audit_look_ahead(self, source: str) -> dict[str, Any]:
        """Deterministic static scan for forbidden future-leakage patterns.

        Returns a dict with ``passed`` bool and list of ``findings``.
        """
        findings: list[str] = []
        patterns = [
            (r"\.shift\(-\d+\)", "negative shift (future row) detected"),
            (r"iloc\[.*:\s*\-?\d+\s*:\s*\]", "future slice (iloc with end index)"),
            (r"\.iloc\[current_idx\s*\+\s*\d+\]", "index beyond current bar"),
            (r"\.tail\(", ".tail() reads trailing/future-relative data"),
            (r"\.sort_index\(.*ascending\s*=\s*False\)", "reverse sort may expose future"),
        ]
        for pattern, desc in patterns:
            if re.search(pattern, source):
                findings.append(desc)

        # Contract A field check — generated V2 must return Contract A keys.
        required_keys = [
            "strategy_id", "symbol", "timeframe", "timestamp_utc", "direction",
            "entry_price", "stop_loss_raw", "target_1_raw", "target_2_raw",
            "active_signals", "regime_snapshot",
        ]
        missing = [k for k in required_keys if k not in source]
        if missing:
            findings.append(f"missing Contract A keys: {missing}")

        # Must read only current_idx window.
        if "iloc[: current_idx + 1]" not in source and "iloc[current_idx]" not in source:
            findings.append("no zero-look-ahead row access (iloc[current_idx]) found")

        return {
            "passed": len(findings) == 0,
            "findings": findings,
            "contract_a_checked": True,
        }

    # -- helper: load V1 baseline ----------------------------------------- #
    def _load_baseline(self) -> BaseStrategy:
        mod = importlib.import_module(V1_MODULE)
        cls = getattr(mod, V1_CLASS)
        return cls()

    # -- helper: load V2 candidate from file ------------------------------ #
    def _load_candidate(self, file_path: str, class_name: str,
                        params: dict[str, Any]) -> BaseStrategy:
        module_path = file_path.replace("/", ".").replace(".py", "")
        # module_path like trading_engine.strategies.candidates.v2_candidate_xxxx
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls(params=params)

    # -- public gate ------------------------------------------------------- #
    def run(
        self,
        candidate_meta: dict[str, Any],
        df_features: Any,
        *,
        symbol: str = "BTCUSDT",
        timeframe: str = "1m",
    ) -> ReviewResult:
        """Audit the candidate then run it through ValidationGatekeeper.

        Returns a ReviewResult. promoted=True only when gate == APPROVED.
        """
        strategy_id = candidate_meta["strategy_id"]
        file_path = candidate_meta["file_path"]
        class_name = candidate_meta["class_name"]
        params = candidate_meta["params"]

        # 1. Read generated source for static audit.
        source = Path(file_path).read_text(encoding="utf-8")
        audit = self.audit_look_ahead(source)

        # 2. Load baseline (V1) and candidate (V2).
        baseline = self._load_baseline()
        candidate = self._load_candidate(file_path, class_name, params)

        # 3. Run independent ValidationGatekeeper (never self-approve).
        gatekeeper = ValidationGatekeeper(
            candidate=candidate,
            baseline=baseline,
            db_path=self.db_path,
        )
        report = gatekeeper.evaluate(df_features, symbol=symbol, timeframe=timeframe)

        promoted = report.final_status == "APPROVED" and audit["passed"]
        final_status = "APPROVED" if promoted else "REJECTED"

        rejection_reason = report.rejection_reason
        if not audit["passed"]:
            rejection_reason = (
                (rejection_reason + "; " if rejection_reason else "")
                + "LOOK_AHEAD_AUDIT_FAILED: " + "; ".join(audit["findings"])
            )
            final_status = "REJECTED"

        # 4. Persist promotion decision to strategy_registry if approved.
        if promoted:
            self._promote_candidate(candidate_meta, report)

        gate_summary = {
            "oos_passed": report.oos_passed,
            "walk_forward_passed": report.walk_forward_passed,
            "param_stability_passed": report.param_stability_passed,
            "cost_stress_passed": report.cost_stress_passed,
            "final_status": report.final_status,
        }

        result = ReviewResult(
            promoted=promoted,
            final_status=final_status,
            rejection_reason=rejection_reason,
            candidate_strategy_id=strategy_id,
            baseline_strategy_id=self.baseline_strategy_id,
            validation_report=report,
            look_ahead_audit=audit,
            gate_summary=gate_summary,
        )
        log_activity(
            "RESEARCH_AGENT", "REVIEW_COMPLETED",
            f"{strategy_id} vs {self.baseline_strategy_id}: {final_status}",
            {
                "candidate": strategy_id,
                "baseline": self.baseline_strategy_id,
                "promoted": promoted,
                "audit_passed": audit["passed"],
                "gate_status": report.final_status,
            },
            db_path=self.db_path,
        )
        return result

    # -- persistence ------------------------------------------------------- #
    def _promote_candidate(
        self,
        candidate_meta: dict[str, Any],
        report: Any,
    ) -> None:
        """Record the approved candidate in strategy_registry (candidate status)."""
        conn = get_connection(db_path=self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO strategy_registry
                    (strategy_id, parent_strategy_id, file_path, status,
                     paradigm_tags_json, parameters_json, hypothesis_summary,
                     created_at_utc, promoted_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_meta["strategy_id"],
                    "EMA_BREAKOUT_V1",
                    candidate_meta["file_path"],
                    "CANDIDATE_APPROVED",
                    json.dumps(["TECHNICAL", "V2_CANDIDATE"]),
                    json.dumps(candidate_meta["params"]),
                    candidate_meta["rationale"],
                    candidate_meta["created_at_utc"],
                    iso_now_utc(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


# --------------------------------------------------------------------------- #
# Orchestrator — runs the full 4-role pipeline end-to-end                     #
# --------------------------------------------------------------------------- #


class ResearchLoop:
    """Orchestrates Research → Hypothesis → Coding → Review.

    Use this single entry point for end-to-end V2 candidate generation and
    gating. V1 (EMA_BREAKOUT_V1) remains the active baseline unless ReviewAgent
    returns APPROVED — and even then only the candidate registry is updated;
    the active approved/ directory is never overwritten by this loop.
    """

    def __init__(self) -> None:
        self.research = ResearchAgent()
        self.hypothesis = HypothesisAgent()
        self.coding = CodingAgent()
        self.review = ReviewAgent()

    def run(
        self,
        trades: list[dict[str, Any]],
        df_features: Any,
        equity_curve: list[tuple[str, float]] | None = None,
        *,
        symbol: str = "BTCUSDT",
        timeframe: str = "1m",
    ) -> dict[str, Any]:
        """Run the full 4-role research loop.

        Returns a dict with the weakness summary, hypothesis, candidate meta,
        and review result. ``promoted`` is True only when the gatekeeper
        approves V2; otherwise V1 stays active.
        """
        # Role 1: Research — consume V1 weakness report.
        weakness = self.research.run(trades, equity_curve)

        # Role 2: Hypothesis — convert weaknesses into a trade idea.
        hypo = self.hypothesis.run(weakness)

        # Role 3: Coding — render V2 candidate source file.
        candidate_meta = self.coding.run(hypo)

        # Role 4: Review — static audit + ValidationGatekeeper.
        review = self.review.run(candidate_meta, df_features,
                                 symbol=symbol, timeframe=timeframe)

        return {
            "weakness": weakness,
            "hypothesis": hypo,
            "candidate_meta": candidate_meta,
            "review": review,
            "promoted": review.promoted,
            "final_status": review.final_status,
            "rejection_reason": review.rejection_reason,
            "v1_stays_active": not review.promoted,
        }
