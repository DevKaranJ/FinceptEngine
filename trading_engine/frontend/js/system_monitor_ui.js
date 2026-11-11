/* js/system_monitor_ui.js — System Status Monitor + Manual Order Ticket (Phase 6) */

(function () {
  "use strict";

  const elGrid = document.getElementById("monitor-grid");
  const elActivityList = document.getElementById("activity-list");
  const elManualTicket = document.getElementById("manual-ticket");
  const elTicketBody = document.getElementById("ticket-body");

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
      { label: "Last Candle", value: snapshot.last_candle ? snapshot.last_candle.symbol || "—" : "—", cls: "neutral" },
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

  // --- Manual Order Ticket form -------------------------------------------
  function buildTicketForm() {
    const formHtml =
      "<div class=\"panel-header\"><span class=\"panel-title\">1-CLICK MANUAL ORDER TICKET</span>" +
      "<span style=\"margin-left:auto;color:#6e6e73;font-size:10px;\">Paper / Manual (human executes broker order manually)</span></div>" +
      "<form id=\"manual-ticket-form\" style=\"padding:10px 14px;display:grid;grid-template-columns:1fr 1fr;gap:8px;\">" +
      "<div style=\"grid-column:span 2;\">" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Strategy ID</label>" +
      "<input name=\"strategy_id\" type=\"text\" value=\"MANUAL\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "</div>" +
      "<div>" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Symbol</label>" +
      "<select name=\"symbol\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "<option>BTCUSDT</option><option>ETHUSDT</option><option>SOLUSDT</option>" +
      "</select>" +
      "</div>" +
      "<div>" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Timeframe</label>" +
      "<select name=\"timeframe\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "<option>1m</option><option>5m</option><option>15m</option><option>1h</option>" +
      "</select>" +
      "</div>" +
      "<div>" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Direction</label>" +
      "<select name=\"direction\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "<option>LONG</option><option>SHORT</option>" +
      "</select>" +
      "</div>" +
      "<div style=\"grid-column:span 2;\">" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Entry Price</label>" +
      "<input name=\"entry_price\" type=\"number\" step=\"any\" value=\"\" placeholder=\"e.g. 67420.50\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "</div>" +
      "<div>" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Stop Loss</label>" +
      "<input name=\"stop_loss\" type=\"number\" step=\"any\" value=\"\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "</div>" +
      "<div>" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Target 1</label>" +
      "<input name=\"target_1_price\" type=\"number\" step=\"any\" value=\"\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "</div>" +
      "<div>" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Target 2</label>" +
      "<input name=\"target_2_price\" type=\"number\" step=\"any\" value=\"\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "</div>" +
      "<div>" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Position Size</label>" +
      "<input name=\"position_size\" type=\"number\" step=\"any\" value=\"\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "</div>" +
      "<div style=\"grid-column:span 2;\">" +
      "<label style=\"display:block;font-size:10px;color:#6e6e73;margin-bottom:4px;\">Notes</label>" +
      "<input name=\"notes\" type=\"text\" value=\"\" placeholder=\"optional\" style=\"width:100%;background:#0a0a0b;border:1px solid #333338;color:#e8e8ea;border-radius:4px;padding:4px 6px;\">" +
      "</div>" +
      "<div style=\"grid-column:span 2;display:flex;gap:8px;\">" +
      "<button type=\"submit\" style=\"flex:1;background:#1a3a5c;border:1px solid #2a5a7c;color:#7dd3fc;border-radius:4px;padding:6px 12px;cursor:pointer;\">LOG MANUAL TRADE</button>" +
      "<button type=\"button\" id=\"btn-ticket-clear\" style=\"flex:1;background:#161619;border:1px solid #333338;color:#c9d1d9;border-radius:4px;padding:6px 12px;cursor:pointer;\">Clear</button>" +
      "</div>" +
      "<div id=\"ticket-msg\" style=\"grid-column:span 2;margin-top:6px;font-size:11px;color:#7ee28b;\"></div>" +
      "</form>";

    elTicketBody.innerHTML = formHtml;

    const form = document.getElementById("manual-ticket-form");
    const msg = document.getElementById("ticket-msg");
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const payload = {
        strategy_id: fd.get("strategy_id") || "MANUAL",
        symbol: fd.get("symbol") || "BTCUSDT",
        timeframe: fd.get("timeframe") || "1m",
        direction: fd.get("direction") || "LONG",
        entry_price: parseFloat(fd.get("entry_price")) || 0,
        stop_loss: parseFloat(fd.get("stop_loss")) || 0,
        target_1_price: parseFloat(fd.get("target_1_price")) || 0,
        target_2_price: fd.get("target_2_price") ? parseFloat(fd.get("target_2_price")) : null,
        position_size: parseFloat(fd.get("position_size")) || 0,
        regime_snapshot: {},
        active_signals: ["MANUAL_ENTRY"],
        notes: fd.get("notes") || null,
      };
      msg.textContent = "Submitting…";
      msg.style.color = "#f0c674";
      try {
        const res = await window.app.post("/api/trades/manual", payload);
        msg.textContent = res.message || "Trade logged.";
        msg.style.color = "#7ee287";
        form.reset();
        form.elements.strategy_id.value = "MANUAL";
        // Refresh status so the ticket appears.
        if (typeof window.app.refreshStatus === "function") window.app.refreshStatus();
      } catch (e) {
        msg.textContent = "Failed: " + e.message;
        msg.style.color = "#ff9a8a";
      }
    });
    document.getElementById("btn-ticket-clear").addEventListener("click", () => {
      form.reset();
      form.elements.strategy_id.value = "MANUAL";
      msg.textContent = "";
    });
  }

  function renderLastTicket(snapshot) {
    const ticket = snapshot.pending_manual_ticket;
    if (!ticket) {
      elManualTicket.style.display = "none";
      return;
    }
    elManualTicket.style.display = "block";
    elTicketBody.innerHTML =
      "<div class=\"panel-header\"><span class=\"panel-title\">MANUAL ORDER TICKET (LAST)</span></div>" +
      "<div class=\"ticket-body\">" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Trade ID</span><span class=\"metric-v\">" + escapeHtml(ticket.trade_id) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Strategy</span><span class=\"metric-v\">" + escapeHtml(ticket.strategy_id) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Direction</span><span class=\"metric-v\">" + escapeHtml(ticket.direction) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Symbol</span><span class=\"metric-v\">" + escapeHtml(ticket.symbol) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Entry</span><span class=\"metric-v\">" +
      (ticket.entry_price != null ? Number(ticket.entry_price).toFixed(2) : "—") + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Status</span><span class=\"metric-v ok\">" + escapeHtml(ticket.status) + "</span></div>" +
      "<div class=\"metric-row\"><span class=\"metric-k\">Created</span><span class=\"metric-v muted small\">" + escapeHtml(ticket.created_at_utc) + "</span></div>" +
      "</div>";
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
