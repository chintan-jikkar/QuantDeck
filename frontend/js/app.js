// frontend/js/app.js — live data wiring for QuantDeck (FastAPI backend, same origin)

const fmt = (v, d = 1) => (v == null || isNaN(v)) ? "—" : Number(v).toFixed(d);
const pct = (v, d = 1) => (v == null || isNaN(v)) ? "—" : (Number(v) * 100).toFixed(d) + "%";
const pctSigned = (v, d = 1) => (v == null || isNaN(v)) ? "—" : ((v >= 0 ? "+" : "") + (Number(v) * 100).toFixed(d) + "%");
function money(v) {
  if (v == null || isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return "$" + (v / 1e12).toFixed(2) + "T";
  if (a >= 1e9)  return "$" + (v / 1e9).toFixed(1) + "B";
  if (a >= 1e6)  return "$" + (v / 1e6).toFixed(1) + "M";
  return "$" + Number(v).toFixed(0);
}
function signal(score) {
  if (score >= 70) return { sp: "sh", sb: "buy", label: "Buy" };
  if (score >= 40) return { sp: "sm", sb: "wch", label: "Watch" };
  return { sp: "sl", sb: "avd", label: "Avoid" };
}

// ── Screener (module 0) ──────────────────────────────────────────────
const SCREENER_TICKERS = "NVDA,MSFT,AAPL,META,AVGO,KO";
async function loadScreener() {
  const tbody = document.getElementById("scr-tbody");
  const kpis = document.getElementById("scr-kpis");
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--txt-m);padding:22px">Loading live data…</td></tr>`;
  try {
    const res = await fetch(`/api/screener?custom=${SCREENER_TICKERS}`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    const rows = (data.rows || []).slice().sort((a, b) => (b.composite_score || 0) - (a.composite_score || 0));
    if (!rows.length) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--amber);padding:22px">No data — the free data tier may be rate-limited. Tap the ↻ refresh (top-right) in a few seconds.</td></tr>`;
      if (kpis) kpis.innerHTML = `<div class="kpi b" style="grid-column:1/-1;text-align:center;color:var(--txt-m);padding:16px">No results yet</div>`;
      return;
    }
    if (kpis) {
      const buys = rows.filter(r => (r.composite_score || 0) >= 70).length;
      const pes = rows.map(r => r.peRatio).filter(x => x != null && !isNaN(x));
      const avgPe = pes.length ? pes.reduce((a, b) => a + b, 0) / pes.length : null;
      const top = rows[0];
      kpis.innerHTML = `
        <div class="kpi b"><i class="ti ti-database kpi-ico" style="color:var(--blue)"></i><div class="kpi-lbl">Universe</div><div class="kpi-val b">${rows.length}</div><div class="kpi-sub">stocks screened</div></div>
        <div class="kpi c"><i class="ti ti-trending-up kpi-ico" style="color:var(--cyan)"></i><div class="kpi-lbl">Buy signals</div><div class="kpi-val c">${buys}</div><div class="kpi-sub">composite ≥ 70</div></div>
        <div class="kpi l"><i class="ti ti-chart-bar kpi-ico" style="color:var(--lime)"></i><div class="kpi-lbl">Avg P/E</div><div class="kpi-val l">${fmt(avgPe)}×</div><div class="kpi-sub">screened set</div></div>
        <div class="kpi a"><i class="ti ti-star kpi-ico" style="color:var(--amber)"></i><div class="kpi-lbl">Top Pick</div><div class="kpi-val w" style="font-size:18px;padding-top:5px">${top.symbol || "—"}</div><div class="kpi-sub">score ${fmt(top.composite_score, 0)}</div></div>`;
    }
    if (tbody) {
      tbody.innerHTML = rows.map(r => {
        const s = signal(r.composite_score || 0);
        return `<tr onclick="selectTicker('${r.symbol}')" style="cursor:pointer">
          <td><span class="cn">${r.symbol || "—"}</span><span class="cs">Equity</span></td>
          <td><span class="sp ${s.sp}">${fmt(r.composite_score, 0)}</span></td>
          <td>${fmt(r.peRatio)}</td>
          <td>${fmt(r.evToEbitda)}</td>
          <td>${pct(r.roe, 0)}</td>
          <td><span class="sb2 ${s.sb}">${s.label}</span></td>
        </tr>`;
      }).join("");
    }
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--pink);padding:22px">Could not load data: ${e.message}</td></tr>`;
  }
}

