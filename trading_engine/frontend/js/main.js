/* js/main.js — FinceptEngine Phase 6 / Milestone 3: WebSocket orchestration + Live Ticker + Tab UI */

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

  // Live status ticker DOM refs
  const elTickerSymbol = document.getElementById("ticker-symbol");
  const elTickerPrice = document.getElementById("ticker-price");
  const elTickerChange = document.getElementById("ticker-change");
  const elTickerSpread = document.getElementById("ticker-spread");
  const elTickerFeeds = document.getElementById("ticker-feeds");
  const elTickerEngine = document.getElementById("ticker-engine");
  const elTickerWs = document.getElementById("ticker-ws");
  const elTickerLatency = document.getElementById("ticker-latency");

  let ws = null;
  let wsConnected = false;
  let reconnectTimer = null;
  let pingStartTime = 0;

  // --- Live Status Ticker Telemetry ---------------------------------------
  const tickerState = {
    symbol: "BTCUSDT",
    price: null,
    prevPrice: null,
    open: null,
    changePct: null,
    spread: "0.1",
    feedsCount: 3,
    engineStatus: "RUNNING",
    wsStatus: "OFFLINE",
    latencyMs: null,
  };

  function formatTickerPrice(val) {
    if (val == null || Number.isNaN(Number(val))) return "--";
    const num = Number(val);
    return num.toLocaleString("en-US", {
      minimumFractionDigits: num >= 100 ? 2 : 4,
      maximumFractionDigits: num >= 100 ? 2 : 4,
    });
  }

  function updateTicker(patch) {
    if (patch) {
      Object.assign(tickerState, patch);
    }

    if (elTickerSymbol && tickerState.symbol) {
      elTickerSymbol.textContent = tickerState.symbol;
    }

    if (elTickerPrice && tickerState.price != null) {
      const formatted = formatTickerPrice(tickerState.price);
      elTickerPrice.textContent = formatted;
      if (tickerState.prevPrice != null && tickerState.price !== tickerState.prevPrice) {
        const isUp = tickerState.price > tickerState.prevPrice;
        elTickerPrice.classList.remove("flash-up", "flash-down");
        void elTickerPrice.offsetWidth; // trigger reflow
        elTickerPrice.classList.add(isUp ? "flash-up" : "flash-down");
      }
    }

    if (elTickerChange && tickerState.changePct != null) {
      const sign = tickerState.changePct >= 0 ? "+" : "";
      elTickerChange.textContent = sign + tickerState.changePct.toFixed(2) + "%";
      elTickerChange.className = "ticker-chg tabular-nums " +
        (tickerState.changePct >= 0 ? "bullish" : "bearish");
    }

    if (elTickerSpread && tickerState.spread != null) {
      elTickerSpread.textContent = tickerState.spread;
    }

    if (elTickerFeeds && tickerState.feedsCount != null) {
      elTickerFeeds.textContent = tickerState.feedsCount + " ACTIVE";
    }

    if (elTickerEngine && tickerState.engineStatus) {
      elTickerEngine.textContent = tickerState.engineStatus;
      elTickerEngine.className = "ticker-badge " +
        (tickerState.engineStatus === "RUNNING"
          ? "ticker-badge-running"
          : tickerState.engineStatus === "IDLE"
          ? "ticker-badge-idle"
          : "ticker-badge-alert");
    }

    if (elTickerWs) {
      elTickerWs.textContent = tickerState.wsStatus;
      elTickerWs.className = "ticker-ws-status " +
        (tickerState.wsStatus === "OK" ? "ok" : "disconnected");
    }

    if (elTickerLatency) {
      elTickerLatency.textContent = tickerState.latencyMs != null
        ? tickerState.latencyMs + "ms"
        : "--ms";
    }
  }

  function measureWsLatency() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      pingStartTime = performance.now();
      sendWS({ type: "ping" });
    }
  }

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
    if (elBadge) {
      elBadge.textContent = status;
      elBadge.className = "badge " +
        (status === "RUNNING" ? "badge-running" : status === "IDLE" ? "badge-idle" : "badge-alert");
    }
    if (elFooterStatus) {
      elFooterStatus.textContent = "● " + (wsConnected ? "Connected" : "Disconnected");
      elFooterStatus.className = wsConnected ? "" : "muted";
    }
    if (elUptime) {
      elUptime.textContent = "uptime " + (snapshot.uptime_s || 0) + "s";
    }
    if (elFooterMsg) {
      elFooterMsg.textContent = wsConnected
        ? "Live stream active — " + (snapshot.connected_feeds || []).join(", ") || "feeds"
        : "Connect WebSocket to stream live candles & paper positions.";
    }

    updateTicker({
      engineStatus: status,
      feedsCount: (snapshot.connected_feeds && snapshot.connected_feeds.length > 0)
        ? snapshot.connected_feeds.length
        : 3,
    });

    // Delegate activity timeline + monitor cards + manual ticket to system monitor.
    if (typeof window.systemMonitor !== "undefined") {
      window.systemMonitor.render(snapshot);
    }
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
      updateTicker({ wsStatus: "OFFLINE", latencyMs: null });
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      wsConnected = true;
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
      if (elBtnConnect) {
        elBtnConnect.textContent = "Connected";
        elBtnConnect.classList.add("btn-primary");
      }
      setStatusText("WebSocket connected — " + WS_URL);
      updateTicker({ wsStatus: "OK" });
      measureWsLatency();
      // Subscribe to all feeds.
      sendWS({ type: "subscribe", feeds: ["candles", "positions", "status"] });
      refreshStatus();
    };

    ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (e) { return; }
      handleWSMessage(msg);
    };

    ws.onclose = () => {
      wsConnected = false;
      if (elBtnConnect) {
        elBtnConnect.textContent = "Connect WS";
        elBtnConnect.classList.remove("btn-primary");
      }
      setStatusText("WebSocket disconnected — will reconnect.");
      updateTicker({ wsStatus: "OFFLINE", latencyMs: null });
      scheduleReconnect();
    };

    ws.onerror = () => {
      setStatusText("WebSocket error.");
      updateTicker({ wsStatus: "OFFLINE", latencyMs: null });
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
      const c = Number(liveCandle.c != null ? liveCandle.c : liveCandle.close);
      const o = Number(liveCandle.o != null ? liveCandle.o : liveCandle.open);
      const h = Number(liveCandle.h != null ? liveCandle.h : liveCandle.high);
      const l = Number(liveCandle.l != null ? liveCandle.l : liveCandle.low);
      const pct = (o > 0) ? ((c - o) / o) * 100 : 0;
      const sp = (h > 0 && l > 0) ? Math.max(0.1, +(h - l).toFixed(1)).toFixed(1) : "0.1";

      updateTicker({
        symbol: liveCandle.symbol || liveCandle.s || tickerState.symbol,
        prevPrice: tickerState.price,
        price: c,
        open: o,
        changePct: pct,
        spread: sp,
      });

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
      if (pingStartTime > 0) {
        const lat = Math.max(1, Math.round(performance.now() - pingStartTime));
        pingStartTime = 0;
        updateTicker({ latencyMs: lat });
      }
    } else if (t === "subscribed") {
      setStatusText("Subscribed to feeds: " + (p && p.feeds ? p.feeds.join(", ") : "none"));
    } else if (t === "ack") {
      // debug ack
    }
  }

  // --- Periodic REST refresh ---------------------------------------------
  let liveCandle = null;

  async function refreshStatus() {
    try {
      const snap = await get("/api/system/status");
      renderStatus(snap);
    } catch (e) {
      setStatusText("REST unavailable: " + e.message);
    }
  }

  async function refreshMarketSnapshot(isInitial = false) {
    const initial = isInitial === true;
    const symEl = document.getElementById("sel-symbol");
    const tfEl = document.getElementById("sel-timeframe");
    const sym = symEl ? symEl.value : "BTCUSDT";
    const tf = tfEl ? tfEl.value : "1m";
    if (elChartSymbol) elChartSymbol.textContent = sym;
    if (elChartTf) elChartTf.textContent = tf;

    try {
      const data = await get("/api/market/snapshot?symbol=" + encodeURIComponent(sym) +
                             "&timeframe=" + encodeURIComponent(tf) + "&limit=500");
      window.latestMarketSnapshot = data;

      if (data.bars && data.bars.length > 0) {
        const latest = data.bars[0]; // newest bar
        const c = Number(latest.c != null ? latest.c : latest.close);
        const o = Number(latest.o != null ? latest.o : latest.open);
        const h = Number(latest.h != null ? latest.h : latest.high);
        const l = Number(latest.l != null ? latest.l : latest.low);
        const pct = (o > 0) ? ((c - o) / o) * 100 : 0;
        const sp = (h > 0 && l > 0) ? Math.max(0.1, +(h - l).toFixed(1)).toFixed(1) : "0.1";

        updateTicker({
          symbol: data.symbol || sym,
          prevPrice: tickerState.price,
          price: c,
          open: o,
          changePct: pct,
          spread: sp,
        });
      }

      if (typeof window.chartEngine !== "undefined") {
        window.chartEngine.loadSnapshot(data, initial);
      }
    } catch (e) {
      setStatusText("Snapshot failed: " + e.message);
    }
  }

  async function refreshLab() {
    try {
      const [reports, diagnostics] = await Promise.all([
        get("/api/validation/reports").catch(() => ({ reports: [] })),
        get("/api/strategy/diagnostics?strategy_id=BASELINE_DEMO_V1").catch(() => null),
      ]);
      if (typeof window.labUI !== "undefined") {
        window.labUI.render(reports, diagnostics);
      }
    } catch (e) {
      if (elLabStatus) elLabStatus.textContent = "Lab load failed: " + e.message;
    }
  }

  let refreshTimer = null;
  function startRefreshLoop() {
    if (refreshTimer) return;
    refreshTimer = setInterval(() => {
      refreshStatus();
      refreshMarketSnapshot(false);
      refreshLab();
      measureWsLatency();
    }, 5000);

    refreshStatus();
    refreshMarketSnapshot(true);
    refreshLab();
    measureWsLatency();
  }

  // --- Wire up buttons ----------------------------------------------------
  if (elBtnConnect) {
    elBtnConnect.addEventListener("click", () => {
      if (wsConnected) { ws.close(); return; }
      connectWS();
    });
  }

  if (elBtnResearch) {
    elBtnResearch.addEventListener("click", async () => {
      if (elLabStatus) elLabStatus.textContent = "Running research loop → validation gate…";
      try {
        const symEl = document.getElementById("sel-symbol");
        const tfEl = document.getElementById("sel-timeframe");
        const sym = symEl ? symEl.value : "BTCUSDT";
        const tf = tfEl ? tfEl.value : "1m";
        const res = await post("/api/research/trigger", { symbol: sym, timeframe: tf });
        if (elLabStatus) {
          elLabStatus.textContent =
            res.final_status + " · " + (res.promoted ? "V2 PROMOTED" : "V1 stays active") +
            (res.rejection_reason ? " · " + res.rejection_reason : "");
        }
        setStatusText("Research: " + res.final_status);
        refreshLab();
        refreshStatus();
      } catch (e) {
        if (elLabStatus) elLabStatus.textContent = "Research failed: " + e.message;
        setStatusText("Research error: " + e.message);
      }
    });
  }

  if (elBtnManual) {
    elBtnManual.addEventListener("click", () => {
      showTab("monitor");
      setStatusText("System Monitor: 1-Click Manual Order Ticket ready.");
    });
  }

  const btnRefreshSnap = document.getElementById("btn-refresh-snapshot");
  if (btnRefreshSnap) {
    btnRefreshSnap.addEventListener("click", () => refreshMarketSnapshot(true));
  }

  const selSym = document.getElementById("sel-symbol");
  if (selSym) {
    selSym.addEventListener("change", () => refreshMarketSnapshot(true));
  }

  const selTf = document.getElementById("sel-timeframe");
  if (selTf) {
    selTf.addEventListener("change", () => refreshMarketSnapshot(true));
  }

  const btnLabRefresh = document.getElementById("btn-lab-refresh");
  if (btnLabRefresh) {
    btnLabRefresh.addEventListener("click", refreshLab);
  }

  const btnTriggerResearch = document.getElementById("btn-trigger-research");
  if (btnTriggerResearch && elBtnResearch) {
    btnTriggerResearch.addEventListener("click", elBtnResearch.click.bind(elBtnResearch));
  }

  // --- Indicator Toggle Chips --------------------------------------------
  document.querySelectorAll(".indicator-chips .chip[data-indicator]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const key = chip.getAttribute("data-indicator");
      const isActive = chip.classList.contains("chip-active");
      const newState = !isActive;
      if (newState) {
        chip.classList.add("chip-active");
      } else {
        chip.classList.remove("chip-active");
      }
      if (typeof window.chartEngine !== "undefined" && typeof window.chartEngine.toggleIndicator === "function") {
        window.chartEngine.toggleIndicator(key, newState);
      }
    });
  });

  // --- Boot ---------------------------------------------------------------
  function boot() {
    connectWS();
    startRefreshLoop();
    showTab("chart");
  }

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  // Expose for other modules
  window.app = {
    WS_URL,
    sendWS,
    wsConnected: () => wsConnected,
    get,
    post,
    refreshStatus,
    refreshLab,
    refreshMarketSnapshot,
    updateTicker,
  };
})();
