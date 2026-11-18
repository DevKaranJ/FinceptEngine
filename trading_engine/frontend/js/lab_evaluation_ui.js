/* js/lab_evaluation_ui.js — Strategy Lab: V1 vs V2, Heatmap, WFA, Equity Curve & Regime Diagnostics (Phase 6 / R5) */

(function () {
  "use strict";

  const elV1 = document.getElementById("lab-v1-metrics");
  const elV2 = document.getElementById("lab-v2-metrics");
  const elHeatmap = document.getElementById("lab-heatmap");
  const elWfa = document.getElementById("lab-wfa");
  const elStatus = document.getElementById("lab-status");
  const elEquityCurve = document.getElementById("lab-equity-curve");
  const elEquitySummary = document.getElementById("lab-equity-summary");
  const elRegimeDiagnostics = document.getElementById("lab-regime-diagnostics");
  const elRegimeStatus = document.getElementById("lab-regime-status");
  const elHeatmapTooltip = document.getElementById("heatmap-floating-tooltip");

  let cachedDiagnostics = null;

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
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function renderV1(reports) {
    let base = null;
    for (const r of (reports.reports || [])) {
      const oos = r.out_of_sample_metrics || {};
      if (oos.baseline) { base = oos.baseline; break; }
    }
    if (!base) {
      if (elV1) elV1.innerHTML = "<div class=\"muted small\">No baseline V1 metrics available yet.</div>";
      return;
    }
    const risk = base.candidate_risk || {};
    if (elV1) {
      elV1.innerHTML =
        metric("Total trades", base.total_trades) +
        metric("Win rate %", base.win_rate_pct != null ? base.win_rate_pct.toFixed(2) + "%" : "—") +
        metric("Profit factor", base.profit_factor, base.profit_factor >= 1.25 ? "ok" : "bad") +
        metric("Expectancy R", base.expectancy_r, base.expectancy_r > 0 ? "ok" : "bad") +
        metric("Net PnL", base.net_pnl != null ? "$" + base.net_pnl.toFixed(2) : "—") +
        metric("Max DD %", risk.max_drawdown_pct != null ? risk.max_drawdown_pct.toFixed(2) + "%" : "—",
          (risk.max_drawdown_pct != null && risk.max_drawdown_pct < 10) ? "ok" : "bad");
    }
  }

  function renderV2(reports) {
    const list = reports.reports || [];
    const latest = list[0];
    if (!latest || !latest.out_of_sample_metrics || !latest.out_of_sample_metrics.candidate) {
      if (elV2) elV2.innerHTML = "<div class=\"muted small\">No V2 candidate evaluated yet.</div>";
      return;
    }
    const c = latest.out_of_sample_metrics.candidate;
    const crisk = c.candidate_risk || {};
    const passCls = latest.final_status === "APPROVED" ? "ok" : "bad";
    if (elV2) {
      elV2.innerHTML =
        metric("Candidate", escapeHtml(latest.candidate_strategy_id), "neutral") +
        metric("Status", latest.final_status, passCls) +
        metric("Total trades", c.total_trades) +
        metric("Win rate %", c.win_rate_pct != null ? c.win_rate_pct.toFixed(2) + "%" : "—") +
        metric("Profit factor", c.profit_factor, c.profit_factor >= 1.25 ? "ok" : "bad") +
        metric("Expectancy R", c.expectancy_r, c.expectancy_r > 0 ? "ok" : "bad") +
        metric("Net PnL", c.net_pnl != null ? "$" + c.net_pnl.toFixed(2) : "—") +
        metric("Max DD %", crisk.max_drawdown_pct != null ? crisk.max_drawdown_pct.toFixed(2) + "%" : "—",
          (crisk.max_drawdown_pct != null && crisk.max_drawdown_pct < 10) ? "ok" : "bad") +
        "<div style=\"margin-top:8px;font-size:11px;color:#8a8a92;\">" +
        "OOS: " + (latest.oos_passed ? "PASS" : "FAIL") + " · " +
        "WFA: " + (latest.walk_forward_passed ? "PASS" : "FAIL") + " · " +
        "Heatmap: " + (latest.param_stability_passed ? "PASS" : "FAIL") + " · " +
        "Cost stress: " + (latest.cost_stress_passed ? "PASS" : "FAIL") +
        "</div>";
    }
  }

  function renderHeatmap(reports) {
    if (!elHeatmap) return;
    const list = reports.reports || [];
    const latest = list[0];
    if (!latest || !latest.parameter_heatmap || !latest.parameter_heatmap.cells || !latest.parameter_heatmap.cells.length) {
      elHeatmap.innerHTML = "<div class=\"muted small\">No heatmap data available yet. Trigger research loop to generate.</div>";
      return;
    }
    const hm = latest.parameter_heatmap;
    const p1 = hm.param_names && hm.param_names[0] ? hm.param_names[0] : "Param 1";
    const p2 = hm.param_names && hm.param_names[1] ? hm.param_names[1] : "Param 2";

    const cells = hm.cells || [];
    const p1vals = [...new Set(cells.map((c) => c.p1_value))].sort((a, b) => a - b);
    const p2vals = [...new Set(cells.map((c) => c.p2_value))].sort((a, b) => b - a);

    let html = "<div style='overflow-x:auto;'><table class='heatmap-table'>";
    html += "<thead><tr>";
    html += "<th class='heatmap-header-corner'>" + escapeHtml(p2) + " ↓ / " + escapeHtml(p1) + " →</th>";
    p1vals.forEach((v) => {
      html += "<th class='heatmap-header-col'>" + v + "</th>";
    });
    html += "</tr></thead><tbody>";

    p2vals.forEach((p2v) => {
      html += "<tr>";
      html += "<td class='heatmap-header-row'>" + p2v + "</td>";
      p1vals.forEach((p1v) => {
        const cell = cells.find((c) => c.p1_value === p1v && c.p2_value === p2v);
        if (cell) {
          const pf = Number(cell.profit_factor) || 0;
          let cellCls = cell.passed ? "cell-pass" : "cell-fail";
          if (pf >= 1.25) cellCls = "cell-pass";
          else if (pf >= 1.0) cellCls = "cell-mid";
          else cellCls = "cell-fail";

          let wrVal = "—";
          if (cell.win_rate_pct != null) {
            const rawWr = Number(cell.win_rate_pct);
            wrVal = isNaN(rawWr) ? cell.win_rate_pct : (rawWr <= 1.0 ? (rawWr * 100).toFixed(1) + "%" : rawWr.toFixed(1) + "%");
          } else if (cell.win_rate != null) {
            const rawWr = Number(cell.win_rate);
            wrVal = isNaN(rawWr) ? cell.win_rate : (rawWr <= 1.0 ? (rawWr * 100).toFixed(1) + "%" : rawWr.toFixed(1) + "%");
          }

          html += "<td class='heatmap-cell " + cellCls + "' " +
            "data-p1='" + escapeHtml(p1) + "' data-p1-val='" + cell.p1_value + "' " +
            "data-p2='" + escapeHtml(p2) + "' data-p2-val='" + cell.p2_value + "' " +
            "data-pf='" + pf.toFixed(2) + "' " +
            "data-er='" + (cell.expectancy_r != null ? Number(cell.expectancy_r).toFixed(3) : "—") + "' " +
            "data-trades='" + (cell.total_trades != null ? cell.total_trades : "—") + "' " +
            "data-wr='" + wrVal + "' " +
            "data-passed='" + (cell.passed ? "PASS" : "FAIL") + "'>" +
            pf.toFixed(2) + "</td>";
        } else {
          html += "<td class='heatmap-cell cell-empty'>—</td>";
        }
      });
      html += "</tr>";
    });
    html += "</tbody></table></div>";

    html += "<div class=\"heatmap-legend\">Pass ratio: " + (hm.pass_ratio * 100).toFixed(1) + "% · " +
      "Pass: " + hm.pass_count + "/" + hm.grid_size + " · " +
      (hm.passed ? "<span style='color:var(--bullish);font-weight:700;'>STABLE (APPROVED)</span>" : "<span style='color:var(--bearish);font-weight:700;'>UNSTABLE (REJECTED)</span>") +
      "</div>";

    elHeatmap.innerHTML = html;
    attachHeatmapTooltip();
  }

  function attachHeatmapTooltip() {
    if (!elHeatmap) return;
    const table = elHeatmap.querySelector(".heatmap-table");
    let tooltip = elHeatmapTooltip || document.getElementById("heatmap-floating-tooltip");
    if (!tooltip) {
      tooltip = document.createElement("div");
      tooltip.id = "heatmap-floating-tooltip";
      tooltip.className = "heatmap-tooltip-card";
      document.body.appendChild(tooltip);
    }

    if (!table) return;

    table.addEventListener("mouseover", (e) => {
      const td = e.target.closest("td.heatmap-cell");
      if (!td || !td.dataset.pf) return;
      const p1 = td.dataset.p1;
      const p1v = td.dataset.p1Val;
      const p2 = td.dataset.p2;
      const p2v = td.dataset.p2Val;
      const pf = td.dataset.pf;
      const er = td.dataset.er;
      const trades = td.dataset.trades;
      const wr = td.dataset.wr;
      const passed = td.dataset.passed;

      const isPass = passed === "PASS";
      const pfNum = parseFloat(pf) || 0;
      const pfColor = pfNum >= 1.25 ? "var(--bullish)" : pfNum >= 1.0 ? "var(--warning)" : "var(--bearish)";

      tooltip.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;border-bottom:1px solid var(--border);padding-bottom:4px;">
          <span style="font-weight:700;color:var(--text-muted);font-size:10px;text-transform:uppercase;">PERTURBED PARAMETERS</span>
          <span class="heatmap-badge ${isPass ? 'pass' : 'fail'}">${passed}</span>
        </div>
        <div style="display:flex;justify-content:space-between;gap:12px;margin:2px 0;"><span style="color:var(--text-muted);">${escapeHtml(p1)}:</span> <span style="font-weight:700;color:var(--info);">${p1v}</span></div>
        <div style="display:flex;justify-content:space-between;gap:12px;margin:2px 0;"><span style="color:var(--text-muted);">${escapeHtml(p2)}:</span> <span style="font-weight:700;color:var(--info);">${p2v}</span></div>
        <div style="border-top:1px solid var(--border-subtle);margin:6px 0;"></div>
        <div style="display:flex;justify-content:space-between;gap:12px;margin:2px 0;"><span style="color:var(--text-muted);">Profit Factor:</span> <span style="font-weight:700;color:${pfColor};">${pf}</span></div>
        <div style="display:flex;justify-content:space-between;gap:12px;margin:2px 0;"><span style="color:var(--text-muted);">Win Rate:</span> <span style="font-weight:700;color:var(--text-primary);">${wr !== "—" ? (String(wr).endsWith("%") ? wr : wr + "%") : "—"}</span></div>
        <div style="display:flex;justify-content:space-between;gap:12px;margin:2px 0;"><span style="color:var(--text-muted);">Expectancy R:</span> <span style="font-weight:700;color:${parseFloat(er) > 0 ? 'var(--bullish)' : 'var(--bearish)'};">${er}R</span></div>
        <div style="display:flex;justify-content:space-between;gap:12px;margin:2px 0;"><span style="color:var(--text-muted);">Total Trades:</span> <span style="font-weight:700;color:var(--text-primary);">${trades}</span></div>
      `;
      tooltip.style.display = "block";
      updateTooltipPos(e, tooltip);
    });

    table.addEventListener("mousemove", (e) => {
      const td = e.target.closest("td.heatmap-cell");
      if (!td || !td.dataset.pf) return;
      updateTooltipPos(e, tooltip);
    });

    table.addEventListener("mouseout", (e) => {
      const td = e.target.closest("td.heatmap-cell");
      if (!td) return;
      tooltip.style.display = "none";
    });
  }

  function updateTooltipPos(e, tooltip) {
    if (!tooltip || tooltip.style.display === "none") return;
    const pad = 14;
    let x = e.clientX + pad;
    let y = e.clientY - 20;
    const tw = 220;
    const th = 150;
    if (x + tw > window.innerWidth - 10) x = e.clientX - tw - pad;
    if (x < 10) x = 10;
    if (y + th > window.innerHeight - 10) y = window.innerHeight - th - 10;
    if (y < 10) y = 10;
    tooltip.style.left = x + "px";
    tooltip.style.top = y + "px";
  }

  function renderWfa(reports) {
    if (!elWfa) return;
    const list = reports.reports || [];
    const latest = list[0];
    if (!latest || !latest.walk_forward_summary || !latest.walk_forward_summary.windows || !latest.walk_forward_summary.windows.length) {
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

  function renderEquityCurve(diagnostics) {
    if (!elEquityCurve) return;
    const points = (diagnostics && diagnostics.equity_curve) || [];
    if (!points || points.length <= 1) {
      elEquityCurve.innerHTML =
        "<div style=\"display:flex;flex-direction:column;align-items:center;justify-content:center;height:180px;color:var(--text-muted);font-size:12px;\">" +
        "<span style=\"font-size:14px;margin-bottom:6px;color:var(--text-primary);\">📈 Equity Curve Awaiting Trades</span>" +
        "<span>No closed trades recorded yet for " + escapeHtml((diagnostics && diagnostics.strategy_id) || "BASELINE_DEMO_V1") + ".</span>" +
        "<span style=\"font-size:11px;margin-top:4px;color:var(--text-muted);\">Execute manual orders or run research backtests to stream the cumulative equity curve and drawdown fill.</span>" +
        "</div>";
      if (elEquitySummary) elEquitySummary.textContent = "Starting: $10,000.00 · Closed Trades: 0";
      return;
    }

    let runningMax = points[0].equity;
    const data = points.map((pt, idx) => {
      const eq = Number(pt.equity);
      if (eq > runningMax) runningMax = eq;
      const ddAmount = runningMax - eq;
      const ddPct = runningMax > 0 ? (ddAmount / runningMax) * 100 : 0;
      return {
        t: pt.t,
        equity: eq,
        hwm: runningMax,
        drawdownAmount: ddAmount,
        drawdownPct: ddPct,
        index: idx,
      };
    });

    const startEquity = data[0].equity;
    const currentEquity = data[data.length - 1].equity;
    const peakEquity = Math.max(...data.map((d) => d.hwm));
    const maxDdPct = Math.max(...data.map((d) => d.drawdownPct));
    const netReturnPct = startEquity > 0 ? ((currentEquity - startEquity) / startEquity) * 100 : 0;

    if (elEquitySummary) {
      const returnColor = netReturnPct >= 0 ? "var(--bullish)" : "var(--bearish)";
      elEquitySummary.innerHTML =
        "<span style=\"color:var(--text-muted);\">Start:</span> $" + startEquity.toFixed(2) + " · " +
        "<span style=\"color:var(--text-muted);\">Current:</span> <span style=\"color:" + returnColor + ";font-weight:700;\">$" +
        currentEquity.toFixed(2) + " (" + (netReturnPct >= 0 ? "+" : "") + netReturnPct.toFixed(2) + "%)</span> · " +
        "<span style=\"color:var(--text-muted);\">Peak:</span> $" + peakEquity.toFixed(2) + " · " +
        "<span style=\"color:var(--text-muted);\">Max DD:</span> <span style=\"color:var(--bearish);font-weight:700;\">-" + maxDdPct.toFixed(2) + "%</span>";
    }

    const W = 800;
    const H = 220;
    const padTop = 18;
    const padBottom = 26;
    const padLeft = 10;
    const padRight = 70;
    const plotW = W - padLeft - padRight;
    const plotH = H - padTop - padBottom;

    const minEq = Math.min(...data.map((d) => d.equity));
    const maxEq = Math.max(...data.map((d) => d.hwm));
    let span = maxEq - minEq;
    if (span <= 0) span = maxEq * 0.05 || 100;
    const yMin = minEq - span * 0.08;
    const yMax = maxEq + span * 0.08;
    const ySpan = yMax - yMin;

    function getX(idx) {
      if (data.length <= 1) return padLeft + plotW / 2;
      return padLeft + (idx / (data.length - 1)) * plotW;
    }
    function getY(val) {
      return padTop + (1 - (val - yMin) / ySpan) * plotH;
    }

    const equityPoints = data.map((d, i) => getX(i).toFixed(1) + "," + getY(d.equity).toFixed(1));
    const hwmPoints = data.map((d, i) => getX(i).toFixed(1) + "," + getY(d.hwm).toFixed(1));

    const equityPathStr = "M " + equityPoints.join(" L ");
    const hwmPathStr = "M " + hwmPoints.join(" L ");
    const drawdownPathStr = "M " + hwmPoints.join(" L ") + " L " + equityPoints.slice().reverse().join(" L ") + " Z";

    let gridLinesSvg = "";
    let yLabelsSvg = "";
    const numTicks = 4;
    for (let k = 0; k <= numTicks; k++) {
      const tickVal = yMin + (k / numTicks) * ySpan;
      const yPos = getY(tickVal);
      gridLinesSvg += "<line x1=\"" + padLeft + "\" y1=\"" + yPos.toFixed(1) + "\" x2=\"" + (padLeft + plotW).toFixed(1) + "\" y2=\"" + yPos.toFixed(1) + "\" stroke=\"var(--border-subtle)\" stroke-width=\"1\" stroke-dasharray=\"2,3\"/>";
      yLabelsSvg += "<text x=\"" + (padLeft + plotW + 6).toFixed(1) + "\" y=\"" + (yPos + 3).toFixed(1) + "\" fill=\"var(--text-muted)\" font-size=\"10\" font-family=\"monospace\">$" + tickVal.toFixed(0) + "</text>";
    }

    let xLabelsSvg = "";
    const xStep = Math.max(1, Math.floor((data.length - 1) / 3));
    for (let i = 0; i < data.length; i += xStep) {
      const xPos = getX(i);
      const ts = data[i].t;
      let label = "T" + i;
      if (ts) {
        const d = new Date(typeof ts === "number" && ts < 1e11 ? ts * 1000 : ts);
        if (!isNaN(d.getTime())) {
          label = d.toISOString().substring(11, 16);
        }
      }
      xLabelsSvg += "<text x=\"" + xPos.toFixed(1) + "\" y=\"" + (H - 8).toFixed(1) + "\" fill=\"var(--text-muted)\" font-size=\"10\" font-family=\"monospace\" text-anchor=\"middle\">" + label + "</text>";
    }

    const svgHtml =
      "<svg viewBox=\"0 0 " + W + " " + H + "\" preserveAspectRatio=\"none\" style=\"width:100%;height:220px;display:block;\" id=\"equity-svg\">" +
      "<defs>" +
      "<linearGradient id=\"drawdownGradient\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">" +
      "<stop offset=\"0%\" stop-color=\"#ff5252\" stop-opacity=\"0.35\"/>" +
      "<stop offset=\"100%\" stop-color=\"#ff5252\" stop-opacity=\"0.06\"/>" +
      "</linearGradient>" +
      "</defs>" +
      gridLinesSvg +
      yLabelsSvg +
      xLabelsSvg +
      "<path d=\"" + drawdownPathStr + "\" fill=\"url(#drawdownGradient)\" stroke=\"none\"/>" +
      "<path d=\"" + hwmPathStr + "\" fill=\"none\" stroke=\"var(--bullish)\" stroke-width=\"1.5\" stroke-dasharray=\"4,3\" opacity=\"0.85\"/>" +
      "<path d=\"" + equityPathStr + "\" fill=\"none\" stroke=\"var(--info)\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>" +
      "<line id=\"crosshair-v\" x1=\"0\" y1=\"" + padTop + "\" x2=\"0\" y2=\"" + (padTop + plotH) + "\" stroke=\"var(--text-muted)\" stroke-width=\"1\" stroke-dasharray=\"3,3\" style=\"display:none;\"/>" +
      "<circle id=\"crosshair-dot-eq\" r=\"4.5\" fill=\"var(--info)\" stroke=\"#ffffff\" stroke-width=\"1.5\" style=\"display:none;\"/>" +
      "<circle id=\"crosshair-dot-hwm\" r=\"3.5\" fill=\"var(--bullish)\" stroke=\"#ffffff\" stroke-width=\"1\" style=\"display:none;\"/>" +
      "<rect id=\"crosshair-overlay\" x=\"" + padLeft + "\" y=\"" + padTop + "\" width=\"" + plotW + "\" height=\"" + plotH + "\" fill=\"transparent\" style=\"cursor:crosshair;\"/>" +
      "</svg>" +
      "<div id=\"equity-tooltip\" class=\"equity-crosshair-tooltip\" style=\"display:none;\"></div>";

    elEquityCurve.innerHTML = svgHtml;

    const overlay = elEquityCurve.querySelector("#crosshair-overlay");
    const lineV = elEquityCurve.querySelector("#crosshair-v");
    const dotEq = elEquityCurve.querySelector("#crosshair-dot-eq");
    const dotHwm = elEquityCurve.querySelector("#crosshair-dot-hwm");
    const tooltip = elEquityCurve.querySelector("#equity-tooltip");

    if (overlay) {
      overlay.addEventListener("mousemove", (e) => {
        const rect = overlay.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const ratio = Math.max(0, Math.min(1, mouseX / rect.width));
        const idx = Math.min(data.length - 1, Math.round(ratio * (data.length - 1)));
        const d = data[idx];

        const xSvg = getX(idx);
        const ySvgEq = getY(d.equity);
        const ySvgHwm = getY(d.hwm);

        lineV.setAttribute("x1", xSvg);
        lineV.setAttribute("x2", xSvg);
        lineV.style.display = "";

        dotEq.setAttribute("cx", xSvg);
        dotEq.setAttribute("cy", ySvgEq);
        dotEq.style.display = "";

        dotHwm.setAttribute("cx", xSvg);
        dotHwm.setAttribute("cy", ySvgHwm);
        dotHwm.style.display = "";

        let timeStr = "Trade #" + (idx + 1);
        if (d.t) {
          const dt = new Date(typeof d.t === "number" && d.t < 1e11 ? d.t * 1000 : d.t);
          if (!isNaN(dt.getTime())) timeStr = dt.toUTCString().replace("GMT", "UTC");
        }

        tooltip.innerHTML =
          "<div style=\"font-weight:700;color:var(--text-primary);margin-bottom:4px;border-bottom:1px solid var(--border);padding-bottom:3px;\">" + escapeHtml(timeStr) + "</div>" +
          "<div style=\"display:flex;justify-content:space-between;gap:12px;margin:2px 0;\"><span style=\"color:var(--text-muted);\">Equity:</span> <span style=\"color:var(--info);font-weight:700;\">$" + d.equity.toFixed(2) + "</span></div>" +
          "<div style=\"display:flex;justify-content:space-between;gap:12px;margin:2px 0;\"><span style=\"color:var(--text-muted);\">Peak (HWM):</span> <span style=\"color:var(--bullish);\">$" + d.hwm.toFixed(2) + "</span></div>" +
          "<div style=\"display:flex;justify-content:space-between;gap:12px;margin:2px 0;\"><span style=\"color:var(--text-muted);\">Drawdown:</span> <span style=\"color:" + (d.drawdownPct > 0 ? "var(--bearish)" : "var(--text-muted)") + ";font-weight:700;\">-" + d.drawdownPct.toFixed(2) + "% (-$" + d.drawdownAmount.toFixed(2) + ")</span></div>";
        tooltip.style.display = "block";

        const cRect = elEquityCurve.getBoundingClientRect();
        let left = e.clientX - cRect.left + 14;
        let top = e.clientY - cRect.top - 20;
        if (left + 220 > cRect.width) left = left - 240;
        if (top < 10) top = 10;
        tooltip.style.left = left + "px";
        tooltip.style.top = top + "px";
      });

      overlay.addEventListener("mouseleave", () => {
        lineV.style.display = "none";
        dotEq.style.display = "none";
        dotHwm.style.display = "none";
        tooltip.style.display = "none";
      });
    }
  }

  function renderRegimeDiagnostics(diagnostics) {
    if (!elRegimeDiagnostics) return;
    const regimes = (diagnostics && diagnostics.regime_breakdown) || {};
    const weaknesses = (diagnostics && diagnostics.weaknesses) || [];
    const report = (diagnostics && diagnostics.weakness_report) || {};

    let html = "";

    // 1. Volatility Regime Table
    const regimeKeys = Object.keys(regimes);
    html += "<div class=\"regime-header-title\">VOLATILITY REGIME BREAKDOWN</div>";
    if (regimeKeys.length === 0) {
      html += "<div class=\"muted small\" style=\"margin-bottom:12px;\">No regime breakdown available yet (requires closed trades with regime snapshots).</div>";
    } else {
      html += "<div style='overflow-x:auto;margin-bottom:14px;'><table class='regime-table'>";
      html += "<thead><tr>";
      html += "<th style='text-align:left;'>REGIME</th>";
      html += "<th>TRADES</th>";
      html += "<th>WIN RATE</th>";
      html += "<th>PROFIT FACTOR</th>";
      html += "<th>EXPECTANCY R</th>";
      html += "<th>NET PNL</th>";
      html += "<th>STATUS</th>";
      html += "</tr></thead><tbody>";

      regimeKeys.forEach((k) => {
        const reg = regimes[k] || {};
        const isLosing = reg.is_losing_regime === true;
        const netPnl = Number(reg.net_pnl) || 0;
        const pnlCls = netPnl > 0 ? "ok" : netPnl < 0 ? "bad" : "neutral";
        const wr = reg.win_rate_pct != null ? reg.win_rate_pct.toFixed(1) + "%" : "—";
        const pf = reg.profit_factor != null ? reg.profit_factor.toFixed(2) : "—";
        const er = reg.expectancy_r != null ? reg.expectancy_r.toFixed(3) + "R" : "—";
        const tr = reg.trade_count != null ? reg.trade_count : (reg.trades != null ? reg.trades : "—");

        html += "<tr class='" + (isLosing ? "row-losing-regime" : "") + "'>";
        html += "<td style='text-align:left;font-weight:700;'><span class='regime-indicator " + (isLosing ? "indicator-bad" : "indicator-ok") + "'></span>" + escapeHtml(k) + "</td>";
        html += "<td>" + tr + "</td>";
        html += "<td>" + wr + "</td>";
        html += "<td>" + pf + "</td>";
        html += "<td>" + er + "</td>";
        html += "<td class='metric-v " + pnlCls + "'>" + (netPnl >= 0 ? "+$" : "-$") + Math.abs(netPnl).toFixed(2) + "</td>";
        html += "<td><span class='badge " + (isLosing ? "badge-regime-losing" : "badge-regime-ok") + "'>" + (isLosing ? "LOSING REGIME" : "STABLE") + "</span></td>";
        html += "</tr>";
      });
      html += "</tbody></table></div>";
    }

    // 2. Root Cause Weakness Banners
    html += "<div class=\"regime-header-title\" style=\"margin-top:14px;\">DIAGNOSTIC ROOT-CAUSE ANALYSIS &amp; V2 GATING FLAGS</div>";
    if (weaknesses.length === 0) {
      html +=
        "<div class=\"weakness-banner banner-accept\">" +
        "<div class=\"banner-icon\">✓</div>" +
        "<div class=\"banner-content\">" +
        "<div class=\"banner-header\"><span class=\"banner-flag\">NO SYSTEMIC REGIME WEAKNESSES DETECTED</span><span class=\"badge badge-rec-accept\">REC: ACCEPT</span></div>" +
        "<div class=\"banner-detail\">Strategy exhibits healthy expectancy and risk control across all evaluated volatility conditions.</div>" +
        "</div></div>";
    } else {
      weaknesses.forEach((w) => {
        const sev = (w.severity || "LOW").toUpperCase();
        const rec = (w.recommendation || "ACCEPT").toUpperCase();
        let bannerCls = sev === "HIGH" ? "banner-high" : sev === "MEDIUM" ? "banner-medium" : "banner-low";
        let icon = sev === "HIGH" ? "⚠️" : sev === "MEDIUM" ? "⚡" : "ℹ️";
        let remedy = getRemedyText(w.flag);

        html +=
          "<div class=\"weakness-banner " + bannerCls + "\">" +
          "<div class=\"banner-icon\">" + icon + "</div>" +
          "<div class=\"banner-content\">" +
          "<div class=\"banner-header\">" +
          "<span class=\"banner-flag\">" + escapeHtml(w.flag) + "</span>" +
          "<span class=\"badge badge-sev-" + sev.toLowerCase() + "\">" + sev + " SEVERITY</span>" +
          "<span class=\"badge badge-rec-" + rec.toLowerCase() + "\">REC: " + rec + "</span>" +
          "</div>" +
          "<div class=\"banner-detail\">" + escapeHtml(w.detail || w.flag) + "</div>" +
          "<div class=\"banner-remedy\"><strong>Remediation:</strong> " + escapeHtml(remedy) + "</div>" +
          "</div></div>";
      });
    }

    if (elRegimeStatus && report.recommendation) {
      elRegimeStatus.textContent = "Recommendation: " + report.recommendation + " (" + (weaknesses.length) + " flags)";
    }

    elRegimeDiagnostics.innerHTML = html;
  }

  function getRemedyText(flag) {
    if (!flag) return "Review strategy execution logs.";
    if (flag.indexOf("LOSING_REGIMES:") >= 0) {
      return "Strategy suffers from adverse selection in this regime. Add an ATR volatility gate or session filter prior to signal generation.";
    }
    if (flag === "STOPS_TOO_TIGHT") {
      return "Over 40% of stopped-out trades reached positive MFE before stop hit. Widen ATR stop multiplier (e.g. from 1.5x to 2.0x).";
    }
    if (flag === "HIGH_COST_DRAG") {
      return "Execution costs exceed 20% of gross profits. Increase target R:R ratio or transition from market orders to passive limit fills.";
    }
    if (flag === "LOW_PROFIT_FACTOR") {
      return "Gross profits do not sufficiently cover gross losses. Tighten entry triggers or enforce higher R:R confirmation.";
    }
    if (flag === "NEGATIVE_EXPECTANCY") {
      return "Mathematical expectancy per trade is zero or negative. Discard or refactor entry and exit rules.";
    }
    if (flag === "HIGH_DRAWDOWN") {
      return "Maximum drawdown exceeds 15%. Reduce position risk per trade from 1.0% to 0.5% or activate daily loss circuit breaker.";
    }
    return "Check parameter sensitivity and out-of-sample consistency.";
  }

  window.labUI = {
    render(reports, diagnostics) {
      reports = reports || { reports: [] };
      renderV1(reports);
      renderV2(reports);
      renderHeatmap(reports);
      renderWfa(reports);

      if (diagnostics) {
        cachedDiagnostics = diagnostics;
      }
      renderEquityCurve(cachedDiagnostics);
      renderRegimeDiagnostics(cachedDiagnostics);
    },
    renderEquityCurve(diagnostics) {
      if (diagnostics) cachedDiagnostics = diagnostics;
      renderEquityCurve(cachedDiagnostics);
    },
    renderRegimeDiagnostics(diagnostics) {
      if (diagnostics) cachedDiagnostics = diagnostics;
      renderRegimeDiagnostics(cachedDiagnostics);
    },
  };

})();