// ── Deep Dive (module 1) ─────────────────────────────────────────────
let DD_TICKER = "AAPL";
let ddInterval = "1d";
let ddIndicators = new Set();
function renderRevChart(svg, series) {
  if (!series || !series.length) { svg.innerHTML = `<text x="200" y="60" text-anchor="middle" fill="#b4bdd4" font-size="10" font-family="DM Mono,monospace">No revenue data</text>`; return; }
  const W = 400, H = 120, pad = 22;
  const maxR = Math.max(...series.map(s => s.revenue || 0), 1);
  const n = series.length;
  const bw = Math.max(6, (W - 2 * pad) / n * 0.55);
  let out = "", line = [];
  series.forEach((s, i) => {
    const x = pad + (W - 2 * pad) * (i + 0.5) / n;
    const h = Math.max(0, (s.revenue || 0) / maxR * (H - 32));
    out += `<rect x="${(x - bw / 2).toFixed(1)}" y="${(H - 16 - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="rgba(79,158,255,0.32)" stroke="var(--blue)" stroke-width="1"/>`;
    out += `<text x="${x.toFixed(1)}" y="${H - 3}" text-anchor="middle" fill="#b4bdd4" font-size="7" font-family="DM Mono,monospace">${(s.date || "").slice(0, 4)}</text>`;
    const nm = s.net_margin;
    if (nm != null && !isNaN(nm)) line.push(`${x.toFixed(1)},${(H - 16 - nm * (H - 32)).toFixed(1)}`);
  });
  if (line.length > 1) out += `<polyline points="${line.join(" ")}" fill="none" stroke="var(--lime)" stroke-width="1.5" stroke-dasharray="4,2"/>`;
  out += `<line x1="14" y1="11" x2="30" y2="11" stroke="var(--blue)" stroke-width="2"/><text x="34" y="14" fill="var(--txt-m)" font-size="9" font-family="DM Mono,monospace">Revenue</text>`;
  out += `<line x1="96" y1="11" x2="112" y2="11" stroke="var(--lime)" stroke-width="1.5" stroke-dasharray="3,2"/><text x="116" y="14" fill="var(--txt-m)" font-size="9" font-family="DM Mono,monospace">Net mgn</text>`;
  svg.innerHTML = out;
}
function _sma(a, n) { const o = a.map(() => null); let s = 0; for (let i = 0; i < a.length; i++) { s += a[i]; if (i >= n) s -= a[i - n]; if (i >= n - 1) o[i] = s / n; } return o; }
function _ema(a, n) { const o = a.map(() => null); const k = 2 / (n + 1); let e = a[0]; for (let i = 0; i < a.length; i++) { e = (i === 0) ? a[0] : a[i] * k + e * (1 - k); if (i >= n - 1) o[i] = e; } return o; }
function _bb(a, n, k) { const mid = _sma(a, n), up = a.map(() => null), lo = a.map(() => null); for (let i = n - 1; i < a.length; i++) { let s = 0; for (let j = i - n + 1; j <= i; j++) s += (a[j] - mid[i]) ** 2; const sd = Math.sqrt(s / n); up[i] = mid[i] + k * sd; lo[i] = mid[i] - k * sd; } return { mid, up, lo }; }
function _trend(a) { const n = a.length, mx = (n - 1) / 2, my = a.reduce((p, c) => p + c, 0) / n; let num = 0, den = 0; for (let i = 0; i < n; i++) { num += (i - mx) * (a[i] - my); den += (i - mx) ** 2; } const b = den ? num / den : 0, aa = my - b * mx; return a.map((_, i) => aa + b * i); }

function _indTraces(key, x, closes) {
  const ln = (y, name, color, dash) => ({ type: "scatter", mode: "lines", x, y, name, line: { color, width: 1.4, dash: dash || "solid" } });
  if (key === "sma20") return [ln(_sma(closes, 20), "SMA 20", "#4f9eff")];
  if (key === "sma50") return [ln(_sma(closes, 50), "SMA 50", "#ffb340")];
  if (key === "sma200") return [ln(_sma(closes, 200), "SMA 200", "#a78bfa")];
  if (key === "ema20") return [ln(_ema(closes, 20), "EMA 20", "#00e5cc")];
  if (key === "bb") { const b = _bb(closes, 20, 2); return [ln(b.up, "BB Upper", "rgba(124,92,255,0.7)", "dot"), ln(b.mid, "BB Mid", "rgba(180,189,212,0.5)"), ln(b.lo, "BB Lower", "rgba(124,92,255,0.7)", "dot")]; }
  if (key === "trend") return [ln(_trend(closes), "Trendline", "#b8f264", "dash")];
  return [];
}
function renderCandles(divId, candles, ticker, indicators) {
  const el = document.getElementById(divId);
  if (!el) return;
  if (!window.Plotly) { el.innerHTML = `<div style="text-align:center;color:var(--txt-m);padding:48px">chart engine not loaded</div>`; return; }
  if (!candles || !candles.length) { el.innerHTML = `<div style="text-align:center;color:var(--txt-m);padding:48px">No price data</div>`; return; }
  const x = candles.map(c => c.t), closes = candles.map(c => c.c);
  // Chinese convention: red = up, green = down.
  const traces = [{
    type: "candlestick", x,
    open: candles.map(c => c.o), high: candles.map(c => c.h), low: candles.map(c => c.l), close: closes,
    increasing: { line: { color: "#ef4d56" }, fillcolor: "rgba(239,77,86,0.6)" },
    decreasing: { line: { color: "#3fb950" }, fillcolor: "rgba(63,185,80,0.6)" },
    name: ticker,
  }];
  const inds = Array.from(indicators || []);
  inds.forEach(k => _indTraces(k, x, closes).forEach(t => traces.push(t)));
  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "DM Mono, monospace", color: "#b4bdd4", size: 11 },
    margin: { l: 8, r: 56, t: 6, b: 28 },
    xaxis: { gridcolor: "rgba(255,255,255,0.05)", rangeslider: { visible: false } },
    yaxis: { gridcolor: "rgba(255,255,255,0.05)", side: "right" },
    dragmode: "zoom", hovermode: "x unified",
    showlegend: inds.length > 0, legend: { orientation: "h", y: 1.04, x: 0, font: { size: 10 } },
  };
  window.Plotly.react(el, traces, layout, { responsive: true, displayModeBar: false, scrollZoom: true });
}
async function loadCandles() {
  const el = document.getElementById("dd-candles"), pt = document.getElementById("dd-pricetitle");
  if (pt) pt.innerHTML = `<i class="ti ti-chart-candle"></i> ${DD_TICKER} — Price`;
  if (el) el.innerHTML = `<div style="text-align:center;color:var(--txt-m);padding:48px">Loading price…</div>`;
  try {
    const p = await (await fetch(`/api/prices/${DD_TICKER}?interval=${ddInterval}`)).json();
    if (p && !p.error && p.candles && p.candles.length) renderCandles("dd-candles", p.candles, DD_TICKER, ddIndicators);
    else if (el) el.innerHTML = `<div style="text-align:center;color:var(--txt-m);padding:48px">Price unavailable: ${(p && p.error) || "no data"}</div>`;
  } catch (e) { if (el) el.innerHTML = `<div style="text-align:center;color:var(--pink);padding:48px">${e.message}</div>`; }
}
async function loadDeepDive() {
  const kp = document.getElementById("dd-kpis");
  const fund = document.getElementById("dd-fundamentals");
  const memo = document.getElementById("dd-memo");
  const svg = document.getElementById("dd-revsvg");
  const title = document.getElementById("dd-revtitle");
  if (memo) memo.innerHTML = `<span style="color:var(--txt-m)">Loading ${DD_TICKER}…</span>`;
  loadCandles();  // price candlestick (independent of the fundamentals call)
  try {
    const res = await fetch(`/api/deep-dive/${DD_TICKER}`);
    const d = await res.json();
    if (!res.ok || d.error) throw new Error(d.error || `API ${res.status}`);
    if (title) title.innerHTML = `<i class="ti ti-chart-area"></i> Revenue &amp; margins — ${d.ticker}`;
    if (kp) {
      const k = d.kpis || {};
      kp.innerHTML = `
        <div class="kpi b"><div class="kpi-lbl">Market Cap</div><div class="kpi-val b">${money(k.marketCap)}</div><div class="kpi-sub">${d.ticker}</div></div>
        <div class="kpi c"><div class="kpi-lbl">Revenue (FY)</div><div class="kpi-val c">${money(k.revenue)}</div><div class="kpi-sub">latest fiscal year</div></div>
        <div class="kpi l"><div class="kpi-lbl">Net Margin</div><div class="kpi-val l">${pct(k.net_margin)}</div><div class="kpi-sub">most recent</div></div>
        <div class="kpi a"><div class="kpi-lbl">P/E</div><div class="kpi-val a">${fmt(k.peRatio)}×</div><div class="kpi-sub">trailing</div></div>`;
    }
    if (fund) {
      const f = d.fundamentals || {};
      const rows = [
        ["P/E (TTM)", fmt(f.peRatio) + "×"], ["EV/EBITDA", fmt(f.evToEbitda) + "×"],
        ["P/B", fmt(f.pbRatio) + "×"], ["ROE", pct(f.roe)], ["Net Margin", pct(f.netProfitMargin)],
        ["Debt/Equity", fmt(f.debtToEquity)], ["Current Ratio", fmt(f.currentRatio)], ["Rev Growth", pct(f.revenueGrowth)],
      ];
      fund.innerHTML = rows.map(([l, v]) => `<tr><td style="color:var(--txt-d);font-size:10px;text-align:left">${l}</td><td style="color:var(--txt)">${v}</td></tr>`).join("");
    }
    if (memo) {
      const m = d.memo || { bull: [], bear: [] };
      const html = (m.bull || []).map(p => `<span style="color:var(--lime)">●</span> ${p}<br>`).join("")
                 + (m.bear || []).map(p => `<span style="color:var(--pink)">●</span> ${p}<br>`).join("");
      memo.innerHTML = html || `<span style="color:var(--txt-d)">Not enough data for a memo</span>`;
    }
    if (svg) renderRevChart(svg, d.revenue_series || []);
  } catch (e) {
    if (memo) memo.innerHTML = `<span style="color:var(--pink)">Could not load ${DD_TICKER}: ${e.message}</span>`;
  }
}

