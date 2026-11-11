/* js/chart_engine.js — TradingView Lightweight Charts integration (Phase 6) */

(function () {
  "use strict";

  const container = document.getElementById("chart-container");
  if (!container) return;
  if (typeof lightweightcharts === "undefined") {
    container.innerHTML =
      "<div style='padding:12px;color:#ff9a8a;'>Lightweight Charts library not loaded.</div>";
    return;
  }

  const { createChart, ColorType } = lightweightcharts;

  // Candlestick chart
  const chart = createChart(container, {
    layout: {
      background: { type: ColorType.Solid, color: "#0b0c0e" },
      textColor: "#c9d1d9",
    },
    grid: {
      vertLines: { color: "#1a1a1e" },
      horzLines: { color: "#1a1a1e" },
    },
    width: container.clientWidth || 700,
    height: container.clientHeight || 420,
    rightPriceScale: {
      borderColor: "#1a1a1e",
    },
    timeScale: {
      borderColor: "#1a1a1e",
      timeVisible: true,
      secondsVisible: false,
    },
  });

  const candleSeries = chart.addCandlestickSeries({
    upColor: "#26a69a",
    downColor: "#ef5350",
    wickUpColor: "#26a69a",
    wickDownColor: "#ef5350",
    borderVisible: false,
    wickVisible: true,
  });

  // Overlay series (line plots). We create them lazily.
  const overlays = {};
  const overlayDefs = [
    { key: "ema_20", color: "#f6c344", lineWidth: 1 },
    { key: "ema_50", color: "#2b6cb0", lineWidth: 1 },
    { key: "hma_20", color: "#9c27b0", lineWidth: 1 },
    { key: "donchian_upper_20", color: "#4ade80", lineWidth: 1 },
    { key: "donchian_lower_20", color: "#f87171", lineWidth: 1 },
  ];

  overlayDefs.forEach((d) => {
    overlays[d.key] = chart.addLineSeries({
      color: d.color,
      lineWidth: d.lineWidth,
      priceFormat: { type: "price", precision: 4, minMove: 0.0001 },
    });
    overlays[d.key].applyOptions({ priceFormat: { type: "price", precision: 4 } });
  });

  // RSI & ATR in a separate pane (simple: draw on price pane but scaled)
  // We'll just store latest values and render as thin overlays on price pane (visual only).
  let currentBars = [];   // {time, open, high, low, close}
  let currentOverlays = {}; // key -> array aligned with currentBars (descending)
  let liveCandle = null;

  function toChartBars(bars) {
    // bars: [{t, o, h, l, c, v}] descending newest-first from API
    const out = bars.slice().reverse(); // -> oldest-first for the chart
    return out.map((b) => ({
      time: b.t,
      open: b.o, high: b.h, low: b.l, close: b.c,
    }));
  }

  function toLineData(key, arr) {
    // arr aligned with bars (descending). Build oldest-first matching times.
    if (!arr || !arr.length) return [];
    const bars = currentBars;
    if (!bars.length) return [];
    // arr is descending; bars[0] is oldest = arr[last]
    const out = [];
    for (let i = 0; i < bars.length; i++) {
      const v = arr[arr.length - 1 - i];
      if (v == null || Number.isNaN(v)) continue;
      out.push({ time: bars[i].time, value: v });
    }
    return out;
  }

  function loadSnapshot(data) {
    currentBars = toChartBars(data.bars || []);
    currentOverlays = data.overlays || {};
    candleSeries.setData(currentBars);

    Object.keys(overlays).forEach((key) => {
      const arr = currentOverlays[key];
      overlays[key].setData(toLineData(key, arr));
    });

    chart.timeScale().fitContent();
    if (data.count) {
      // no-op: count informational
    }
  }

  function onCandle(c) {
    if (!c) return;
    liveCandle = c;
    const bar = {
      time: c.t || c.time || c.open_time_utc,
      open: c.o != null ? c.o : c.open,
      high: c.h != null ? c.h : c.high,
      low: c.l != null ? c.l : c.low,
      close: c.c != null ? c.c : c.close,
    };
    // Update or append the last bar.
    if (currentBars.length && currentBars[currentBars.length - 1].time === bar.time) {
      currentBars[currentBars.length - 1] = bar;
      candleSeries.update(bar);
    } else {
      currentBars.push(bar);
      candleSeries.update(bar);
      // Keep a rolling window
      if (currentBars.length > 1000) currentBars.shift();
    }
  }

  function resize() {
    chart.applyOptions({
      width: container.clientWidth,
      height: container.clientHeight,
    });
  }

  window.addEventListener("resize", resize);

  // Public API
  window.chartEngine = {
    loadSnapshot,
    onCandle,
    resize,
  };

  // Initial empty render
  candleSeries.setData([]);
  chart.timeScale().fitContent();

})();
