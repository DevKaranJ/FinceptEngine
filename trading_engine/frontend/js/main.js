/* js/main.js — FinceptEngine Phase 6: WebSocket orchestration + tab UI */

(function () {
  "use strict";

  const BASE = window.location.origin;
  const WS_URL = BASE.replace(/^http/, "ws") + "/ws/live";

  // --- DOM refs -----------------------------------------------------------
  const elBadge = document.getElementById("badge-text");
  const elUptime = document.getElementById("uptime-text");
  const elFooterStatus = document.getElementById("footer-status");
  const elFooterMsg = document.getElementById("footer-msg");
  const elBtnConnect = document.getElementById("btn-connect");
  const elBtnResearch = document.getElementById("btn-research");
  const elBtnManual = document.getElementById("btn-manual");
  const elChartSymbol = document.getElementById("chart-symbol");
  const elChartTf = document.getElementById("chart-tf");
  const elLabStatus = document.getElementById("lab-status");
  const elManualTicket = document.getElementById("manual-ticket");
  const elTicketBody = document.getElementById("ticket-body");
  const elActivityList = document.getElementById("activity-list");

  let ws = null;
  let wsConnected = false;
  let reconnectTimer = null;

  // --- Tab switching ------------------------------------------------------
  function showTab(tabId) {
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("tab-active"));
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("nav-item-active"));
    const panel = document.getElementById("tab-" + tabId);
    const btn = document.querySelector(".nav-item[data-tab='" + tabId + "']");
    if (panel) panel.classList.add("tab-active");
    if (btn) btn.classList.add("nav-item-active");
    if (tabId === "chart" && typeof window.chartEngine !== "undefined") {
      window.chartEngine.resize();
    }
  }

  document.querySelectorAll(".nav-item[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => showTab(btn.getAttribute("data-tab")));
  });

  // --- Network helpers ----------------------------------------------------
  async function get(path) {
    const res = await fetch(BASE + path, { credentials: "same-origin" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json();
  }

  async function post(path, body) {
    const res = await fetch(BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
      credentials: "same-origin",
    });
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail || ""; } catch (e) {}
      throw new Error("HTTP " + res.status + (detail ? ": " + detail : ""));
    }
    return res.json();
  }

  // --- Status rendering ---------------------------------------------------
  function renderStatus(snapshot) {
    const status = snapshot.status || "IDLE";
    elBadge.textContent = status;
    elBadge.className = "badge " +
      (status === "RUNNING" ? "badge-running" : status === "IDLE" ? "badge-idle" : "badge-alert");
    elFooterStatus.textContent = "● " + (wsConnected ? "Connected" : "Disconnected");
    elFooterStatus.className = wsConnected ? "" : "muted";
    elUptime.textContent = "uptime " + (snapshot.uptime_s || 0) + "s";
    elFooterMsg.textContent = wsConnected
      ? "Live stream active — " + (snapshot.connected_feeds || []).join(", ") || "feeds"
      : "Connect WebSocket to stream live candles & paper positions.";

    // Delegate activity timeline + monitor cards + manual ticket to system monitor.
    if (typeof window.systemMonitor !== "undefined") {
      window.systemMonitor.render(snapshot);
    }
  }

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function setStatusText(msg) {
    if (elFooterMsg) elFooterMsg.textContent = msg;
  }

  // --- WebSocket ----------------------------------------------------------
  function connectWS() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      setStatusText("WS open failed: " + e.message);
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      wsConnected = true;
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
      elBtnConnect.textContent = "Connected";
      elBtnConnect.classList.add("btn-primary");
      setStatusText("WebSocket connected — " + WS_URL);
      // Subscribe to all feeds.
      sendWS({ type: "subscribe", feeds: ["candles", "positions", "status"] });
      refreshStatus();
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
      } catch (e) { return; }
      handleWSMessage(msg);
    };

    ws.onclose = () => {
      wsConnected = false;
      elBtnConnect.textContent = "Connect WS";
      elBtnConnect.classList.remove("btn-primary");
      setStatusText("WebSocket disconnected — will reconnect.");
      scheduleReconnect();
    };

    ws.onerror = (e) => {
      setStatusText("WebSocket error.");
      ws.close();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(connectWS, 3000);
  }

  function sendWS(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }

  function handleWSMessage(msg) {
    const t = msg.type;
    const p = msg.payload;
    if (t === "snapshot") {
      renderStatus(p || {});
    } else if (t === "candle") {
      liveCandle = p || {};
      if (typeof window.chartEngine !== "undefined") {
        window.chartEngine.onCandle(liveCandle);
      }
      if (typeof window.footprintUI !== "undefined") {
        window.footprintUI.onCandle(liveCandle);
      }
      renderStatus({ last_candle: liveCandle });
    } else if (t === "positions") {
      if (typeof window.systemMonitor !== "undefined") {
        window.systemMonitor.onPositions(p || {});
      }
    } else if (t === "status") {
      renderStatus({ status: (p && p.status) || "RUNNING" });
    } else if (t === "manual_ticket") {
      renderStatus({ pending_manual_ticket: p || {} });
    } else if (t === "pong") {
      // heartbeat ack — ignore
    } else if (t === "subscribed") {
      setStatusText("Subscribed to feeds: " + (p && p.feeds ? p.feeds.join(", ") : "none"));
    } else if (t === "ack") {
      // debug ack — ignore
    }
  }

  // --- Periodic REST refresh ---------------------------------------------
  let liveCandle = null;

  async function refreshStatus() {
    try {
      const snap = await get("/api/system/status");
      renderStatus(snap);
    } catch (e) {
      // REST may fail if server not running — keep last known state.
      setStatusText("REST unavailable: " + e.message);
    }
  }

  async function refreshMarketSnapshot() {
    const sym = document.getElementById("sel-symbol").value;
    const tf = document.getElementById("sel-timeframe").value;
    elChartSymbol.textContent = sym;
    elChartTf.textContent = tf;
    try {
      const data = await get("/api/market/snapshot?symbol=" + encodeURIComponent(sym) +
                             "&timeframe=" + encodeURIComponent(tf) + "&limit=500");
      if (typeof window.chartEngine !== "undefined") {
        window.chartEngine.loadSnapshot(data);
      }
    } catch (e) {
      setStatusText("Snapshot failed: " + e.message);
    }
  }

  async function refreshLab() {
    try {
      const data = await get("/api/validation/reports");
      if (typeof window.labUI !== "undefined") {
        window.labUI.render(data);
      }
    } catch (e) {
      elLabStatus.textContent = "Lab load failed: " + e.message;
    }
  }

  let refreshTimer = null;
  function startRefreshLoop() {
    if (refreshTimer) return;
    refreshTimer = setInterval(() => {
      refreshStatus();
      refreshMarketSnapshot();
      refreshLab();
    }, 5000);
    refreshStatus();
    refreshMarketSnapshot();
    refreshLab();
  }

  // --- Wire up buttons ----------------------------------------------------
  elBtnConnect.addEventListener("click", () => {
    if (wsConnected) { ws.close(); return; }
    connectWS();
  });

  elBtnResearch.addEventListener("click", async () => {
    elLabStatus.textContent = "Running research loop → validation gate…";
    try {
      const sym = document.getElementById("sel-symbol").value;
      const tf = document.getElementById("sel-timeframe").value;
      const res = await post("/api/research/trigger", { symbol: sym, timeframe: tf });
      elLabStatus.textContent =
        res.final_status + " · " + (res.promoted ? "V2 PROMOTED" : "V1 stays active") +
        (res.rejection_reason ? " · " + res.rejection_reason : "");
      setStatusText("Research: " + res.final_status);
      refreshLab();
      refreshStatus();
    } catch (e) {
      elLabStatus.textContent = "Research failed: " + e.message;
      setStatusText("Research error: " + e.message);
    }
  });

  elBtnManual.addEventListener("click", () => {
    showTab("monitor");
    // placeholder — the manual ticket form posts via the ticket UI in monitor tab
    setStatusText("Open System Monitor to submit a manual order ticket.");
  });

  document.getElementById("btn-refresh-snapshot").addEventListener("click", refreshMarketSnapshot);
  document.getElementById("sel-symbol").addEventListener("change", refreshMarketSnapshot);
  document.getElementById("sel-timeframe").addEventListener("change", refreshMarketSnapshot);
  document.getElementById("btn-lab-refresh").addEventListener("click", refreshLab);
  document.getElementById("btn-trigger-research").addEventListener("click", elBtnResearch.click.bind(elBtnResearch));

  // --- Boot ---------------------------------------------------------------
  window.addEventListener("DOMContentLoaded", () => {
    connectWS();
    startRefreshLoop();
    showTab("chart");
  });

  // Expose for other modules
  window.app = {
    WS_URL, sendWS, wsConnected: () => wsConnected,
    get, post, refreshStatus, refreshLab, refreshMarketSnapshot,
  };
})();