// ── Valuation (module 2) ─────────────────────────────────────────────
let VAL_TICKER = "AAPL";
function renderRangeSvg(svg, bear, base, bull, cur) {
  const vals = [bear, base, bull, cur].filter(x => x != null && !isNaN(x));
  if (vals.length < 2) { svg.innerHTML = `<text x="180" y="75" text-anchor="middle" fill="#b4bdd4" font-size="11" font-family="DM Mono,monospace">No range</text>`; return; }
  const W = 360, H = 150, padB = 26, padT = 22;
  const hi = Math.max(...vals) * 1.05, lo = Math.min(...vals) * 0.9, span = (hi - lo) || 1;
  const Y = v => H - padB - (v - lo) / span * (H - padB - padT);
  const bars = [["Bear", bear, "var(--pink)"], ["Base", base, "var(--cyan)"], ["Bull", bull, "var(--lime)"]].filter(b => b[1] != null);
  const n = bars.length, slot = (W - 80) / n, bw = Math.min(54, slot * 0.6);
  let out = "";
  bars.forEach((b, i) => {
    const cx = 60 + slot * (i + 0.5), x = cx - bw / 2, yy = Y(b[1]);
    out += `<rect x="${x.toFixed(0)}" y="${yy.toFixed(0)}" width="${bw.toFixed(0)}" height="${(H - padB - yy).toFixed(0)}" rx="4" fill="${b[2]}" opacity="0.2" stroke="${b[2]}" stroke-width="1.2"/>`;
    out += `<text x="${cx.toFixed(0)}" y="${(yy - 7).toFixed(0)}" text-anchor="middle" fill="${b[2]}" font-size="12" font-family="DM Mono,monospace">$${b[1].toFixed(0)}</text>`;
    out += `<text x="${cx.toFixed(0)}" y="${(H - 9).toFixed(0)}" text-anchor="middle" fill="#b4bdd4" font-size="11" font-family="DM Mono,monospace">${b[0]}</text>`;
  });
  if (cur != null) {
    const cy = Y(cur);
    out += `<line x1="24" y1="${cy.toFixed(0)}" x2="${(W - 24).toFixed(0)}" y2="${cy.toFixed(0)}" stroke="var(--amber)" stroke-width="1.4" stroke-dasharray="5,3"/><text x="${(W - 26).toFixed(0)}" y="${(cy - 6).toFixed(0)}" text-anchor="end" fill="var(--amber)" font-size="11" font-family="DM Mono,monospace">Now $${cur.toFixed(0)}</text>`;
  }
  svg.innerHTML = out;
}
async function loadValuation() {
  const kp = document.getElementById("val-kpis");
  const dcfT = document.getElementById("val-dcf");
  const fields = document.getElementById("val-dcffields");
  const compsT = document.getElementById("val-comps");
  const svg = document.getElementById("val-rangesvg");
  if (dcfT) dcfT.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--txt-m);padding:18px">Valuing ${VAL_TICKER}…</td></tr>`;
  try {
    const res = await fetch(`/api/valuation/${VAL_TICKER}`);
    const d = await res.json();
    if (!res.ok || (d.error && !d.dcf)) throw new Error(d.error || `API ${res.status}`);
    const dcf = d.dcf || {}, cur = d.current_price, w = d.wacc || {};
    const dollar = v => (v != null && !isNaN(v)) ? "$" + Number(v).toFixed(0) : "—";
    if (kp) {
      const impl = (dcf.price_base != null && cur) ? (dcf.price_base / cur - 1) : null;
      kp.innerHTML = `
        <div class="kpi c"><div class="kpi-lbl">DCF Fair Value</div><div class="kpi-val c">${dcf.price_base != null ? "$" + dcf.price_base.toFixed(2) : "—"}</div><div class="kpi-sub">base case</div></div>
        <div class="kpi l"><div class="kpi-lbl">Bull / Bear</div><div class="kpi-val l" style="font-size:18px;padding-top:5px">${dollar(dcf.price_bull)} / ${dollar(dcf.price_bear)}</div><div class="kpi-sub">DCF range</div></div>
        <div class="kpi b"><div class="kpi-lbl">Current Price</div><div class="kpi-val b">${cur != null ? "$" + cur.toFixed(2) : "—"}</div><div class="kpi-sub">${d.ticker}</div></div>
        <div class="kpi a"><div class="kpi-lbl">Implied Return</div><div class="kpi-val a">${impl != null ? (impl >= 0 ? "+" : "") + (impl * 100).toFixed(1) + "%" : "—"}</div><div class="kpi-sub">DCF base vs price</div></div>`;
    }
    if (dcfT) {
      const fcfs = dcf.fcf_series || [], disc = dcf.disc_fcf || [];
      const n = Math.min(5, fcfs.length);
      let rows = "";
      for (let i = 0; i < n; i++) rows += `<tr><td>Y${i + 1}</td><td>${(fcfs[i] / 1e9).toFixed(1)}</td><td class="up2">${(disc[i] / 1e9).toFixed(1)}</td></tr>`;
      dcfT.innerHTML = rows || `<tr><td colspan="3" style="text-align:center;color:var(--txt-d)">No projection</td></tr>`;
    }
    if (fields) {
      fields.innerHTML = `
        <div class="dcf-field"><div class="dcf-lbl">WACC</div><div class="dcf-val" style="font-size:15px;color:var(--blue)">${w.wacc != null ? (w.wacc * 100).toFixed(1) + "%" : "—"}</div></div>
        <div class="dcf-field"><div class="dcf-lbl">Terminal Growth</div><div class="dcf-val" style="font-size:15px;color:var(--cyan)">${w.terminal_growth != null ? (w.terminal_growth * 100).toFixed(1) + "%" : "—"}</div></div>
        <div class="dcf-field"><div class="dcf-lbl">Equity Value</div><div class="dcf-val" style="font-size:15px;color:var(--lime)">${money(dcf.equity_value)}</div></div>`;
    }
    if (compsT) {
      const rows = d.comps || [];
      compsT.innerHTML = rows.length
        ? rows.map(r => `<tr><td><span class="cn">${r.symbol || "—"}</span></td><td>${fmt(r.evToEbitda)}×</td><td>${fmt(r.peRatio)}×</td><td class="${(r.revenueGrowth || 0) >= 0 ? "up2" : "dn2"}">${pct(r.revenueGrowth, 0)}</td></tr>`).join("")
        : `<tr><td colspan="4" style="text-align:center;color:var(--txt-d);padding:14px">Comps unavailable (peer API rate limit)</td></tr>`;
    }
    if (svg) renderRangeSvg(svg, dcf.price_bear, dcf.price_base, dcf.price_bull, cur);
  } catch (e) {
    if (dcfT) dcfT.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--pink);padding:18px">Could not value ${VAL_TICKER}: ${e.message}</td></tr>`;
  }
}

