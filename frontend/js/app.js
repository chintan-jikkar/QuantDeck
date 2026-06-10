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
const SCREENER_TICKERS = "NVDA,MSFT,AAPL,META,AMD,AVGO,LLY,KO";
async function loadScreener() {
  const tbody = document.getElementById("scr-tbody");
  const kpis = document.getElementById("scr-kpis");
  if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--txt-m);padding:22px">Loading live data…</td></tr>`;
  try {
    const res = await fetch(`/api/screener?custom=${SCREENER_TICKERS}`);
    if (!res.ok) throw new Error(`API ${res.status}`);
    const data = await res.json();
    const rows = (data.rows || []).slice().sort((a, b) => (b.composite_score || 0) - (a.composite_score || 0));
    if (!rows.length) { if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--amber);padding:22px">No data returned</td></tr>`; return; }
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
        return `<tr>
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
const DD_TICKER = "AAPL";
function renderRevChart(svg, series) {
  if (!series || !series.length) { svg.innerHTML = `<text x="200" y="60" text-anchor="middle" fill="#3a4460" font-size="10" font-family="DM Mono,monospace">No revenue data</text>`; return; }
  const W = 400, H = 120, pad = 22;
  const maxR = Math.max(...series.map(s => s.revenue || 0), 1);
  const n = series.length;
  const bw = Math.max(6, (W - 2 * pad) / n * 0.55);
  let out = "", line = [];
  series.forEach((s, i) => {
    const x = pad + (W - 2 * pad) * (i + 0.5) / n;
    const h = Math.max(0, (s.revenue || 0) / maxR * (H - 32));
    out += `<rect x="${(x - bw / 2).toFixed(1)}" y="${(H - 16 - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="rgba(79,158,255,0.32)" stroke="var(--blue)" stroke-width="1"/>`;
    out += `<text x="${x.toFixed(1)}" y="${H - 3}" text-anchor="middle" fill="#3a4460" font-size="7" font-family="DM Mono,monospace">${(s.date || "").slice(0, 4)}</text>`;
    const nm = s.net_margin;
    if (nm != null && !isNaN(nm)) line.push(`${x.toFixed(1)},${(H - 16 - nm * (H - 32)).toFixed(1)}`);
  });
  if (line.length > 1) out += `<polyline points="${line.join(" ")}" fill="none" stroke="var(--lime)" stroke-width="1.5" stroke-dasharray="4,2"/>`;
  out += `<line x1="${W-92}" y1="10" x2="${W-78}" y2="10" stroke="var(--blue)" stroke-width="2"/><text x="${W-74}" y="13" fill="#6b7a99" font-size="8" font-family="DM Mono,monospace">Revenue</text>`;
  out += `<line x1="${W-92}" y1="22" x2="${W-78}" y2="22" stroke="var(--lime)" stroke-width="1.5" stroke-dasharray="3,2"/><text x="${W-74}" y="25" fill="#6b7a99" font-size="8" font-family="DM Mono,monospace">Net mgn</text>`;
  svg.innerHTML = out;
}
async function loadDeepDive() {
  const kp = document.getElementById("dd-kpis");
  const fund = document.getElementById("dd-fundamentals");
  const memo = document.getElementById("dd-memo");
  const svg = document.getElementById("dd-revsvg");
  const title = document.getElementById("dd-revtitle");
  if (memo) memo.innerHTML = `<span style="color:var(--txt-m)">Loading ${DD_TICKER}… (a deep dive takes a few seconds)</span>`;
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
const VAL_TICKER = "AAPL";
function renderRangeSvg(svg, bear, base, bull, cur) {
  const pts = [bear, base, bull, cur].filter(x => x != null && !isNaN(x));
  if (pts.length < 2) { svg.innerHTML = `<text x="120" y="38" text-anchor="middle" fill="#3a4460" font-size="9" font-family="DM Mono,monospace">No range</text>`; return; }
  const lo = Math.min(...pts), hi = Math.max(...pts), span = (hi - lo) || 1;
  const W = 240, padL = 16, padR = 16, y = 30, h = 14;
  const X = v => padL + (v - lo) / span * (W - padL - padR);
  let out = "";
  if (bear != null && bull != null)
    out += `<rect x="${X(Math.min(bear, bull)).toFixed(1)}" y="${y}" width="${Math.abs(X(bull) - X(bear)).toFixed(1)}" height="${h}" rx="3" fill="rgba(0,229,204,0.16)" stroke="var(--cyan)" stroke-width="1"/>`;
  if (base != null)
    out += `<line x1="${X(base).toFixed(1)}" y1="${y - 4}" x2="${X(base).toFixed(1)}" y2="${y + h + 4}" stroke="var(--lime)" stroke-width="2"/><text x="${X(base).toFixed(1)}" y="${y - 7}" text-anchor="middle" fill="var(--lime)" font-size="8" font-family="DM Mono,monospace">Base $${base.toFixed(0)}</text>`;
  if (cur != null)
    out += `<line x1="${X(cur).toFixed(1)}" y1="${y - 9}" x2="${X(cur).toFixed(1)}" y2="${y + h + 9}" stroke="var(--amber)" stroke-width="1" stroke-dasharray="3,2"/><text x="${X(cur).toFixed(1)}" y="${y + h + 18}" text-anchor="middle" fill="var(--amber)" font-size="8" font-family="DM Mono,monospace">Now $${cur.toFixed(0)}</text>`;
  if (bear != null) out += `<text x="${X(bear).toFixed(1)}" y="${y + h + 18}" text-anchor="middle" fill="var(--pink)" font-size="7" font-family="DM Mono,monospace">Bear $${bear.toFixed(0)}</text>`;
  if (bull != null) out += `<text x="${X(bull).toFixed(1)}" y="${y - 7}" text-anchor="middle" fill="var(--cyan)" font-size="7" font-family="DM Mono,monospace">Bull $${bull.toFixed(0)}</text>`;
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
  if (!strat || strat.length < 2) { svg.innerHTML = `<text x="210" y="60" text-anchor="middle" fill="#3a4460" font-size="10" font-family="DM Mono,monospace">No data</text>`; return; }
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
const MC_TICKER = "AAPL";
function renderCone(svg, bands, samples) {
  const p10 = bands.p10 || [], p25 = bands.p25 || [], p50 = bands.p50 || [], p75 = bands.p75 || [], p90 = bands.p90 || [];
  if (p50.length < 2) { svg.innerHTML = `<text x="200" y="70" text-anchor="middle" fill="#9aa6c2" font-size="10" font-family="DM Mono,monospace">No data</text>`; return; }
  const W = 420, H = 140, padL = 8, padR = 30;
  const all = [...p10, ...p90].filter(x => x != null && !isNaN(x));
  const lo = Math.min(...all), hi = Math.max(...all), span = (hi - lo) || 1;
  const n = p50.length;
  const X = i => padL + i / (n - 1) * (W - padL - padR);
  const Y = v => H - 10 - (v - lo) / span * (H - 22);
  const poly = arr => arr.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
  let out = `<polygon points="${poly(p90)} ${p10.map((v, i) => `${X(n - 1 - i).toFixed(1)},${Y(p10[n - 1 - i]).toFixed(1)}`).join(" ")}" fill="rgba(79,158,255,0.08)"/>`;
  out += `<polygon points="${poly(p75)} ${p25.map((v, i) => `${X(n - 1 - i).toFixed(1)},${Y(p25[n - 1 - i]).toFixed(1)}`).join(" ")}" fill="rgba(0,229,204,0.10)"/>`;
  (samples || []).slice(0, 10).forEach(p => { out += `<polyline points="${poly(p)}" fill="none" stroke="rgba(167,139,250,0.22)" stroke-width="0.8"/>`; });
  out += `<polyline points="${poly(p50)}" fill="none" stroke="var(--cyan)" stroke-width="1.8"/>`;
  out += `<text x="${W - 26}" y="${Y(p90[n - 1]).toFixed(1)}" fill="var(--lime)" font-size="8" font-family="DM Mono,monospace">P90</text>`;
  out += `<text x="${W - 26}" y="${Y(p50[n - 1]).toFixed(1)}" fill="var(--cyan)" font-size="8" font-family="DM Mono,monospace">Med</text>`;
  out += `<text x="${W - 26}" y="${Y(p10[n - 1]).toFixed(1)}" fill="var(--pink)" font-size="8" font-family="DM Mono,monospace">P10</text>`;
  svg.innerHTML = out;
}
function renderHist(svg, hist, start) {
  if (!hist || !hist.length) { svg.innerHTML = `<text x="110" y="50" text-anchor="middle" fill="#9aa6c2" font-size="9" font-family="DM Mono,monospace">No data</text>`; return; }
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
  try {
    const res = await fetch(`/api/simulation/${MC_TICKER}`);
    const d = await res.json();
    if (!res.ok || (d.error && !d.bands)) throw new Error(d.error || `API ${res.status}`);
    const rp = d.returns_pct || {}, rm = d.risk_metrics || {};
    if (kp) kp.innerHTML = `
      <div class="kpi c"><div class="kpi-lbl">Median Return</div><div class="kpi-val c">${pctSigned(rp.p50)}</div><div class="kpi-sub">2,000 sims · ${d.horizon}d</div></div>
      <div class="kpi l"><div class="kpi-lbl">95th Percentile</div><div class="kpi-val l">${pctSigned(rp.p95)}</div><div class="kpi-sub">bull scenario</div></div>
      <div class="kpi p"><div class="kpi-lbl">5th Percentile</div><div class="kpi-val p">${pctSigned(rp.p5)}</div><div class="kpi-sub">bear scenario</div></div>
      <div class="kpi a"><div class="kpi-lbl">Prob. of Profit</div><div class="kpi-val a">${pct(d.prob_profit, 1)}</div><div class="kpi-sub">above start price</div></div>`;
    if (cone) renderCone(cone, d.bands || {}, d.sample_paths || []);
    if (hs) renderHist(hs, d.histogram || [], d.start_price);
    if (risk) {
      const rf = (lbl, val, col) => `<div class="dcf-field"><div class="dcf-lbl">${lbl}</div><div style="font-size:14px;font-weight:700;color:${col};font-family:'Syne',sans-serif;margin-top:3px">${val}</div></div>`;
      risk.innerHTML = rf("VaR (95%)", pct(rm.var_95, 1), "var(--pink)") + rf("CVaR (95%)", pct(rm.cvar_95, 1), "var(--pink)") +
        rf("Expected Ret", pctSigned(rm.expected_return), "var(--cyan)") +
        rf("Median Price", rm.p50_price != null ? "$" + Number(rm.p50_price).toFixed(0) : "—", "var(--blue)");
    }
  } catch (e) {
    if (kp) kp.innerHTML = `<div class="kpi c" style="grid-column:1/-1;text-align:center;color:var(--pink)">Simulation failed: ${e.message}</div>`;
  }
}

// ── Strategy Library (module 5) ──────────────────────────────────────
function renderPerfBars(svg, strats) {
  if (!strats.length) { svg.innerHTML = `<text x="110" y="65" text-anchor="middle" fill="#9aa6c2" font-size="9" font-family="DM Mono,monospace">No data</text>`; return; }
  const W = 220, H = 130, maxA = Math.max(...strats.map(s => Math.abs(s.total_return || 0)), 0.01), n = strats.length, bw = (W - 20) / n * 0.6, zero = H - 30;
  let out = `<line x1="0" y1="${zero}" x2="${W}" y2="${zero}" stroke="#9aa6c2" stroke-width="0.5" stroke-dasharray="2,2"/>`;
  strats.forEach((s, i) => {
    const x = 10 + (W - 20) * (i + 0.5) / n, r = s.total_return || 0, h = Math.abs(r) / maxA * (H - 52), y = r >= 0 ? zero - h : zero, col = r >= 0 ? "var(--lime)" : "var(--pink)";
    out += `<rect x="${(x - bw / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="2" fill="${col}" opacity="0.35" stroke="${col}" stroke-width="1"/>`;
    out += `<text x="${x.toFixed(1)}" y="${(r >= 0 ? y - 3 : y + h + 9).toFixed(1)}" text-anchor="middle" fill="${col}" font-size="7" font-family="DM Mono,monospace">${(r * 100).toFixed(0)}%</text>`;
    out += `<text x="${x.toFixed(1)}" y="${H - 3}" text-anchor="middle" fill="#9aa6c2" font-size="6" font-family="DM Mono,monospace">${(s.name || "").slice(0, 6)}</text>`;
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

// ── Module loader wiring ─────────────────────────────────────────────
const loaders = { 0: loadScreener, 1: loadDeepDive, 2: loadValuation, 3: loadBacktester, 4: loadMonteCarlo, 5: loadStrategies };
const loaded = {};
function onModule(idx) { if (loaders[idx] && !loaded[idx]) { loaded[idx] = true; loaders[idx](); } }

document.addEventListener("DOMContentLoaded", () => {
  const orig = window.switchModule;
  window.switchModule = function (idx, el) { if (orig) orig(idx, el); onModule(idx); };
  onModule(0);  // Screener is the active module on load
});
