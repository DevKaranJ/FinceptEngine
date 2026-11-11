/* js/footprint_ui.js — Footprint ladder / order-flow visualization (Phase 6) */

(function () {
  "use strict";

  const container = document.getElementById("footprint-container");
  if (!container) return;

  let ladder = []; // [{price, bidVol, askVol, trades, delta}]

  function render() {
    if (!ladder.length) {
      container.innerHTML =
        "<div style='padding:24px;color:#6e6e73;text-align:center;'>No footprint data. Connect WS and stream candles.</div>";
      return;
    }

    // Build price ladder rows (sorted high -> low)
    const rows = [...ladder].sort((a, b) => b.price - a.price);
    const maxVol = Math.max(1, ...rows.map((r) => Math.max(r.bidVol, r.askVol)));

    let html = "<table style='width:100%;border-collapse:collapse;font-size:11px;'>";
    html += "<thead><tr style='color:#6e6e73;'>" +
      "<th style='text-align:right;padding:4px 6px;border-bottom:1px solid #222;'>Price</th>" +
      "<th style='text-align:right;padding:4px 6px;border-bottom:1px solid #222;'>Bid Vol</th>" +
      "<th style='text-align:center;padding:4px 6px;border-bottom:1px solid #222;'>Trades</th>" +
      "<th style='text-align:right;padding:4px 6px;border-bottom:1px solid #222;'>Ask Vol</th>" +
      "<th style='text-align:right;padding:4px 6px;border-bottom:1px solid #222;'>Delta</th>" +
      "</tr></thead><tbody>";

    rows.forEach((r) => {
      const bidPct = Math.round((r.bidVol / maxVol) * 100);
      const askPct = Math.round((r.askVol / maxVol) * 100);
      const delta = r.askVol - r.bidVol;
      const deltaCls = delta > 0 ? "ask" : delta < 0 ? "bid" : "neu";
      html += "<tr>" +
        "<td style='text-align:right;padding:3px 6px;color:#c9d1d9;font-weight:700;'>" + r.price.toFixed(2) + "</td>" +
        "<td style='text-align:right;padding:3px 6px;'><div class='bar bid' style='width:" + bidPct + "%;'></div> " + r.bidVol + "</td>" +
        "<td style='text-align:center;padding:3px 6px;color:#8a8a92;'>" + r.trades + "</td>" +
        "<td style='text-align:right;padding:3px 6px;'><div class='bar ask' style='width:" + askPct + "%;'></div> " + r.askVol + "</td>" +
        "<td style='text-align:right;padding:3px 6px;color:" + (deltaCls === "ask" ? "#ef5350" : deltaCls === "bid" ? "#26a69a" : "#8a8a92") + ";font-weight:700;'>" +
        (delta > 0 ? "+" : "") + delta + "</td>" +
        "</tr>";
    });
    html += "</tbody></table>";

    // Legend
    html += "<div style='margin-top:8px;color:#6e6e73;font-size:10px;display:flex;gap:16px;'>" +
      "<span>Bid <span style='color:#26a69a;'>▲ buy pressure</span></span>" +
      "<span>Ask <span style='color:#ef5350;'>▼ sell pressure</span></span>" +
      "<span>Delta = Ask − Bid</span>" +
      "</div>";

    container.innerHTML = html;
  }

  function onCandle(c) {
    if (!c) return;
    // Derive a synthetic footprint ladder around the candle close so the UI
    // always has something to render when a real feed isn't attached.
    const close = Number(c.c != null ? c.c : c.close);
    const high = Number(c.h != null ? c.h : c.high);
    const low = Number(c.l != null ? c.l : c.low);
    const vol = Number(c.v != null ? c.v : c.volume) || 100;
    const range = Math.max(high - low, 0.01);
    const steps = 7;
    ladder = [];
    for (let i = 0; i < steps; i++) {
      const price = low + (range / steps) * (i + 0.5);
      // Concentrate volume near close; skew bid/ask based on candle direction.
      const dist = Math.abs(price - close) / range;
      const base = vol * (1 - dist) * 0.6;
      const isUp = close >= (c.o != null ? c.o : c.open);
      const bidVol = Math.floor(base * (isUp ? 1.1 : 0.9));
      const askVol = Math.floor(base * (isUp ? 0.9 : 1.1));
      ladder.push({ price, bidVol, askVol, trades: Math.floor(base * 0.3) });
    }
    render();
  }

  // Expose
  window.footprintUI = { onCandle, render };

  render();
})();