// ── Backtester (module 3) ────────────────────────────────────────────
const BT = { strategy: "MA Crossover", ticker: "AAPL", start: "2021-01-01", end: "2024-12-31" };
function renderEquitySvg(svg, strat, bench) {
  if (!strat || strat.length < 2) { svg.innerHTML = `<text x="210" y="60" text-anchor="middle" fill="#b4bdd4" font-size="10" font-family="DM Mono,monospace">No data</text>`; return; }
  const W = 420, H = 120, pad = 10;
  const all = [...strat, ...(bench || [])].filter(x => x != null && !isNaN(x));
  const lo = Math.min(...all), hi = Math.max(...all), span = (hi - lo) || 1;
  const pts = arr => arr.map((v, i) => `${(pad + i / (arr.length - 1) * (W - 2 * pad)).toFixed(1)},${(H - 10 - (v - lo) / span * (H - 26)).toFixed(1)}`).join(" ");
  let out = "";
  if (bench && bench.length > 1) out += `<polyline points="${pts(bench)}" fill="none" stroke="var(--blue)" stroke-width="1.2" stroke-dasharray="3,3"/>`;
  out += `<polyline points="${pts(strat)}" fill="none" stroke="var(--lime)" stroke-width="2" stroke-linejoin="round"/>`;
  out += `<line x1="14" y1="12" x2="30" y2="12" stroke="var(--lime)" stroke-width="2"/><text x="34" y="15" fill="#6b7a99" font-size="9" font-family="DM Mono,monospace">Strategy</text>`;
  out += `<line x1="104" y1="12" x2="120" y2="12" stroke="var(--blue)" stroke-width="1.5" stroke-dasharray="3,2"/><text x="124" y="15" fill="#6b7a99" font-size="9" font-family="DM Mono,monospace">Benchmark</text>`;
  svg.innerHTML = out;
}
function renderHeatmap(el, monthly) {
  if (!monthly || !monthly.length) { el.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--txt-d);font-size:9px">No monthly data</div>`; return; }
  let labels = "", cells = "";
  monthly.forEach(m => {
    labels += `<div style="font-size:7px;color:var(--txt-d);text-align:center">${(m.month || "")[0] || ""}</div>`;
    const r = m.ret || 0;
    const a = Math.min(0.85, 0.18 + Math.abs(r) * 7);
    const col = r >= 0 ? `rgba(184,242,100,${a.toFixed(2)})` : `rgba(255,95,160,${a.toFixed(2)})`;
    cells += `<div title="${m.month}: ${(r * 100).toFixed(1)}%" style="height:16px;background:${col};border-radius:2px"></div>`;
  });
  el.innerHTML = labels + cells;
}
async function loadBacktester() {
  const stats = document.getElementById("bt-stats");
  const svg = document.getElementById("bt-eqsvg");
  const trades = document.getElementById("bt-trades");
  const heat = document.getElementById("bt-heatmap");
  if (stats) stats.innerHTML = `<div class="ts-stat" style="grid-column:1/-1;text-align:center;color:var(--txt-m)">Running backtest…</div>`;
  try {
    const res = await fetch(`/api/backtest?${new URLSearchParams(BT)}`);
    const d = await res.json();
    if (!res.ok || d.error) throw new Error(d.error || `API ${res.status}`);
    const t = d.tearsheet || {};
    if (stats) {
      const stat = (lbl, val, col) => `<div class="ts-stat"><div class="ts-lbl">${lbl}</div><div class="ts-val" style="color:${col}">${val}</div></div>`;
      stats.innerHTML =
        stat("Total Return", pctSigned(t.total_return), "var(--lime)") +
        stat("Ann. Sharpe", fmt(t.sharpe, 2), "var(--cyan)") +
        stat("Max Drawdown", pct(t.max_drawdown, 1), "var(--pink)") +
        stat("Win Rate", pct(t.win_rate, 1), "var(--blue)") +
        stat("Sortino", fmt(t.sortino, 2), "var(--amber)") +
        stat("CAGR", pctSigned(t.cagr), "var(--lime)");
    }
    if (svg) renderEquitySvg(svg, d.equity || [], d.benchmark || []);
    if (trades) {
      const rows = d.trades || [];
      trades.innerHTML = rows.length
        ? rows.map(r => `<tr><td><span class="cn">${r.date || "—"}</span></td><td>${r.action || "—"}</td><td>${r.price != null ? "$" + Number(r.price).toFixed(2) : "—"}</td></tr>`).join("")
        : `<tr><td colspan="3" style="text-align:center;color:var(--txt-d)">No trades</td></tr>`;
    }
    if (heat) renderHeatmap(heat, d.monthly || []);
  } catch (e) {
    if (stats) stats.innerHTML = `<div class="ts-stat" style="grid-column:1/-1;text-align:center;color:var(--pink)">Backtest failed: ${e.message}</div>`;
  }
}

