// frontend/js/app.js — live data wiring for QuantDeck (FastAPI backend, same origin)

const fmt = (v, d = 1) => (v == null || isNaN(v)) ? "—" : Number(v).toFixed(d);
const pct = (v, d = 1) => (v == null || isNaN(v)) ? "—" : (Number(v) * 100).toFixed(d) + "%";
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

// ── Module loader wiring ─────────────────────────────────────────────
const loaders = { 0: loadScreener, 1: loadDeepDive };
const loaded = {};
function onModule(idx) { if (loaders[idx] && !loaded[idx]) { loaded[idx] = true; loaders[idx](); } }

document.addEventListener("DOMContentLoaded", () => {
  const orig = window.switchModule;
  window.switchModule = function (idx, el) { if (orig) orig(idx, el); onModule(idx); };
  onModule(0);  // Screener is the active module on load
});
