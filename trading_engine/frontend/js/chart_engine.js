/* js/chart_engine.js — TradingView Lightweight Charts integration (Phase 6) */

(function () {
  "use strict";

  const container = document.getElementById("chart-container");
  const legendEl = document.getElementById("chart-legend");
  if (!container) return;

  const LWC = window.LightweightCharts || window.lightweightcharts;
  if (!LWC) {
    container.innerHTML =
      "<div style='padding:12px;color:#ff9a8a;'>Lightweight Charts library not loaded.</div>";
    return;
  }

  const { createChart, ColorType, CandlestickSeries, LineSeries, HistogramSeries } = LWC;

  // Candlestick chart
  const chart = createChart(container, {
    layout: {
      background: { type: ColorType.Solid, color: "#0b0e14" },
      textColor: "#c9d1d9",
    },
    grid: {
      vertLines: { color: "#161c28" },
      horzLines: { color: "#161c28" },
    },
    width: container.clientWidth || 700,
    height: container.clientHeight || 420,
    rightPriceScale: {
      borderColor: "#232d3f",
      scaleMargins: { top: 0.08, bottom: 0.25 },
    },
    timeScale: {
      borderColor: "#232d3f",
      timeVisible: true,
      secondsVisible: false,
    },
  });

  const candleSeries = (typeof chart.addSeries === "function" && CandlestickSeries)
    ? chart.addSeries(CandlestickSeries, {
        upColor: "#00e676",
        downColor: "#ff5252",
        wickUpColor: "#00e676",
        wickDownColor: "#ff5252",
        borderVisible: false,
        wickVisible: true,
      })
    : chart.addCandlestickSeries({
        upColor: "#00e676",
        downColor: "#ff5252",
        wickUpColor: "#00e676",
        wickDownColor: "#ff5252",
        borderVisible: false,
        wickVisible: true,
      });

  // Dedicated bottom volume histogram sub-pane
  const volumeSeries = (typeof chart.addSeries === "function" && HistogramSeries)
    ? chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      })
    : (typeof chart.addHistogramSeries === "function")
    ? chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      })
    : null;

  if (chart.priceScale("volume")) {
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
  }
  if (chart.priceScale("right")) {
    chart.priceScale("right").applyOptions({
      scaleMargins: { top: 0.08, bottom: 0.25 },
    });
  }

  // Overlay series (line plots).
  const overlays = {};
  const overlayVisibility = {
    ema_20: true,
    ema_50: true,
    hma_20: true,
    donchian_20: true,
  };

  const overlayDefs = [
    { key: "ema_20", color: "#f6c344", lineWidth: 1 },
    { key: "ema_50", color: "#29b6f6", lineWidth: 1 },
    { key: "hma_20", color: "#ab47bc", lineWidth: 1 },
    { key: "donchian_upper_20", color: "#00e676", lineWidth: 1 },
    { key: "donchian_middle_20", color: "#29b6f6", lineWidth: 1 },
    { key: "donchian_lower_20", color: "#ff5252", lineWidth: 1 },
  ];

  overlayDefs.forEach((d) => {
    const opts = {
      color: d.color,
      lineWidth: d.lineWidth,
      priceFormat: { type: "price", precision: 4, minMove: 0.0001 },
    };
    overlays[d.key] = (typeof chart.addSeries === "function" && LineSeries)
      ? chart.addSeries(LineSeries, opts)
      : chart.addLineSeries(opts);
  });

  // State
  let currentBars = [];   // [{time, open, high, low, close, volume}]
  let currentOverlays = {}; // key -> array
  let liveCandle = null;
  let isHovering = false;

  function toUnixSec(t) {
    if (typeof t === "number") return Math.floor(t);
    const ms = Date.parse(t);
    if (!Number.isNaN(ms)) return Math.floor(ms / 1000);
    return Math.floor(Date.now() / 1000);
  }

  function toChartBars(bars) {
    // bars: [{t, o, h, l, c, v}] descending newest-first from API
    const out = bars.slice().reverse(); // -> oldest-first for the chart
    const seen = new Set();
    const result = [];
    for (const b of out) {
      const ts = toUnixSec(b.t || b.time || b.open_time_utc);
      if (seen.has(ts)) continue;
      seen.add(ts);
      result.push({
        time: ts,
        open: Number(b.o != null ? b.o : b.open),
        high: Number(b.h != null ? b.h : b.high),
        low: Number(b.l != null ? b.l : b.low),
        close: Number(b.c != null ? b.c : b.close),
        volume: Number(b.v != null ? b.v : (b.volume != null ? b.volume : 0)),
      });
    }
    result.sort((a, b) => a.time - b.time);
    return result;
  }

  function toLineData(key, arr) {
    if (!arr || !arr.length) return [];
    const bars = currentBars;
    if (!bars.length) return [];
    const out = [];
    for (let i = 0; i < bars.length; i++) {
      const v = arr[arr.length - 1 - i];
      if (v == null || Number.isNaN(v)) continue;
      out.push({ time: bars[i].time, value: Number(v) });
    }
    return out;
  }

  // --- Hover Legend Bar Formatting ---
  function formatPrice(val) {
    if (val == null || Number.isNaN(Number(val))) return "-";
    const num = Number(val);
    return num.toFixed(num >= 100 ? 2 : 4);
  }

  function formatVolume(val) {
    if (val == null || Number.isNaN(Number(val))) return "0.00";
    const v = Number(val);
    if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(2) + "K";
    return v.toFixed(2);
  }

  function formatTime(t) {
    if (!t) return "--";
    const d = new Date(t * 1000);
    return d.toISOString().replace("T", " ").replace(/\..+/, "") + " UTC";
  }

  function renderLegend(bar) {
    if (!legendEl) return;
    if (!bar) {
      legendEl.innerHTML = `<span class="legend-item"><span class="legend-label">STATUS</span> <span class="legend-val">Awaiting market data…</span></span>`;
      return;
    }
    const o = Number(bar.open);
    const h = Number(bar.high);
    const l = Number(bar.low);
    const c = Number(bar.close);
    const v = Number(bar.volume != null ? bar.volume : (bar.value != null ? bar.value : 0));
    const isUp = c >= o;
    const diff = c - o;
    const pct = o !== 0 ? ((diff / o) * 100).toFixed(2) : "0.00";
    const sign = diff >= 0 ? "+" : "";
    const colorClass = isUp ? "up" : "down";

    legendEl.innerHTML = [
      `<span class="legend-item"><span class="legend-label">TIME</span> <span class="legend-val">${formatTime(bar.time)}</span></span>`,
      `<span class="legend-item"><span class="legend-label">O</span> <span class="legend-val">${formatPrice(o)}</span></span>`,
      `<span class="legend-item"><span class="legend-label">H</span> <span class="legend-val">${formatPrice(h)}</span></span>`,
      `<span class="legend-item"><span class="legend-label">L</span> <span class="legend-val">${formatPrice(l)}</span></span>`,
      `<span class="legend-item"><span class="legend-label">C</span> <span class="legend-val ${colorClass}">${formatPrice(c)}</span></span>`,
      `<span class="legend-item"><span class="legend-label">CHG</span> <span class="legend-val ${colorClass}">${sign}${pct}%</span></span>`,
      `<span class="legend-item"><span class="legend-label">VOL</span> <span class="legend-val">${formatVolume(v)}</span></span>`,
    ].join(' <span style="color:#232d3f;">|</span> ');
  }

  function getLatestBar() {
    if (liveCandle) {
      const ts = toUnixSec(liveCandle.t || liveCandle.time || liveCandle.open_time_utc);
      return {
        time: ts,
        open: Number(liveCandle.o != null ? liveCandle.o : liveCandle.open),
        high: Number(liveCandle.h != null ? liveCandle.h : liveCandle.high),
        low: Number(liveCandle.l != null ? liveCandle.l : liveCandle.low),
        close: Number(liveCandle.c != null ? liveCandle.c : liveCandle.close),
        volume: Number(liveCandle.v != null ? liveCandle.v : (liveCandle.volume != null ? liveCandle.volume : 0)),
      };
    }
    if (currentBars.length) {
      return currentBars[currentBars.length - 1];
    }
    return null;
  }

  function updateLegend(hoveredBar) {
    if (hoveredBar) {
      renderLegend(hoveredBar);
    } else {
      renderLegend(getLatestBar());
    }
  }

  // Crosshair move subscription for hover legend
  chart.subscribeCrosshairMove((param) => {
    if (!param || !param.time || param.point === undefined || param.point.x < 0 || param.point.y < 0) {
      isHovering = false;
      updateLegend();
      return;
    }

    isHovering = true;
    let candleData = null;
    let volValue = null;

    if (param.seriesData && typeof param.seriesData.get === "function") {
      candleData = param.seriesData.get(candleSeries);
      if (volumeSeries) {
        const vD = param.seriesData.get(volumeSeries);
        if (vD) volValue = vD.value;
      }
    }

    if (!candleData && param.time) {
      const b = currentBars.find((item) => item.time === param.time);
      if (b) {
        candleData = b;
        volValue = b.volume;
      }
    }

    if (candleData) {
      updateLegend({
        time: param.time,
        open: candleData.open,
        high: candleData.high,
        low: candleData.low,
        close: candleData.close,
        volume: volValue != null ? volValue : candleData.volume,
      });
    } else {
      updateLegend();
    }
  });

  // Indicator Toggle
  function toggleIndicator(key, isVisible) {
    if (typeof isVisible === "boolean") {
      overlayVisibility[key] = isVisible;
    } else {
      overlayVisibility[key] = !overlayVisibility[key];
    }
    const visible = overlayVisibility[key];

    if (key === "donchian_20") {
      ["donchian_upper_20", "donchian_middle_20", "donchian_lower_20"].forEach((subKey) => {
        if (overlays[subKey]) {
          overlays[subKey].applyOptions({ visible: visible });
        }
      });
    } else if (overlays[key]) {
      overlays[key].applyOptions({ visible: visible });
    }
    return visible;
  }

  // Snapshot loading with Viewport Stability
  function loadSnapshot(data, isInitial = false) {
    const visibleRange = chart.timeScale().getVisibleLogicalRange();

    currentBars = toChartBars(data.bars || []);
    currentOverlays = data.overlays || {};
    candleSeries.setData(currentBars);

    if (volumeSeries) {
      const volData = currentBars.map((b) => ({
        time: b.time,
        value: b.volume || 0,
        color: b.close >= b.open ? "rgba(0, 230, 118, 0.6)" : "rgba(255, 82, 82, 0.6)",
      }));
      volumeSeries.setData(volData);
    }

    Object.keys(overlays).forEach((key) => {
      const arr = currentOverlays[key];
      overlays[key].setData(toLineData(key, arr));
    });

    if (isInitial || !visibleRange) {
      chart.timeScale().fitContent();
    } else {
      chart.timeScale().setVisibleLogicalRange(visibleRange);
    }

    if (!isHovering) {
      updateLegend();
    }
  }

  function onCandle(c) {
    if (!c || !candleSeries) return;
    liveCandle = c;
    const ts = toUnixSec(c.t || c.time || c.open_time_utc);
    const o = Number(c.o != null ? c.o : c.open);
    const h = Number(c.h != null ? c.h : c.high);
    const l = Number(c.l != null ? c.l : c.low);
    const close = Number(c.c != null ? c.c : c.close);
    const vol = Number(c.v != null ? c.v : (c.volume != null ? c.volume : 0));
    const bar = {
      time: ts,
      open: o,
      high: h,
      low: l,
      close: close,
      volume: vol,
    };
    const volColor = close >= o ? "rgba(0, 230, 118, 0.6)" : "rgba(255, 82, 82, 0.6)";

    if (currentBars.length && currentBars[currentBars.length - 1].time === bar.time) {
      currentBars[currentBars.length - 1] = bar;
      candleSeries.update(bar);
      if (volumeSeries) {
        volumeSeries.update({ time: ts, value: vol, color: volColor });
      }
    } else if (!currentBars.length || bar.time > currentBars[currentBars.length - 1].time) {
      currentBars.push(bar);
      candleSeries.update(bar);
      if (volumeSeries) {
        volumeSeries.update({ time: ts, value: vol, color: volColor });
      }
      if (currentBars.length > 1000) currentBars.shift();
    }

    if (!isHovering) {
      updateLegend(bar);
    }
  }

  function resize() {
    chart.applyOptions({
      width: container.clientWidth,
      height: container.clientHeight,
    });
  }

  window.addEventListener("resize", resize);

  function getLatestATR() {
    if (currentOverlays && currentOverlays.atr_14 && currentOverlays.atr_14.length > 0) {
      const v = currentOverlays.atr_14[0];
      if (v != null && !Number.isNaN(Number(v)) && Number(v) > 0) return Number(v);
    }
    return null;
  }

  // Public API
  window.chartEngine = {
    loadSnapshot,
    onCandle,
    resize,
    toggleIndicator,
    getChart: () => chart,
    getLatestATR,
    getLatestBar,
  };

  // Initial empty render
  candleSeries.setData([]);
  if (volumeSeries) volumeSeries.setData([]);
  chart.timeScale().fitContent();
  updateLegend();

})();