// ── Monte Carlo (module 4) ───────────────────────────────────────────
let MC_TICKER = "AAPL";
let _mcAnim = null;
function renderCone(svg, bands, samples, upto) {
  const p10 = bands.p10 || [], p25 = bands.p25 || [], p50 = bands.p50 || [], p75 = bands.p75 || [], p90 = bands.p90 || [];
  const Nfull = p50.length;
  if (Nfull < 2) { svg.innerHTML = `<text x="200" y="70" text-anchor="middle" fill="#b4bdd4" font-size="11" font-family="DM Mono,monospace">No data</text>`; return; }
  const n = (upto && upto < Nfull) ? Math.max(2, upto) : Nfull;
  const W = 420, H = 140, padL = 8, padR = 30;
  const all = [...p10, ...p90].filter(x => x != null && !isNaN(x));
  const lo = Math.min(...all), hi = Math.max(...all), span = (hi - lo) || 1;
  const X = i => padL + i / (Nfull - 1) * (W - padL - padR);
  const Y = v => H - 10 - (v - lo) / span * (H - 22);
  const up = a => Array.from({ length: n }, (_, i) => `${X(i).toFixed(1)},${Y(a[i]).toFixed(1)}`).join(" ");
  const down = a => Array.from({ length: n }, (_, i) => `${X(n - 1 - i).toFixed(1)},${Y(a[n - 1 - i]).toFixed(1)}`).join(" ");
  let out = `<polygon points="${up(p90)} ${down(p10)}" fill="rgba(79,158,255,0.08)"/>`;
  out += `<polygon points="${up(p75)} ${down(p25)}" fill="rgba(0,229,204,0.10)"/>`;
  (samples || []).slice(0, 10).forEach(p => { out += `<polyline points="${up(p)}" fill="none" stroke="rgba(167,139,250,0.22)" stroke-width="0.8"/>`; });
  out += `<polyline points="${up(p50)}" fill="none" stroke="var(--cyan)" stroke-width="2"/>`;
  if (n >= Nfull) {
    out += `<text x="${W - 26}" y="${Y(p90[Nfull - 1]).toFixed(1)}" fill="var(--lime)" font-size="9" font-family="DM Mono,monospace">P90</text>`;
    out += `<text x="${W - 26}" y="${Y(p50[Nfull - 1]).toFixed(1)}" fill="var(--cyan)" font-size="9" font-family="DM Mono,monospace">Med</text>`;
    out += `<text x="${W - 26}" y="${Y(p10[Nfull - 1]).toFixed(1)}" fill="var(--pink)" font-size="9" font-family="DM Mono,monospace">P10</text>`;
  }
  svg.innerHTML = out;
}
function renderHist(svg, hist, start) {
  if (!hist || !hist.length) { svg.innerHTML = `<text x="110" y="50" text-anchor="middle" fill="#b4bdd4" font-size="9" font-family="DM Mono,monospace">No data</text>`; return; }
  const W = 220, H = 100, pad = 6;
  const maxC = Math.max(...hist.map(h => h.count), 1);
  const bw = (W - 2 * pad) / hist.length;
  let out = "";
  hist.forEach((h, i) => {
    const ht = h.count / maxC * (H - 16);
    const col = h.x >= start ? "rgba(184,242,100,0.5)" : "rgba(255,95,160,0.4)";
    out += `<rect x="${(pad + i * bw).toFixed(1)}" y="${(H - 10 - ht).toFixed(1)}" width="${(bw - 1).toFixed(1)}" height="${ht.toFixed(1)}" rx="1.5" fill="${col}"/>`;
  });
  let si = hist.findIndex(h => h.x >= start); if (si < 0) si = hist.length - 1;
  const sx = pad + (si + 0.5) * bw;
  out += `<line x1="${sx.toFixed(1)}" y1="6" x2="${sx.toFixed(1)}" y2="${H - 8}" stroke="var(--amber)" stroke-width="1.2" stroke-dasharray="3,2"/><text x="${(sx + 2).toFixed(1)}" y="12" fill="var(--amber)" font-size="7" font-family="DM Mono,monospace">Start</text>`;
  svg.innerHTML = out;
}
async function loadMonteCarlo() {
  const kp = document.getElementById("mc-kpis"), cone = document.getElementById("mc-conesvg"),
        hs = document.getElementById("mc-histsvg"), risk = document.getElementById("mc-risk");
  if (kp) kp.innerHTML = `<div class="kpi c" style="grid-column:1/-1;text-align:center;color:var(--txt-m)">Simulating ${MC_TICKER}…</div>`;
  if (cone) cone.innerHTML = `<text x="200" y="70" text-anchor="middle" fill="#b4bdd4" font-size="11" font-family="DM Mono,monospace">running…</text>`;
  try {
    const _model = (document.getElementById("mc-model") || {}).value || "gbm";
    const res = await fetch(`/api/simulation/${MC_TICKER}?model=${_model}`);
    const d = await res.json();
    if (!res.ok || (d.error && !d.bands)) throw new Error(d.error || `API ${res.status}`);
    const ct = document.getElementById("mc-conetitle");
    if (ct) ct.innerHTML = `<i class="ti ti-chart-dots"></i> ${(d.model || "GBM").toUpperCase()} path simulation — ${MC_TICKER} · ${d.horizon}-day horizon`;
    const rp = d.returns_pct || {}, rm = d.risk_metrics || {};
    if (kp) kp.innerHTML = `
      <div class="kpi c"><div class="kpi-lbl">Median Return</div><div class="kpi-val c">${pctSigned(rp.p50)}</div><div class="kpi-sub">2,000 sims · ${d.horizon}d</div></div>
      <div class="kpi l"><div class="kpi-lbl">95th Percentile</div><div class="kpi-val l">${pctSigned(rp.p95)}</div><div class="kpi-sub">bull scenario</div></div>
      <div class="kpi p"><div class="kpi-lbl">5th Percentile</div><div class="kpi-val p">${pctSigned(rp.p5)}</div><div class="kpi-sub">bear scenario</div></div>
      <div class="kpi a"><div class="kpi-lbl">Prob. of Profit</div><div class="kpi-val a">${pct(d.prob_profit, 1)}</div><div class="kpi-sub">above start price</div></div>`;
    if (cone) {
      if (_mcAnim) { clearInterval(_mcAnim); _mcAnim = null; }
      const _N = ((d.bands && d.bands.p50) || []).length;
      let _k = 2;
      renderCone(cone, d.bands || {}, d.sample_paths || [], _k);
      _mcAnim = setInterval(() => {
        _k += Math.max(1, Math.floor(_N / 40));
        if (_k >= _N) { _k = _N; clearInterval(_mcAnim); _mcAnim = null; }
        renderCone(cone, d.bands || {}, d.sample_paths || [], _k);
      }, 40);
    }
    if (hs) renderHist(hs, d.histogram || [], d.start_price);
    if (risk) {
      const rf = (lbl, val, col) => `<div class="dcf-field"><div class="dcf-lbl">${lbl}</div><div style="font-size:14px;font-weight:700;color:${col};font-family:'Syne',sans-serif;margin-top:3px">${val}</div></div>`;
      risk.innerHTML = rf("VaR (95%)", pct(rm.var_95, 1), "var(--pink)") + rf("CVaR (95%)", pct(rm.cvar_95, 1), "var(--pink)") +
        rf("Expected Ret", pctSigned(rm.expected_return), "var(--cyan)") +
        rf("Median Price", rm.p50_price != null ? "$" + Number(rm.p50_price).toFixed(0) : "—", "var(--blue)");
    }
    const meta = document.getElementById("mc-meta");
    if (meta) meta.innerHTML = `<span style="color:var(--txt-m)">Model: <span style="color:var(--cyan)">${(d.model || "gbm").toUpperCase()}</span></span><span style="color:var(--txt-m)">Horizon: <span style="color:var(--txt)">${d.horizon}d</span></span><span style="color:var(--txt-m)">Paths: <span style="color:var(--txt)">2,000</span></span><span style="color:var(--txt-m)">Start: <span style="color:var(--txt)">$${Number(d.start_price).toFixed(0)}</span></span>`;
  } catch (e) {
    if (kp) kp.innerHTML = `<div class="kpi c" style="grid-column:1/-1;text-align:center;color:var(--pink)">Simulation failed: ${e.message}</div>`;
  }
}

