/* js/system_monitor_ui.js — System Status Monitor + Intelligent 1-Click Manual Order Ticket (R4) */

(function () {
  "use strict";

  const elGrid = document.getElementById("monitor-grid");
  const elActivityList = document.getElementById("activity-list");
  const elManualTicket = document.getElementById("manual-ticket");
  const elTicketLastBody = document.getElementById("ticket-last-body");
  const elOrderTicketPanel = document.getElementById("order-ticket-panel");

  // --- Monitor cards -------------------------------------------------------
  function renderMonitor(snapshot) {
    if (!elGrid) return;
    const feeds = snapshot.connected_feeds || [];
    const uptime = Number(snapshot.uptime_s || 0);
    const status = snapshot.status || "IDLE";

    const cards = [
      { label: "Engine Status", value: status,
        cls: status === "RUNNING" ? "ok" : (status === "IDLE" ? "neutral" : "bad") },
      { label: "Uptime (s)", value: uptime.toFixed(1), cls: "neutral" },
      { label: "Feeds", value: feeds.length, cls: feeds.length > 0 ? "ok" : "bad" },
      { label: "Strategies Tested", value: snapshot.total_strategies_tested || 0, cls: "neutral" },
      { label: "Approved (V2)", value: snapshot.approved_count || 0, cls: "ok" },
      { label: "Open Positions", value: Object.keys(snapshot.positions || {}).length, cls: "neutral" },
      { label: "Last Candle", value: snapshot.last_candle ? (snapshot.last_candle.symbol || snapshot.last_candle.s || "—") : "—", cls: "neutral" },
      { label: "Pending Ticket", value: snapshot.pending_manual_ticket ? "OPEN" : "—",
        cls: snapshot.pending_manual_ticket ? "bad" : "neutral" },
    ];

    elGrid.innerHTML = cards.map((c) =>
      "<div class=\"mon-card\">" +
      "<div class=\"mon-label\">" + escapeHtml(c.label) + "</div>" +
      "<div class=\"mon-value " + c.cls + "\">" + escapeHtml(c.value) + "</div>" +
      "</div>"
    ).join("");
  }

  function renderActivity(activity) {
    if (!elActivityList) return;
    elActivityList.innerHTML = "";
    (activity || []).slice(0, 25).forEach((a) => {
      const div = document.createElement("div");
      div.className = "activity-row";
      div.innerHTML =
        "<span class=\"ts\">" + escapeHtml(a.timestamp_utc) + "</span>" +
        "<span class=\"comp\">[" + escapeHtml(a.component) + "]</span>" +
        "<span class=\"evt\">" + escapeHtml(a.event_type) + "</span>" +
        "<span class=\"sum\">" + escapeHtml(a.summary) + "</span>";
      elActivityList.appendChild(div);
    });
  }

  // --- Manual Order Ticket form (R4 Intelligent Risk Manager) --------------
  function buildTicketForm() {
    const elContainer = elOrderTicketPanel || document.getElementById("order-ticket-panel");
    if (!elContainer) return;

    const formHtml = `
      <div class="panel-header">
        <span class="panel-title">1-CLICK MANUAL ORDER TICKET // RISK GATE</span>
        <div style="display:flex;align-items:center;gap:10px;">
          <span class="ticket-risk-badge badge-neutral" id="ticket-rr-badge">AWAITING INPUTS</span>
          <span class="muted small">Paper / Manual Execution</span>
        </div>
      </div>
      <form id="manual-ticket-form" class="order-ticket-form">
        <!-- Row 1: Capital & Risk % -->
        <div class="form-group">
          <label for="ticket-capital">Capital ($)</label>
          <input id="ticket-capital" name="capital" type="number" step="any" min="1" value="10000" class="ticket-input">
        </div>
        <div class="form-group">
          <label for="ticket-risk-pct">Risk (%)</label>
          <input id="ticket-risk-pct" name="risk_pct" type="number" step="0.1" min="0.01" max="100" value="1.0" class="ticket-input">
        </div>

        <!-- Row 2: Symbol, Timeframe, Direction -->
        <div class="form-group">
          <label for="ticket-symbol">Symbol</label>
          <select id="ticket-symbol" name="symbol" class="ticket-select">
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
            <option value="SOLUSDT">SOLUSDT</option>
          </select>
        </div>
        <div class="form-group">
          <label for="ticket-timeframe">Timeframe</label>
          <select id="ticket-timeframe" name="timeframe" class="ticket-select">
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
          </select>
        </div>
        <div class="form-group span-2">
          <label>Direction</label>
          <div class="direction-toggle-group">
            <button type="button" class="dir-btn dir-long active" data-direction="LONG" id="btn-dir-long">LONG</button>
            <button type="button" class="dir-btn dir-short" data-direction="SHORT" id="btn-dir-short">SHORT</button>
          </div>
          <input type="hidden" name="direction" id="ticket-direction" value="LONG">
        </div>

        <!-- Row 3: Entry Price, Stop Loss (+ ATR buffer button) -->
        <div class="form-group">
          <div class="label-with-action">
            <label for="ticket-entry">Entry Price</label>
            <button type="button" class="btn-link" id="btn-use-last-price">Use Last Price</button>
          </div>
          <input id="ticket-entry" name="entry_price" type="number" step="any" placeholder="e.g. 68000.00" class="ticket-input">
        </div>
        <div class="form-group">
          <div class="label-with-action">
            <label for="ticket-stop">Stop Loss</label>
            <button type="button" class="btn-atr-buffer" id="btn-atr-buffer" title="Auto-fill SL, TP1, and TP2 using 1.5x ATR">⚡ 1-Click ATR Buffer (1.5x)</button>
          </div>
          <input id="ticket-stop" name="stop_loss" type="number" step="any" placeholder="e.g. 67800.00" class="ticket-input">
        </div>

        <!-- Row 4: Target 1, Target 2 -->
        <div class="form-group">
          <label for="ticket-target-1">Target 1 (1.5x R:R Gate)</label>
          <input id="ticket-target-1" name="target_1_price" type="number" step="any" placeholder="e.g. 68350.00" class="ticket-input">
        </div>
        <div class="form-group">
          <label for="ticket-target-2">Target 2 (Runner / 3.0x)</label>
          <input id="ticket-target-2" name="target_2_price" type="number" step="any" placeholder="optional e.g. 68600.00" class="ticket-input">
        </div>

        <!-- Row 5: Dynamic Position Sizing Readout -->
        <div class="sizing-readout-card span-2">
          <div class="sizing-stat">
            <span class="stat-label">CALCULATED UNITS</span>
            <span class="stat-val" id="calc-units">0.0000</span>
          </div>
          <div class="sizing-stat">
            <span class="stat-label">DOLLAR RISK</span>
            <span class="stat-val" id="calc-risk-dollars">$0.00</span>
          </div>
          <div class="sizing-stat">
            <span class="stat-label">RISK PER UNIT</span>
            <span class="stat-val" id="calc-risk-per-unit">$0.00</span>
          </div>
          <div class="sizing-stat">
            <span class="stat-label">R:R RATIO</span>
            <span class="stat-val" id="calc-rr-ratio">—</span>
          </div>
        </div>

        <!-- Row 6: Execution Notes -->
        <div class="form-group span-2">
          <label for="ticket-notes">Execution Notes</label>
          <input id="ticket-notes" name="notes" type="text" placeholder="Optional notes" class="ticket-input">
        </div>

        <!-- Row 7: Actions -->
        <div class="form-actions span-2">
          <button type="submit" id="btn-ticket-submit" class="btn-execute" disabled>
            ⚡ LOG 1-CLICK ORDER (R:R &gt;= 1.5 REQUIRED)
          </button>
          <button type="button" id="btn-ticket-clear" class="btn-clear">Clear Ticket</button>
        </div>
        <div id="ticket-msg" class="ticket-msg span-2"></div>
      </form>
    `;

    elContainer.innerHTML = formHtml;

    // Element references
    const form = document.getElementById("manual-ticket-form");
    const elCapital = document.getElementById("ticket-capital");
    const elRiskPct = document.getElementById("ticket-risk-pct");
    const elSymbol = document.getElementById("ticket-symbol");
    const elTimeframe = document.getElementById("ticket-timeframe");
    const elDirection = document.getElementById("ticket-direction");
    const elBtnLong = document.getElementById("btn-dir-long");
    const elBtnShort = document.getElementById("btn-dir-short");
    const elEntry = document.getElementById("ticket-entry");
    const elStop = document.getElementById("ticket-stop");
    const elTarget1 = document.getElementById("ticket-target-1");
    const elTarget2 = document.getElementById("ticket-target-2");
    const elNotes = document.getElementById("ticket-notes");
    const elCalcUnits = document.getElementById("calc-units");
    const elCalcRiskDollars = document.getElementById("calc-risk-dollars");
    const elCalcRiskPerUnit = document.getElementById("calc-risk-per-unit");
    const elCalcRrRatio = document.getElementById("calc-rr-ratio");
    const elRrBadge = document.getElementById("ticket-rr-badge");
    const elSubmitBtn = document.getElementById("btn-ticket-submit");
    const elClearBtn = document.getElementById("btn-ticket-clear");
    const elAtrBtn = document.getElementById("btn-atr-buffer");
    const elUseLastBtn = document.getElementById("btn-use-last-price");
    const elMsg = document.getElementById("ticket-msg");

    // Direction Toggle
    elBtnLong.addEventListener("click", () => {
      elDirection.value = "LONG";
      elBtnLong.classList.add("active");
      elBtnShort.classList.remove("active");
      recalculateMetrics();
    });
    elBtnShort.addEventListener("click", () => {
      elDirection.value = "SHORT";
      elBtnShort.classList.add("active");
      elBtnLong.classList.remove("active");
      recalculateMetrics();
    });

    // Helper: format prices cleanly
    function fmtPrice(p) {
      if (p == null || isNaN(p)) return "";
      return p >= 100 ? p.toFixed(2) : p.toFixed(4);
    }

    // Recalculate Position Sizing & Validate R:R Gate
    function recalculateMetrics() {
      const capital = parseFloat(elCapital.value) || 0;
      const riskPct = parseFloat(elRiskPct.value) || 0;
      const direction = elDirection.value || "LONG";
      const entry = parseFloat(elEntry.value) || 0;
      const stop = parseFloat(elStop.value) || 0;
      const target1 = parseFloat(elTarget1.value) || 0;
      const target2 = elTarget2.value ? parseFloat(elTarget2.value) : null;

      const maxRiskDollars = capital * (riskPct / 100.0);
      const riskPerUnit = (entry > 0 && stop > 0) ? Math.abs(entry - stop) : 0;
      let units = 0;
      if (riskPerUnit > 0 && maxRiskDollars > 0) {
        units = maxRiskDollars / riskPerUnit;
      }

      elCalcUnits.textContent = units > 0
        ? (units >= 100 ? units.toFixed(2) : units >= 1 ? units.toFixed(4) : units.toFixed(6))
        : "0.0000";
      elCalcRiskDollars.textContent = "$" + maxRiskDollars.toFixed(2);
      elCalcRiskPerUnit.textContent = riskPerUnit > 0
        ? "$" + (riskPerUnit >= 100 ? riskPerUnit.toFixed(2) : riskPerUnit.toFixed(4))
        : "$0.00";

      if (entry <= 0 || stop <= 0 || target1 <= 0) {
        elRrBadge.textContent = "AWAITING INPUTS";
        elRrBadge.className = "ticket-risk-badge badge-neutral";
        elCalcRrRatio.textContent = "—";
        elSubmitBtn.disabled = true;
        elSubmitBtn.textContent = "⚡ LOG 1-CLICK ORDER (AWAITING INPUTS)";
        return;
      }

      // Directional validation
      let dirError = "";
      if (direction === "LONG") {
        if (stop >= entry) dirError = "Stop Loss must be < Entry for LONG";
        else if (target1 <= entry) dirError = "Target 1 must be > Entry for LONG";
        else if (target2 !== null && target2 <= target1) dirError = "Target 2 must be > Target 1 for LONG";
      } else {
        if (stop <= entry) dirError = "Stop Loss must be > Entry for SHORT";
        else if (target1 >= entry) dirError = "Target 1 must be < Entry for SHORT";
        else if (target2 !== null && (target2 >= target1 || target2 <= 0)) dirError = "Target 2 must be < Target 1 and > 0 for SHORT";
      }

      if (dirError) {
        elRrBadge.textContent = "DIRECTION ERROR: " + dirError;
        elRrBadge.className = "ticket-risk-badge badge-blocked";
        elCalcRrRatio.textContent = "INVALID";
        elSubmitBtn.disabled = true;
        elSubmitBtn.textContent = "⚡ EXECUTION BLOCKED (" + dirError + ")";
        return;
      }

      const risk = Math.abs(entry - stop);
      const reward = Math.abs(target1 - entry);
      const rr = risk > 0 ? (reward / risk) : 0;
      elCalcRrRatio.textContent = rr.toFixed(2) + " R";

      // Match backend round(rr, 4) >= 1.50
      const isRrValid = (Math.round(rr * 10000) / 10000) >= 1.50;
      if (isRrValid && units > 0) {
        elRrBadge.textContent = `R:R = ${rr.toFixed(2)} (VALID)`;
        elRrBadge.className = "ticket-risk-badge badge-valid";
        elSubmitBtn.disabled = false;
        elSubmitBtn.textContent = `⚡ EXECUTE 1-CLICK ORDER (${direction} ${units.toFixed(4)} UNITS)`;
      } else {
        elRrBadge.textContent = `R:R = ${rr.toFixed(2)} < 1.50 REQUIRED (BLOCKED)`;
        elRrBadge.className = "ticket-risk-badge badge-blocked";
        elSubmitBtn.disabled = true;
        elSubmitBtn.textContent = `⚡ EXECUTION BLOCKED (R:R ${rr.toFixed(2)} < 1.50)`;
      }
    }

    // Attach reactive listeners
    [elCapital, elRiskPct, elEntry, elStop, elTarget1, elTarget2].forEach((inp) => {
      inp.addEventListener("input", recalculateMetrics);
      inp.addEventListener("change", recalculateMetrics);
    });

    // Use Last Price
    elUseLastBtn.addEventListener("click", () => {
      let lastClose = null;
      if (typeof window.chartEngine !== "undefined" && typeof window.chartEngine.getLatestBar === "function") {
        const b = window.chartEngine.getLatestBar();
        if (b && b.close) lastClose = b.close;
      }
      if (!lastClose && window.latestMarketSnapshot && window.latestMarketSnapshot.bars && window.latestMarketSnapshot.bars.length > 0) {
        const b0 = window.latestMarketSnapshot.bars[0];
        lastClose = b0.c != null ? b0.c : b0.close;
      }
      if (lastClose) {
        elEntry.value = fmtPrice(lastClose);
        recalculateMetrics();
        elMsg.textContent = "Entry set to latest market price: " + fmtPrice(lastClose);
        elMsg.style.color = "var(--bullish)";
      } else {
        elMsg.textContent = "No market price available yet.";
        elMsg.style.color = "var(--bearish)";
      }
    });

    // 1-Click ATR Buffer (1.5x)
    elAtrBtn.addEventListener("click", async () => {
      const direction = elDirection.value || "LONG";
      let entry = parseFloat(elEntry.value) || 0;
      if (entry <= 0) {
        elUseLastBtn.click();
        entry = parseFloat(elEntry.value) || 0;
      }
      if (entry <= 0) {
        elMsg.textContent = "Please enter an Entry Price first.";
        elMsg.style.color = "var(--bearish)";
        return;
      }

      let atr = null;
      if (typeof window.chartEngine !== "undefined" && typeof window.chartEngine.getLatestATR === "function") {
        atr = window.chartEngine.getLatestATR();
      }
      if (!atr && window.latestMarketSnapshot && window.latestMarketSnapshot.overlays && window.latestMarketSnapshot.overlays.atr_14) {
        const arr = window.latestMarketSnapshot.overlays.atr_14;
        if (arr.length > 0 && arr[0] > 0) atr = Number(arr[0]);
      }
      if (!atr) {
        try {
          const sym = elSymbol.value || "BTCUSDT";
          const tf = elTimeframe.value || "1m";
          const snap = await window.app.get(`/api/market/snapshot?symbol=${sym}&timeframe=${tf}&limit=50`);
          if (snap && snap.overlays && snap.overlays.atr_14 && snap.overlays.atr_14.length > 0) {
            atr = Number(snap.overlays.atr_14[0]);
          }
        } catch (e) {}
      }
      if (!atr || atr <= 0) {
        atr = entry * 0.005; // 0.5% default fallback
      }

      let stopLoss = 0;
      let target1 = 0;
      let target2 = 0;

      if (direction === "LONG") {
        stopLoss = entry - (1.5 * atr);
        const risk = entry - stopLoss;
        target1 = entry + (1.5 * risk);
        target2 = entry + (3.0 * risk);
      } else {
        stopLoss = entry + (1.5 * atr);
        const risk = stopLoss - entry;
        target1 = entry - (1.5 * risk);
        target2 = Math.max(0.0001, entry - (3.0 * risk));
      }

      elStop.value = fmtPrice(stopLoss);
      elTarget1.value = fmtPrice(target1);
      elTarget2.value = fmtPrice(target2);
      recalculateMetrics();

      elMsg.textContent = `1-Click ATR applied: ATR(14)=${atr.toFixed(2)}, SL=1.5x, TP1=1.5R, TP2=3.0R`;
      elMsg.style.color = "var(--bullish)";
    });

    // Clear Button
    elClearBtn.addEventListener("click", () => {
      form.reset();
      elCapital.value = "10000";
      elRiskPct.value = "1.0";
      elDirection.value = "LONG";
      elBtnLong.classList.add("active");
      elBtnShort.classList.remove("active");
      elMsg.textContent = "";
      recalculateMetrics();
    });

    // Form Submission
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      if (elSubmitBtn.disabled) return;

      const capital = parseFloat(elCapital.value) || 0;
      const riskPct = parseFloat(elRiskPct.value) || 0;
      const entry = parseFloat(elEntry.value) || 0;
      const stop = parseFloat(elStop.value) || 0;
      const target1 = parseFloat(elTarget1.value) || 0;
      const target2 = elTarget2.value ? parseFloat(elTarget2.value) : null;
      const direction = elDirection.value || "LONG";

      const maxRiskDollars = capital * (riskPct / 100.0);
      const riskPerUnit = Math.abs(entry - stop);
      const units = riskPerUnit > 0 ? (maxRiskDollars / riskPerUnit) : 0;

      const payload = {
        strategy_id: "MANUAL",
        symbol: elSymbol.value || "BTCUSDT",
        timeframe: elTimeframe.value || "1m",
        direction: direction,
        entry_price: entry,
        stop_loss: stop,
        target_1_price: target1,
        target_2_price: target2,
        position_size: parseFloat(units.toFixed(6)),
        regime_snapshot: {},
        active_signals: ["MANUAL_1CLICK_ENTRY"],
        notes: elNotes.value.trim() || `1-Click ATR entry (Cap: $${capital}, Risk: ${riskPct}%, R:R: ${(Math.abs(target1 - entry) / riskPerUnit).toFixed(2)})`,
      };

      elSubmitBtn.disabled = true;
      elMsg.textContent = "Transmitting 1-Click order…";
      elMsg.style.color = "var(--warning)";

      try {
        const res = await window.app.post("/api/trades/manual", payload);
        elMsg.textContent = `Order Placed: Trade ID ${res.trade_id} (${res.message || "OK"})`;
        elMsg.style.color = "var(--bullish)";
        if (typeof window.app.refreshStatus === "function") {
          window.app.refreshStatus();
        }
      } catch (e) {
        elMsg.textContent = "Order Rejected: " + e.message;
        elMsg.style.color = "var(--bearish)";
      } finally {
        recalculateMetrics();
      }
    });

    recalculateMetrics();
  }

  // --- Render Last Ticket (Decoupled, never overwrites form) ----------------
  function renderLastTicket(snapshot) {
    const elTicketCard = elManualTicket || document.getElementById("manual-ticket");
    const elLastBody = elTicketLastBody || document.getElementById("ticket-last-body");
    if (!elTicketCard || !elLastBody) return;

    const ticket = snapshot.pending_manual_ticket;
    if (!ticket) {
      elTicketCard.style.display = "none";
      return;
    }
    elTicketCard.style.display = "block";
    elLastBody.innerHTML =
      "<div class=\"metric-row\"><span class=\"metric-k\">Trade ID</span><span class=\"metric-v\">" + escapeHtml(ticket.trade_id) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Strategy</span><span class=\"metric-v\">" + escapeHtml(ticket.strategy_id) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Direction</span><span class=\"metric-v\">" + escapeHtml(ticket.direction) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Symbol</span><span class=\"metric-v\">" + escapeHtml(ticket.symbol) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Entry</span><span class=\"metric-v\">" +
      (ticket.entry_price != null ? Number(ticket.entry_price).toFixed(2) : "—") + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Status</span><span class=\"metric-v ok\">" + escapeHtml(ticket.status) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Created</span><span class=\"metric-v muted small\">" + escapeHtml(ticket.created_at_utc) + "</span></div>";
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  window.systemMonitor = {
    render(snapshot) {
      renderMonitor(snapshot);
      renderActivity(snapshot.recent_activity || []);
      renderLastTicket(snapshot);
    },
    onPositions(positions) {
      // positions are reflected in monitor cards via status refresh
    },
  };

  // Initialize ticket form once DOM is ready.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildTicketForm);
  } else {
    buildTicketForm();
  }

})();
