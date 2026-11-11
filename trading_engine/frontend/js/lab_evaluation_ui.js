/* js/lab_evaluation_ui.js — Strategy Lab: V1 vs V2, heatmap, WFA curves (Phase 6) */

(function () {
  "use strict";

  const elV1 = document.getElementById("lab-v1-metrics");
  const elV2 = document.getElementById("lab-v2-metrics");
  const elHeatmap = document.getElementById("lab-heatmap");
  const elWfa = document.getElementById("lab-wfa");
  const elStatus = document.getElementById("lab-status");

  function metric(label, value, cls) {
    return "<div class=\"metric-row\">" +
      "<span class=\"metric-k\">" + escapeHtml(label) + "</span>" +
      "<span class=\"metric-v " + (cls || "") + "\">" + fmt(value) + "</span>" +
      "</div>";
  }

  function fmt(v) {
    if (v === null || v === undefined) return "—";
    if (typeof v === "number") {
      if (!Number.isFinite(v)) return v > 0 ? "∞" : "−∞";
      return Number(v).toFixed(4);
    }
    return String(v);
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderV1(reports) {
    // V1 = baseline metrics from the latest report's out_of_sample baseline block.
    let base = null;
    for (const r of (reports.reports || [])) {
      const oos = r.out_of_sample_metrics || {};
      if (oos.baseline) { base = oos.baseline; break; }
    }
    if (!base) {
      elV1.innerHTML = "<div class=\"muted small\">No baseline V1 metrics available yet.</div>";
      return;
    }
    const risk = base.candidate_risk || {};
    elV1.innerHTML =
      metric("Total trades", base.total_trades) +
      metric("Win rate %", base.win_rate_pct) +
      metric("Profit factor", base.profit_factor, base.profit_factor >= 1.25 ? "ok" : "bad") +
      metric("Expectancy R", base.expectancy_r, base.expectancy_r > 0 ? "ok" : "bad") +
      metric("Net PnL", base.net_pnl) +
      metric("Max DD %", risk.max_drawdown_pct != null ? risk.max_drawdown_pct : "—",
        (risk.max_drawdown_pct != null && risk.max_drawdown_pct < 10) ? "ok" : "bad");
  }

  function renderV2(reports) {
    const list = reports.reports || [];
    const latest = list[0];
    if (!latest || !latest.out_of_sample_metrics || !latest.out_of_sample_metrics.candidate) {
      elV2.innerHTML = "<div class=\"muted small\">No V2 candidate evaluated yet.</div>";
      return;
    }
    const c = latest.out_of_sample_metrics.candidate;
    const crisk = c.candidate_risk || {};
    const passCls = latest.final_status === "APPROVED" ? "ok" : "bad";
    elV2.innerHTML =
      metric("Candidate", escapeHtml(latest.candidate_strategy_id), "neutral") +
      metric("Status", latest.final_status, passCls) +
      metric("Total trades", c.total_trades) +
      metric("Win rate %", c.win_rate_pct) +
      metric("Profit factor", c.profit_factor, c.profit_factor >= 1.25 ? "ok" : "bad") +
      metric("Expectancy R", c.expectancy_r, c.expectancy_r > 0 ? "ok" : "bad") +
      metric("Net PnL", c.net_pnl) +
      metric("Max DD %", crisk.max_drawdown_pct != null ? crisk.max_drawdown_pct : "—",
        (crisk.max_drawdown_pct != null && crisk.max_drawdown_pct < 10) ? "ok" : "bad") +
      "<div style=\"margin-top:8px;font-size:11px;color:#8a8a92;\">" +
      "OOS: " + (latest.oos_passed ? "PASS" : "FAIL") + " · " +
      "WFA: " + (latest.walk_forward_passed ? "PASS" : "FAIL") + " · " +
      "Heatmap: " + (latest.param_stability_passed ? "PASS" : "FAIL") + " · " +
      "Cost stress: " + (latest.cost_stress_passed ? "PASS" : "FAIL") +
      "</div>";
  }

  function renderHeatmap(reports) {
    const list = reports.reports || [];
    const latest = list[0];
    if (!latest || !latest.parameter_heatmap || !latest.parameter_heatmap.cells.length) {
      elHeatmap.innerHTML = "<div class=\"muted small\">No heatmap data available yet.</div>";
      return;
    }
    const hm = latest.parameter_heatmap;
    const p1 = hm.param_names && hm.param_names[0] ? hm.param_names[0] : "Param 1";
    const p2 = hm.param_names && hm.param_names[1] ? hm.param_names[1] : "Param 2";

    // Build grid: rows = p2 values (descending), cols = p1 values
    const cells = hm.cells || [];
    const p1vals = [...new Set(cells.map((c) => c.p1_value))].sort((a, b) => a - b);
    const p2vals = [...new Set(cells.map((c) => c.p2_value))].sort((a, b) => b - a);

    let html = "<table style='width:100%;border-collapse:collapse;font-size:11px;text-align:center;'>";
    // header row
    html += "<thead><tr>";
    html += "<th style='padding:4px 2px;border:1px solid #333;background:#1a1a1e;color:#8a8a92;' class='header-cell'>" + escapeHtml(p2) + " ↓ / " + escapeHtml(p1) + " →</th>";
    p1vals.forEach((v) => {
      html += "<th style='padding:4px 2px;border:1px solid #333;background:#141416;color:#7dd3fc;' class='header-cell'>" + v + "</th>";
    });
    html += "</tr></thead><tbody>";
    p2vals.forEach((p2v) => {
      html += "<tr>";
      html += "<td style='padding:4px 2px;border:1px solid #333;background:#141416;color:#8a8a92;' class='header-cell'>" + p2v + "</td>";
      p1vals.forEach((p1v) => {
        const cell = cells.find((c) => c.p1_value === p1v && c.p2_value === p2v);
        if (cell) {
          const cls = cell.passed ? "pass" : "fail";
          html += "<td class=\"cell " + cls + "\" title=\"PF " + cell.profit_factor + " · ER " + cell.expectancy_r + " · T " + cell.total_trades + "\">" +
            cell.profit_factor.toFixed(2) + "</td>";
        } else {
          html += "<td class=\"cell\" style='background:#141416;color:#444;border:1px solid #1a1a1e;'>—</td>";
        }
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    html += "<div class=\"heatmap-legend\">Pass ratio: " + (hm.pass_ratio * 100).toFixed(1) + "% · " +
      "Pass: " + hm.pass_count + "/" + hm.grid_size + " · " +
      (hm.passed ? "<span style='color:#7ee287;font-weight:700;'>STABLE</span>" : "<span style='color:#ff9a8a;font-weight:700;'>UNSTABLE</span>") +
      "</div>";
    elHeatmap.innerHTML = html;
  }

  function renderWfa(reports) {
    const list = reports.reports || [];
    const latest = list[0];
    if (!latest || !latest.walk_forward_summary || !latest.walk_forward_summary.windows.length) {
      elWfa.innerHTML = "<div class=\"muted small\">No walk-forward data available yet.</div>";
      return;
    }
    const wf = latest.walk_forward_summary;
    const profitable = wf.profitable_windows || 0;
    const total = wf.total_windows || 0;
    const passCls = profitable >= Math.ceil(total * 0.8) ? "ok" : "bad";
    let html =
      "<div class=\"metric-row\"><span class=\"metric-k\">Profitable windows</span>" +
      "<span class=\"metric-v " + passCls + "\">" + profitable + " / " + total + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Required (≥80%)</span>" +
      "<span class=\"metric-v\">" + wf.required + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Status</span>" +
      "<span class=\"metric-v " + passCls + "\">" + (wf.passed ? "PASS" : "FAIL") + "</span></div>" +
      "<div class=\"wfa-window\" style=\"margin-top:10px;\">";
    (wf.windows || []).forEach((win) => {
      const erCls = win.expectancy_r > 0 ? "ok" : "bad";
      html += "<div class=\"wfa-row\">" +
        "<span>Window " + win.window + "</span>" +
        "<span>ER " + win.expectancy_r.toFixed(3) + "R</span>" +
        "<span class=\"" + erCls + "\">" + (win.profitable ? "profitable" : "loss") + "</span>" +
        "</div>";
    });
    html += "</div>";
    elWfa.innerHTML = html;
  }

  window.labUI = {
    render(reports) {
      reports = reports || { reports: [] };
      renderV1(reports);
      renderV2(reports);
      renderHeatmap(reports);
      renderWfa(reports);
    },
  };

})();