// ── Strategy Library (module 5) ──────────────────────────────────────
function renderPerfBars(svg, strats) {
  if (!strats.length) { svg.innerHTML = `<text x="110" y="65" text-anchor="middle" fill="#b4bdd4" font-size="9" font-family="DM Mono,monospace">No data</text>`; return; }
  const W = 220, H = 130, maxA = Math.max(...strats.map(s => Math.abs(s.total_return || 0)), 0.01), n = strats.length, bw = (W - 20) / n * 0.6, zero = H - 30;
  let out = `<line x1="0" y1="${zero}" x2="${W}" y2="${zero}" stroke="#b4bdd4" stroke-width="0.5" stroke-dasharray="2,2"/>`;
  strats.forEach((s, i) => {
    const x = 10 + (W - 20) * (i + 0.5) / n, r = s.total_return || 0, h = Math.abs(r) / maxA * (H - 52), y = r >= 0 ? zero - h : zero, col = r >= 0 ? "var(--lime)" : "var(--pink)";
    out += `<rect x="${(x - bw / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="${col}" opacity="0.35" stroke="${col}" stroke-width="1"/>`;
    out += `<text x="${x.toFixed(1)}" y="${(r >= 0 ? y - 3 : y + h + 9).toFixed(1)}" text-anchor="middle" fill="${col}" font-size="7" font-family="DM Mono,monospace">${(r * 100).toFixed(0)}%</text>`;
    out += `<text x="${x.toFixed(1)}" y="${H - 3}" text-anchor="middle" fill="#b4bdd4" font-size="6" font-family="DM Mono,monospace">${(s.name || "").slice(0, 6)}</text>`;
  });
  svg.innerHTML = out;
}
async function loadStrategies() {
  const kp = document.getElementById("sl-kpis"), cards = document.getElementById("sl-cards"), svg = document.getElementById("sl-perfsvg");
  if (cards) cards.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--txt-m);padding:20px">Backtesting strategies…</div>`;
  try {
    const res = await fetch(`/api/strategies`);
    const d = await res.json();
    if (!res.ok || (d.error && !(d.strategies || []).length)) throw new Error(d.error || `API ${res.status}`);
    const list = d.strategies || [], valid = list.filter(s => !s.error && s.sharpe != null);
    if (kp) {
      const sharpes = valid.map(s => s.sharpe), rets = valid.map(s => s.total_return);
      const best = valid.reduce((a, b) => ((b.sharpe || -99) > (a.sharpe || -99) ? b : a), valid[0] || {});
      const avgRet = rets.length ? rets.reduce((a, b) => a + b, 0) / rets.length : null;
      kp.innerHTML = `
        <div class="kpi b"><div class="kpi-lbl">Strategies</div><div class="kpi-val b">${list.length}</div><div class="kpi-sub">on ${d.ticker}</div></div>
        <div class="kpi l"><div class="kpi-lbl">Best Sharpe</div><div class="kpi-val l">${fmt(best.sharpe, 2)}</div><div class="kpi-sub">${(best.name || "").slice(0, 18)}</div></div>
        <div class="kpi c"><div class="kpi-lbl">Avg Total Return</div><div class="kpi-val c">${pctSigned(avgRet)}</div><div class="kpi-sub">2021–24 on ${d.ticker}</div></div>
        <div class="kpi a"><div class="kpi-lbl">Reference</div><div class="kpi-val w" style="font-size:16px;padding-top:5px">${d.ticker}</div><div class="kpi-sub">single-name test</div></div>`;
    }
    if (cards) cards.innerHTML = list.map(s => {
      const tag = s.error
        ? `<span class="strat-tag" style="color:var(--pink)">n/a here</span>`
        : `<span class="strat-tag">Sharpe ${fmt(s.sharpe, 2)}</span><span class="strat-tag" style="color:${(s.total_return || 0) >= 0 ? "var(--lime)" : "var(--pink)"}">${pctSigned(s.total_return)}</span>`;
      return `<div class="strat-card" onclick="this.classList.toggle('sel')"><div class="strat-name">${s.name}</div><div class="strat-desc">${s.description || ""}</div><div class="strat-meta">${tag}</div></div>`;
    }).join("");
    if (svg) renderPerfBars(svg, valid);
  } catch (e) {
    if (cards) cards.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--pink);padding:20px">Could not load strategies: ${e.message}</div>`;
  }
}

// ── Portfolio Optimizer (module 6) ───────────────────────────────────
function renderFrontier(svg, frontier, maxSharpe, minVol) {
  if (!frontier || !frontier.length) { svg.innerHTML = `<text x="115" y="65" text-anchor="middle" fill="#b4bdd4" font-size="9" font-family="DM Mono,monospace">No data</text>`; return; }
  const W = 230, H = 130, padL = 24, padB = 20;
  const vols = frontier.map(p => p[0]).concat([maxSharpe[0], minVol[0]]);
  const rets = frontier.map(p => p[1]).concat([maxSharpe[1], minVol[1]]);
  const vlo = Math.min(...vols), vhi = Math.max(...vols), rlo = Math.min(...rets), rhi = Math.max(...rets);
  const X = v => padL + (v - vlo) / ((vhi - vlo) || 1) * (W - padL - 8);
  const Y = r => H - padB - (r - rlo) / ((rhi - rlo) || 1) * (H - padB - 12);
  let out = `<line x1="${padL}" y1="10" x2="${padL}" y2="${H - padB}" stroke="#b4bdd4" stroke-width="1"/><line x1="${padL}" y1="${H - padB}" x2="${W - 4}" y2="${H - padB}" stroke="#b4bdd4" stroke-width="1"/>`;
  out += `<text x="6" y="14" fill="#b4bdd4" font-size="7" font-family="DM Mono,monospace">Ret</text><text x="${W - 26}" y="${H - 8}" fill="#b4bdd4" font-size="7" font-family="DM Mono,monospace">Risk</text>`;
  frontier.forEach(p => { out += `<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="1.6" fill="rgba(255,255,255,0.14)"/>`; });
  out += `<circle cx="${X(minVol[0]).toFixed(1)}" cy="${Y(minVol[1]).toFixed(1)}" r="3.5" fill="#b4bdd4"/><text x="${(X(minVol[0]) + 5).toFixed(1)}" y="${(Y(minVol[1]) + 3).toFixed(1)}" fill="#b4bdd4" font-size="7" font-family="DM Mono,monospace">Min Vol</text>`;
  out += `<circle cx="${X(maxSharpe[0]).toFixed(1)}" cy="${Y(maxSharpe[1]).toFixed(1)}" r="5" fill="var(--lime)"/><text x="${(X(maxSharpe[0]) + 6).toFixed(1)}" y="${(Y(maxSharpe[1]) + 3).toFixed(1)}" fill="var(--lime)" font-size="7" font-family="DM Mono,monospace">★ Max Sharpe</text>`;
  svg.innerHTML = out;
}
function renderCorr(el, corr) {
  const syms = corr.symbols || [], m = corr.matrix || [];
  if (!syms.length) { el.innerHTML = `<div style="grid-column:1/-1;color:#fff;font-size:8px">No data</div>`; return; }
  const k = syms.length;
  el.style.gridTemplateColumns = `repeat(${k + 1},1fr)`;
  let out = `<div></div>`;
  syms.forEach(s => out += `<div style="color:#fff;font-size:8px">${s}</div>`);
  for (let i = 0; i < k; i++) {
    out += `<div style="color:#fff;font-size:8px">${syms[i]}</div>`;
    for (let j = 0; j < k; j++) {
      const v = m[i][j], a = Math.abs(v);
      const col = v >= 0 ? `rgba(0,229,204,${(0.14 + a * 0.5).toFixed(2)})` : `rgba(255,95,160,${(0.14 + a * 0.5).toFixed(2)})`;
      out += `<div style="height:18px;background:${col};border-radius:2px;display:flex;align-items:center;justify-content:center;font-size:7px;color:#fff">${v.toFixed(2)}</div>`;
    }
  }
  el.innerHTML = out;
}
async function loadPortfolio() {
  const kp = document.getElementById("po-kpis"), wts = document.getElementById("po-weights"),
        fr = document.getElementById("po-frontier"), cr = document.getElementById("po-corr");
  if (wts) wts.innerHTML = `<div style="text-align:center;color:var(--txt-m);padding:14px">Optimizing portfolio…</div>`;
  try {
    const res = await fetch(`/api/portfolio`);
    const d = await res.json();
    if (!res.ok || (d.error && !d.weights)) throw new Error(d.error || `API ${res.status}`);
    if (kp) kp.innerHTML = `
      <div class="kpi c"><div class="kpi-lbl">Expected Return</div><div class="kpi-val c">${pctSigned(d.expected_return)}</div><div class="kpi-sub">optimized · ann.</div></div>
      <div class="kpi l"><div class="kpi-lbl">Portfolio Sharpe</div><div class="kpi-val l">${fmt(d.sharpe, 2)}</div><div class="kpi-sub">max-Sharpe frontier</div></div>
      <div class="kpi b"><div class="kpi-lbl">Portfolio Vol.</div><div class="kpi-val b">${pct(d.volatility, 1)}</div><div class="kpi-sub">ann. std dev</div></div>
      <div class="kpi a"><div class="kpi-lbl">Positions</div><div class="kpi-val a">${d.positions}</div><div class="kpi-sub">in basket</div></div>`;
    if (wts) {
      const cols = ["var(--blue)", "var(--cyan)", "var(--lime)", "var(--amber)", "var(--purple)", "var(--pink)", "var(--blue)", "var(--cyan)"];
      const maxW = Math.max(...d.weights.map(w => w.weight), 0.01);
      wts.innerHTML = d.weights.map((w, i) => `<div class="port-bar-row"><span class="pb-sym">${w.symbol}</span><div class="pb-track"><div class="pb-fill" style="width:${(w.weight / maxW * 100).toFixed(0)}%;background:${cols[i % cols.length]}"></div></div><span class="pb-pct">${(w.weight * 100).toFixed(1)}%</span><span class="pb-ret ${w.ret >= 0 ? "up2" : "dn2"}">${pctSigned(w.ret)}</span></div>`).join("");
    }
    if (fr) renderFrontier(fr, d.frontier || [], d.max_sharpe || [0, 0], d.min_vol || [0, 0]);
    if (cr) renderCorr(cr, d.correlation || {});
  } catch (e) {
    if (wts) wts.innerHTML = `<div style="text-align:center;color:var(--pink);padding:14px">Optimization failed: ${e.message}</div>`;
  }
}

// ── Module loader wiring + shared ticker flow ────────────────────────
const loaders = { 0: loadScreener, 1: loadDeepDive, 2: loadValuation, 3: loadBacktester, 4: loadMonteCarlo, 5: loadStrategies, 6: loadPortfolio };
const TICKER_MODULES = new Set([1, 2, 3, 4]);  // deep dive, valuation, backtester, monte carlo
const loaded = {};
function onModule(idx) {
  if (!loaders[idx]) return;
  const key = TICKER_MODULES.has(idx) ? DD_TICKER : "once";
  if (loaded[idx] === key) return;
  loaded[idx] = key;
  loaders[idx]();
}
function selectTicker(t) {
  t = (t || "").toUpperCase().trim();
  if (!t) return;
  DD_TICKER = VAL_TICKER = MC_TICKER = t;
  BT.ticker = t;
  TICKER_MODULES.forEach(i => delete loaded[i]);   // force reload for the new ticker
  window.switchModule(1, null);                     // jump to Deep Dive
}
window.selectTicker = selectTicker;

let _curModule = 0;
async function resolveAndSelect(q) {
  q = (q || "").trim();
  if (!q) return;
  try {
    const r = await (await fetch(`/api/search?q=${encodeURIComponent(q)}`)).json();
    const sym = (r.results && r.results[0] && r.results[0].symbol) || q.toUpperCase();
    selectTicker(sym);
  } catch (e) { selectTicker(q.toUpperCase()); }
}

document.addEventListener("DOMContentLoaded", () => {
  const orig = window.switchModule;
  window.switchModule = function (idx, el) {
    if (orig) orig(idx, el);
    _curModule = idx;
    const sub = document.getElementById("mod-sub");
    if (sub && TICKER_MODULES.has(idx)) sub.textContent = "/ " + DD_TICKER;
    onModule(idx);
  };
  const search = document.getElementById("ticker-search");
  if (search) search.addEventListener("keydown", e => {
    if (e.key === "Enter") { resolveAndSelect(search.value); search.value = ""; search.blur(); }
  });
  const iv = document.getElementById("dd-interval");
  if (iv) iv.addEventListener("change", () => { ddInterval = iv.value; loadCandles(); });
  document.querySelectorAll(".ind-btn").forEach(b => b.addEventListener("click", () => {
    const k = b.dataset.ind;
    if (ddIndicators.has(k)) { ddIndicators.delete(k); b.classList.remove("on"); }
    else { ddIndicators.add(k); b.classList.add("on"); }
    loadCandles();
  }));
  const rf = document.getElementById("topbar-refresh");
  if (rf) rf.addEventListener("click", () => { delete loaded[_curModule]; if (loaders[_curModule]) loaders[_curModule](); });
  const mcRun = document.getElementById("mc-run");
  if (mcRun) mcRun.addEventListener("click", () => loadMonteCarlo());
  const mcModel = document.getElementById("mc-model");
  if (mcModel) mcModel.addEventListener("change", () => loadMonteCarlo());
  onModule(0);  // Screener active on load
});
