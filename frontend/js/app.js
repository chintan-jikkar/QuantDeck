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

// ── Daily top-pick rotation (localStorage) ───────────────────────────
function getDailyTopPick(rows) {
  const today = new Date().toISOString().slice(0, 10);
  const storeKey = "qd-daily-pick";
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(storeKey) || "{}"); } catch (_) {}
  if (stored.date === today && stored.symbol) {
    const match = rows.find(r => r.symbol === stored.symbol);
    return { pick: match || rows[0], isRepeat: stored.isRepeat || false, honorable: stored.honorable || [] };
  }
  const sorted = rows.filter(r => r.composite_score != null).sort((a, b) => (b.composite_score || 0) - (a.composite_score || 0));
  const history = stored.history || [];
  const maxExclude = Math.max(0, Math.floor(sorted.length * 0.6));
  const recent = history.slice(-maxExclude);
  const pick = sorted.find(r => !recent.includes(r.symbol));
  const isRepeat = !pick;
  const finalPick = pick || sorted[0];
  const honorable = sorted.filter(r => r !== finalPick).slice(0, 2).map(r => r.symbol);
  const newHistory = [...history, finalPick.symbol].slice(-sorted.length);
  try {
    localStorage.setItem(storeKey, JSON.stringify({ date: today, symbol: finalPick.symbol, isRepeat, honorable, history: newHistory }));
  } catch (_) {}
  return { pick: finalPick, isRepeat, honorable };
}

async function _renderScrWatchlistChips() {
  const el = document.getElementById("scr-watchlist-chips");
  if (!el) return;
  try {
    const d = await (await fetch("/api/watchlist")).json();
    const items = d.tickers || [];
    if (!items.length) { el.innerHTML = `<span style="color:var(--txt-d);font-size:10px">Add tickers to your watchlist →</span>`; return; }
    el.innerHTML = items.map(it => {
      const chg = it.change_pct;
      const cls = chg == null ? "var(--txt-m)" : chg >= 0 ? "var(--lime)" : "var(--pink)";
      const chgStr = chg != null ? ` ${chg >= 0 ? "+" : ""}${chg.toFixed(1)}%` : "";
      return `<span onclick="selectTicker('${it.symbol}')" style="cursor:pointer;display:inline-flex;align-items:center;gap:3px;background:rgba(79,158,255,0.1);border:1px solid rgba(79,158,255,0.25);border-radius:5px;padding:3px 8px;font-size:10px;font-family:'DM Mono',monospace;color:var(--blue);white-space:nowrap">
        ${it.symbol}<span style="color:${cls};font-size:9px">${chgStr}</span></span>`;
    }).join("");
  } catch (_) { el.innerHTML = `<span style="color:var(--txt-d);font-size:10px">—</span>`; }
}

// ── Screener (module 0) ──────────────────────────────────────────────
const SCREENER_TICKERS ="NVDA,MSFT,AAPL,META,AVGO,KO,TSLA,AMZN,GOOG,RELIANCE.NS,TCS.NS,TATASTEEL.NS,INFY.NS,ASML,NVO,SAP,BABA,005930.KS";
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
    // Daily top-pick rotation
    const { pick: dailyPick, isRepeat, honorable } = getDailyTopPick(rows);
    if (kpis) {
      const buys = rows.filter(r => (r.composite_score || 0) >= 70).length;
      const pes = rows.map(r => r.peRatio).filter(x => x != null && !isNaN(x));
      const avgPe = pes.length ? pes.reduce((a, b) => a + b, 0) / pes.length : null;
      const repeatBadge = isRepeat ? `<span style="font-size:8px;color:var(--amber);font-family:'DM Mono',monospace;display:block;margin-top:2px">Honorable mention</span>` : "";
      kpis.innerHTML = `
        <div class="kpi b"><i class="ti ti-database kpi-ico" style="color:var(--blue)"></i><div class="kpi-lbl">Universe</div><div class="kpi-val b">${rows.length}</div><div class="kpi-sub">stocks screened</div></div>
        <div class="kpi c"><i class="ti ti-trending-up kpi-ico" style="color:var(--cyan)"></i><div class="kpi-lbl">Buy signals</div><div class="kpi-val c">${buys}</div><div class="kpi-sub">composite ≥ 70</div></div>
        <div class="kpi l"><i class="ti ti-chart-bar kpi-ico" style="color:var(--lime)"></i><div class="kpi-lbl">Avg P/E</div><div class="kpi-val l">${fmt(avgPe)}×</div><div class="kpi-sub">screened set</div></div>
        <div class="kpi a"><i class="ti ti-star kpi-ico" style="color:var(--amber)"></i><div class="kpi-lbl">Top Pick</div><div class="kpi-val w" style="font-size:18px;padding-top:5px">${dailyPick ? dailyPick.symbol : "—"}</div><div class="kpi-sub">score ${fmt(dailyPick ? dailyPick.composite_score : null, 0)}${isRepeat ? " · repeat" : ""}</div>${repeatBadge}</div>`;
    }
    if (dailyPick) {
      const lbl = document.getElementById("scr-spark-label");
      const sc = document.getElementById("scr-spark-score");
      const honorStr = honorable.length ? ` · next: ${honorable.join(", ")}` : "";
      if (lbl) lbl.textContent = `${dailyPick.symbol}${isRepeat ? " (repeat)" : ""} — score trend`;
      if (sc) sc.textContent = `↑ ${fmt(dailyPick.composite_score, 0)}pts${honorStr}`;
    }
    // Screener watchlist section
    _renderScrWatchlistChips();
  } catch (e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--pink);padding:22px">Could not load data: ${e.message}</td></tr>`;
  }
}

// ── Deep Dive (module 1) ─────────────────────────────────────────────
let DD_TICKER = "AAPL";
let ddInterval = "1d";
let ddIndicators = new Set();
function renderRevPlotly(divId, series) {
  const div = document.getElementById(divId);
  if (!div) return;
  if (!series || !series.length) {
    div.innerHTML = `<div style="height:230px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-family:'DM Mono',monospace;font-size:11px">No revenue data</div>`;
    return;
  }
  const labels = series.map(s => (s.date || "").slice(0, 4));
  const revs = series.map(s => +((s.revenue || 0) / 1e9).toFixed(2));
  const margins = series.map(s => s.net_margin != null ? +((s.net_margin) * 100).toFixed(1) : null);
  const traces = [
    { x: labels, y: revs, name: "Revenue ($B)", type: "bar",
      marker: { color: "rgba(79,158,255,0.4)", line: { color: "rgba(79,158,255,0.85)", width: 1 } },
      hovertemplate: "%{x}<br>Revenue: $%{y:.1f}B<extra></extra>" },
    { x: labels, y: margins, name: "Net Margin", type: "scatter", mode: "lines+markers",
      yaxis: "y2", line: { color: "#b8f264", width: 2, dash: "dot" },
      marker: { color: "#b8f264", size: 6 },
      hovertemplate: "%{x}<br>Net Margin: %{y:.1f}%<extra></extra>" },
  ];
  const layout = {
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    margin: { l: 40, r: 44, t: 8, b: 30 },
    xaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" } },
    yaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             tickformat: ".0f", title: { text: "$B", font: { color: "#6b7a99", size: 9 } }, zeroline: false },
    yaxis2: { overlaying: "y", side: "right", tickformat: ".0f", ticksuffix: "%",
               tickfont: { color: "#b8f264", size: 9, family: "DM Mono" }, zeroline: false, showgrid: false },
    legend: { font: { color: "#b4bdd4", size: 9, family: "DM Mono" }, x: 0.01, y: 0.99,
               bgcolor: "rgba(8,11,18,0.6)", bordercolor: "rgba(255,255,255,0.06)", borderwidth: 1 },
    bargap: 0.38, hovermode: "x unified",
    hoverlabel: { bgcolor: "#131929", bordercolor: "#243559", font: { color: "#e2e8f7", size: 10, family: "DM Mono" } },
  };
  Plotly.react(div, traces, layout, { responsive: true, displayModeBar: false });
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
    showlegend: inds.length > 0,
    legend: { orientation: "h", y: -0.07, x: 0, xanchor: "left", yanchor: "top",
              font: { size: 9, family: "DM Mono, monospace", color: "#b4bdd4" },
              bgcolor: "rgba(0,0,0,0)", borderwidth: 0 },
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
  const title = document.getElementById("dd-revtitle");
  if (memo) memo.innerHTML = `<span style="color:var(--txt-m)">Loading ${DD_TICKER}…</span>`;
  loadCandles();  // price candlestick (independent of the fundamentals call)
  try {
    const res = await fetch(`/api/deep-dive/${DD_TICKER}`);
    const d = await res.json();
    if (!res.ok || d.error) throw new Error(d.error || `API ${res.status}`);
    if (title) title.innerHTML = `<i class="ti ti-chart-area"></i> Revenue &amp; margins — ${d.ticker}`;
    const an = d.analyst || {};
    if (kp) {
      const k = d.kpis || {};
      const tgt = an.target != null ? "$" + Number(an.target).toFixed(0) : "—";
      const upsideStr = an.upside != null ? `<div class="kpi-sub ${an.upside >= 0 ? "up" : "dn"}">${an.upside >= 0 ? "+" : ""}${an.upside}% vs price</div>` : `<div class="kpi-sub">${an.n_analysts ? an.n_analysts + " analysts" : "analyst target"}</div>`;
      kp.innerHTML = `
        <div class="kpi b"><div class="kpi-lbl">Market Cap</div><div class="kpi-val b">${money(k.marketCap)}</div><div class="kpi-sub">${d.ticker}</div></div>
        <div class="kpi c"><div class="kpi-lbl">Revenue (FY)</div><div class="kpi-val c">${money(k.revenue)}</div><div class="kpi-sub">latest fiscal year</div></div>
        <div class="kpi l"><div class="kpi-lbl">Net Margin</div><div class="kpi-val l">${pct(k.net_margin)}</div><div class="kpi-sub">most recent</div></div>
        <div class="kpi a"><div class="kpi-lbl">Analyst Target</div><div class="kpi-val a">${tgt}</div>${upsideStr}</div>`;
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
    const analystEl = document.getElementById("dd-analyst");
    if (analystEl) {
      const recColors = { strong_buy: "var(--lime)", buy: "var(--lime)", hold: "var(--amber)", sell: "var(--pink)", strong_sell: "var(--pink)", underperform: "var(--pink)", outperform: "var(--lime)" };
      const recLabels = { strong_buy: "Strong Buy", buy: "Buy", hold: "Hold", sell: "Sell", strong_sell: "Strong Sell", underperform: "Underperform", outperform: "Outperform" };
      const recKey = an.rec_key || "";
      const recColor = recColors[recKey] || "var(--txt-m)";
      const recLabel = recLabels[recKey] || (recKey ? recKey.replace(/_/g," ") : "—");
      let barHtml = "";
      if (an.buy_pct != null && an.hold_pct != null && an.sell_pct != null) {
        barHtml = `
          <div style="display:flex;gap:6px;align-items:center;margin-bottom:5px">
            <div style="flex:1;height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden">
              <div style="display:flex;height:100%">
                <div style="width:${an.buy_pct}%;background:var(--lime)"></div>
                <div style="width:${an.hold_pct}%;background:var(--amber)"></div>
                <div style="width:${an.sell_pct}%;background:var(--pink)"></div>
              </div>
            </div>
          </div>
          <div style="display:flex;gap:12px;font-size:10px">
            <span style="color:var(--lime)">■ Buy ${an.buy_pct}%</span>
            <span style="color:var(--amber)">■ Hold ${an.hold_pct}%</span>
            <span style="color:var(--pink)">■ Sell ${an.sell_pct}%</span>
          </div>`;
      }
      const tgtLine = an.target != null ? `<div style="font-size:10px;color:var(--txt-m);margin-bottom:6px">Target: <span style="color:var(--txt)">$${Number(an.target).toFixed(0)}</span>${an.target_high ? ` · High: $${Number(an.target_high).toFixed(0)}` : ""}${an.n_analysts ? ` · ${an.n_analysts} analysts` : ""}</div>` : "";
      analystEl.innerHTML = `
        <div class="ctitle" style="font-size:10px;margin-bottom:8px"><i class="ti ti-users"></i> Analyst consensus</div>
        <div style="font-size:13px;font-weight:700;color:${recColor};font-family:'Syne',sans-serif;margin-bottom:6px">${recLabel}</div>
        ${tgtLine}${barHtml || `<div style="font-size:10px;color:var(--txt-d)">Breakdown unavailable</div>`}`;
    }
    if (memo) {
      const m = d.memo || { bull: [], bear: [] };
      const html = (m.bull || []).map(p => `<span style="color:var(--lime)">●</span> ${p}<br>`).join("")
                 + (m.bear || []).map(p => `<span style="color:var(--pink)">●</span> ${p}<br>`).join("");
      memo.innerHTML = html || `<span style="color:var(--txt-d)">Not enough data for a memo</span>`;
    }
    // Sector + macro
    const sectorEl = document.getElementById("dd-sector");
    if (sectorEl) {
      const si = d.sector_info || {};
      const mac = si.macro || {};
      const rows = [
        ["Sector", si.sector || "—"], ["Industry", si.industry || "—"],
        ["Country", si.country || "—"], ["Exchange", si.exchange || "—"],
        ["Currency", si.currency || "—"], ["Employees", si.employees ? Number(si.employees).toLocaleString() : "—"],
        ["Beta", si.beta != null ? fmt(si.beta) : "—"], ["Div. Yield", si.dividend_yield != null ? pct(si.dividend_yield) : "—"],
        ["Short Ratio", si.short_ratio != null ? fmt(si.short_ratio) : "—"],
      ].filter(([, v]) => v !== "—");
      const macroRows = mac.country_key ? [
        ["ERP", mac.erp != null ? (mac.erp * 100).toFixed(2) + "%" : "—"],
        ["Country Risk", mac.crp != null ? (mac.crp * 100).toFixed(2) + "%" : "—"],
        ["Risk-Free", mac.rf_pct != null ? mac.rf_pct.toFixed(1) + "%" : "—"],
      ] : [];
      sectorEl.innerHTML = `
        <div class="ctitle" style="font-size:10px;margin-bottom:7px"><i class="ti ti-building-skyscraper"></i> Sector &amp; macro context</div>
        ${rows.map(([l, v]) => `<div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px"><span style="color:var(--txt-d)">${l}</span><span style="color:var(--txt);text-align:right;max-width:55%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${v}</span></div>`).join("")}
        ${macroRows.length ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-size:9px;color:var(--txt-d);margin-bottom:4px">MACRO · ${mac.country_key}</div>
        ${macroRows.map(([l, v]) => `<div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:3px"><span style="color:var(--txt-d)">${l}</span><span style="color:var(--amber)">${v}</span></div>`).join("")}` : ""}`;
    }
    // News section
    const newsEl = document.getElementById("dd-news");
    if (newsEl) {
      const newsList = d.news || [];
      if (!newsList.length) {
        newsEl.innerHTML = `<div style="color:var(--txt-d);font-size:10px">No recent news available</div>`;
      } else {
        newsEl.innerHTML = newsList.map(n =>
          `<div style="display:flex;gap:10px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--border)">
            <div style="flex:1;min-width:0">
              ${n.link ? `<a href="${n.link}" target="_blank" rel="noopener" style="color:var(--txt);font-size:11px;font-family:'DM Mono',monospace;text-decoration:none;line-height:1.4;display:block;white-space:normal;word-break:break-word">${n.title || "—"}</a>`
                       : `<span style="color:var(--txt);font-size:11px;font-family:'DM Mono',monospace;line-height:1.4;display:block">${n.title || "—"}</span>`}
              <div style="font-size:9px;color:var(--txt-d);margin-top:3px">${n.publisher || ""}${n.date ? " · " + n.date : ""}</div>
            </div>
          </div>`
        ).join("");
      }
    }
    renderRevPlotly("dd-revchart", d.revenue_series || []);
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

    // WACC components breakdown
    const waccT = document.getElementById("val-wacc-table");
    if (waccT) {
      const p = (v, d=1) => v != null ? (v*100).toFixed(d)+"%" : "—";
      const f2 = v => v != null ? Number(v).toFixed(2) : "—";
      waccT.querySelector("tbody").innerHTML = `
        <tr><td style="color:var(--txt-d);font-size:10px">Risk-Free (Rf)</td><td style="color:var(--txt)">${p(w.rf)}</td></tr>
        <tr><td style="color:var(--txt-d);font-size:10px">Beta (β)</td><td style="color:var(--txt)">${f2(w.beta)}</td></tr>
        <tr><td style="color:var(--txt-d);font-size:10px">Cost of Equity (Ke)</td><td style="color:var(--blue)">${p(w.ke)}</td></tr>
        <tr><td style="color:var(--txt-d);font-size:10px">Cost of Debt (Kd)</td><td style="color:var(--txt)">${p(w.kd)}</td></tr>
        <tr><td style="color:var(--txt-d);font-size:10px">Tax Rate</td><td style="color:var(--txt)">${p(w.tax_rate)}</td></tr>
        <tr style="border-top:1px solid var(--border)">
          <td style="color:var(--txt-m);font-size:10px;font-weight:600;padding-top:8px">WACC</td>
          <td style="color:var(--cyan);font-weight:700;padding-top:8px">${p(w.wacc)}</td>
        </tr>`;
    }

    // Multi-method price summary
    const methT = document.getElementById("val-methods");
    if (methT && cur) {
      const row = (label, price, col) => {
        if (price == null || isNaN(price)) return "";
        const vs = (price / cur - 1) * 100;
        const vsCol = vs >= 0 ? "var(--lime)" : "var(--pink)";
        return `<tr><td style="color:var(--txt-d);font-size:10px">${label}</td><td style="color:${col}">${dollar(price)}</td><td style="color:${vsCol}">${vs >= 0 ? "+" : ""}${vs.toFixed(1)}%</td></tr>`;
      };
      const ci = d.comps_implied || {}, ddm = d.ddm || {};
      const ddmPrice = (ddm.applicable && ddm.price > 0 && ddm.price < cur * 3) ? ddm.price : null;
      methT.innerHTML =
        row("DCF Base", dcf.price_base, "var(--cyan)") +
        row("DCF Bull", dcf.price_bull, "var(--lime)") +
        row("DCF Bear", dcf.price_bear, "var(--pink)") +
        row("Comps — P/E", ci.price_from_pe, "var(--blue)") +
        row("Comps — EV/EBITDA", ci.price_from_ev_ebitda, "var(--blue)") +
        (ddmPrice ? row("DDM", ddmPrice, "var(--amber)") : "") ||
        `<tr><td colspan="3" style="color:var(--txt-d);text-align:center;padding:10px">No data</td></tr>`;
    }
  } catch (e) {
    if (dcfT) dcfT.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--pink);padding:18px">Could not value ${VAL_TICKER}: ${e.message}</td></tr>`;
  }
}

// ── Backtester (module 3) ────────────────────────────────────────────
const BT = { strategy: "MA Crossover", ticker: "AAPL", start: "2021-01-01", end: "2024-12-31" };
function renderEquityPlotly(divId, strat, stratDates, bench, benchDates, markers, stratLabel, benchLabel) {
  const div = document.getElementById(divId);
  if (!div) return;
  if (!strat || strat.length < 2) {
    div.innerHTML = `<div style="height:240px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-size:11px;font-family:'DM Mono',monospace">No equity data</div>`;
    return;
  }
  const traces = [];
  if (bench && bench.length > 1) {
    traces.push({
      x: benchDates && benchDates.length ? benchDates : bench.map((_, i) => i),
      y: bench, name: benchLabel || "Benchmark", mode: "lines",
      line: { color: "rgba(79,158,255,0.65)", width: 1.4, dash: "dot" },
      hovertemplate: "%{x}<br><b>%{y:.1f}</b><extra>Benchmark</extra>",
    });
  }
  traces.push({
    x: stratDates && stratDates.length ? stratDates : strat.map((_, i) => i),
    y: strat, name: stratLabel || "Strategy", mode: "lines",
    line: { color: "#b8f264", width: 2 },
    hovertemplate: "%{x}<br><b>%{y:.1f}</b><extra>Strategy</extra>",
  });
  const buys = (markers || []).filter(m => m.action === "buy" && m.val != null);
  const sells = (markers || []).filter(m => m.action === "sell" && m.val != null);
  if (buys.length) traces.push({
    x: buys.map(m => m.date), y: buys.map(m => m.val),
    name: "Entry", mode: "markers",
    marker: { color: "#b8f264", symbol: "triangle-up", size: 9, opacity: 0.85,
               line: { color: "rgba(0,0,0,0.4)", width: 1 } },
    hovertemplate: "%{x}<br>Entry @ %{y:.1f}<extra></extra>",
  });
  if (sells.length) traces.push({
    x: sells.map(m => m.date), y: sells.map(m => m.val),
    name: "Exit", mode: "markers",
    marker: { color: "#ff5fa0", symbol: "triangle-down", size: 9, opacity: 0.85,
               line: { color: "rgba(0,0,0,0.4)", width: 1 } },
    hovertemplate: "%{x}<br>Exit @ %{y:.1f}<extra></extra>",
  });
  const layout = {
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    margin: { l: 40, r: 8, t: 8, b: 30 },
    xaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             linecolor: "rgba(255,255,255,0.08)", zeroline: false },
    yaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             tickformat: ".0f", linecolor: "rgba(255,255,255,0.08)", zeroline: false },
    legend: { font: { color: "#b4bdd4", size: 9, family: "DM Mono" }, x: 0.01, y: 0.98,
               bgcolor: "rgba(8,11,18,0.6)", bordercolor: "rgba(255,255,255,0.08)", borderwidth: 1 },
    hovermode: "x unified",
    hoverlabel: { bgcolor: "#131929", bordercolor: "#243559", font: { color: "#e2e8f7", size: 10, family: "DM Mono" } },
  };
  Plotly.newPlot(div, traces, layout, { responsive: true, displayModeBar: false });
}
const _MONTH_ABB = {Jan:"Jan",Feb:"Feb",Mar:"Mar",Apr:"Apr",May:"May",Jun:"Jun",Jul:"Jul",Aug:"Aug",Sep:"Sep",Oct:"Oct",Nov:"Nov",Dec:"Dec",
  January:"Jan",February:"Feb",March:"Mar",April:"Apr",June:"Jun",July:"Jul",August:"Aug",September:"Sep",October:"Oct",November:"Nov",December:"Dec"};
function renderHeatmap(el, monthly) {
  if (!monthly || !monthly.length) { el.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--txt-d);font-size:9px">No monthly data</div>`; return; }
  let labels = "", cells = "";
  monthly.forEach(m => {
    const abbr = _MONTH_ABB[m.month] || (m.month || "").slice(0, 3) || "";
    labels += `<div style="font-size:9px;color:var(--txt-m);text-align:center;font-weight:600;letter-spacing:0.2px">${abbr}</div>`;
    const r = m.ret || 0;
    const a = Math.min(0.85, 0.18 + Math.abs(r) * 7);
    const col = r >= 0 ? `rgba(184,242,100,${a.toFixed(2)})` : `rgba(255,95,160,${a.toFixed(2)})`;
    cells += `<div title="${m.month}: ${(r * 100).toFixed(1)}%" style="height:16px;background:${col};border-radius:2px"></div>`;
  });
  el.innerHTML = labels + cells;
}
async function loadBacktester() {
  const stats = document.getElementById("bt-stats");
  const trades = document.getElementById("bt-trades");
  const heat = document.getElementById("bt-heatmap");
  const title = document.getElementById("bt-eq-title");
  const ticker = document.getElementById("bt-curr-ticker");
  if (stats) stats.innerHTML = `<div class="ts-stat" style="grid-column:1/-1;text-align:center;color:var(--txt-m)">Running backtest…</div>`;
  if (ticker) ticker.textContent = BT.ticker;
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
    if (title) title.innerHTML = `<i class="ti ti-chart-line"></i> ${d.strategy} — ${d.ticker} · ${BT.start.slice(0,4)}–${BT.end.slice(0,4)}`;
    renderEquityPlotly("bt-eqchart", d.equity || [], d.equity_dates || [], d.benchmark || [], d.benchmark_dates || [], d.trade_markers || [], d.strategy, d.benchmark_ticker || "Benchmark");
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
function renderConePlotly(divId, bands, samples, upto) {
  const div = document.getElementById(divId);
  if (!div) return;
  const p10 = bands.p10 || [], p25 = bands.p25 || [], p50 = bands.p50 || [],
        p75 = bands.p75 || [], p90 = bands.p90 || [];
  const Nfull = p50.length;
  if (Nfull < 2) {
    div.innerHTML = `<div style="height:280px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-family:'DM Mono',monospace;font-size:11px">No simulation data</div>`;
    return;
  }
  const n = (upto && upto < Nfull) ? Math.max(2, upto) : Nfull;
  const xs = Array.from({ length: n }, (_, i) => i);
  const traces = [
    { x: [...xs, ...xs.slice().reverse()], y: [...p90.slice(0, n), ...p10.slice(0, n).reverse()],
      fill: "toself", fillcolor: "rgba(79,158,255,0.07)", line: { color: "transparent" },
      name: "P10–P90", hoverinfo: "skip" },
    { x: [...xs, ...xs.slice().reverse()], y: [...p75.slice(0, n), ...p25.slice(0, n).reverse()],
      fill: "toself", fillcolor: "rgba(0,229,204,0.10)", line: { color: "transparent" },
      name: "P25–P75", hoverinfo: "skip" },
    ...(samples || []).slice(0, 8).map((s, i) => ({
      x: xs, y: s.slice(0, n), mode: "lines", line: { color: "rgba(167,139,250,0.20)", width: 0.8 },
      showlegend: false, hoverinfo: "skip"
    })),
    { x: xs, y: p50.slice(0, n), mode: "lines", name: "Median",
      line: { color: "#00e5cc", width: 2 },
      hovertemplate: "Day %{x}<br>Median: $%{y:.2f}<extra></extra>" },
    ...(n >= Nfull ? [
      { x: [n-1], y: [p90[Nfull-1]], mode: "markers+text", text: ["P90"], textposition: "middle right",
        marker: { color: "#b8f264", size: 6 }, showlegend: false, hoverinfo: "skip",
        textfont: { color: "#b8f264", size: 9, family: "DM Mono" } },
      { x: [n-1], y: [p10[Nfull-1]], mode: "markers+text", text: ["P10"], textposition: "middle right",
        marker: { color: "#ff5fa0", size: 6 }, showlegend: false, hoverinfo: "skip",
        textfont: { color: "#ff5fa0", size: 9, family: "DM Mono" } },
    ] : []),
  ];
  const layout = {
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    margin: { l: 38, r: 36, t: 6, b: 28 },
    xaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             title: { text: "days", font: { color: "#6b7a99", size: 9 } }, zeroline: false },
    yaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             tickprefix: "$", zeroline: false },
    legend: { font: { color: "#b4bdd4", size: 9, family: "DM Mono" }, x: 0.01, y: 0.99,
               bgcolor: "rgba(8,11,18,0.6)", bordercolor: "rgba(255,255,255,0.06)", borderwidth: 1 },
    hovermode: "x unified",
    hoverlabel: { bgcolor: "#131929", bordercolor: "#243559", font: { color: "#e2e8f7", size: 10, family: "DM Mono" } },
  };
  Plotly.react(div, traces, layout, { responsive: true, displayModeBar: false });
}

function renderHistPlotly(divId, hist, start) {
  const div = document.getElementById(divId);
  if (!div) return;
  if (!hist || !hist.length) {
    div.innerHTML = `<div style="height:210px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-family:'DM Mono',monospace;font-size:11px">No histogram data</div>`;
    return;
  }
  const xs = hist.map(h => h.x);
  const colors = hist.map(h => h.x >= start ? "rgba(184,242,100,0.55)" : "rgba(255,95,160,0.45)");
  const traces = [
    { x: xs, y: hist.map(h => h.count), type: "bar", marker: { color: colors },
      hovertemplate: "Price: $%{x:.1f}<br>Count: %{y}<extra></extra>" },
  ];
  const shapes = [{
    type: "line", x0: start, x1: start, y0: 0, y1: 1, yref: "paper",
    line: { color: "#f59e0b", width: 1.5, dash: "dot" }
  }];
  const annotations = [{
    x: start, y: 1, yref: "paper", text: "Start", showarrow: false,
    font: { color: "#f59e0b", size: 9, family: "DM Mono" }, xanchor: "left", yanchor: "top"
  }];
  const layout = {
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    margin: { l: 36, r: 10, t: 6, b: 28 },
    xaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             tickprefix: "$", zeroline: false },
    yaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" }, zeroline: false },
    bargap: 0.05, shapes, annotations,
    hovermode: "x", showlegend: false,
    hoverlabel: { bgcolor: "#131929", bordercolor: "#243559", font: { color: "#e2e8f7", size: 10, family: "DM Mono" } },
  };
  Plotly.react(div, traces, layout, { responsive: true, displayModeBar: false });
}

async function loadMonteCarlo() {
  const kp = document.getElementById("mc-kpis"),
        coneDiv = document.getElementById("mc-conechart"),
        histDiv = document.getElementById("mc-histchart"),
        risk = document.getElementById("mc-risk");
  if (kp) kp.innerHTML = `<div class="kpi c" style="grid-column:1/-1;text-align:center;color:var(--txt-m)">Simulating ${MC_TICKER}…</div>`;
  if (coneDiv) { Plotly.purge(coneDiv); coneDiv.innerHTML = `<div style="height:280px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-family:'DM Mono',monospace;font-size:11px">running…</div>`; }
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
    if (coneDiv) {
      if (_mcAnim) { clearInterval(_mcAnim); _mcAnim = null; }
      const _N = ((d.bands && d.bands.p50) || []).length;
      let _k = 2;
      renderConePlotly("mc-conechart", d.bands || {}, d.sample_paths || [], _k);
      _mcAnim = setInterval(() => {
        _k += Math.max(1, Math.floor(_N / 40));
        if (_k >= _N) { _k = _N; clearInterval(_mcAnim); _mcAnim = null; }
        renderConePlotly("mc-conechart", d.bands || {}, d.sample_paths || [], _k);
      }, 40);
    }
    renderHistPlotly("mc-histchart", d.histogram || [], d.start_price);
    if (risk) {
      const rf = (lbl, val, col) => `<div class="dcf-field"><div class="dcf-lbl">${lbl}</div><div style="font-size:14px;font-weight:700;color:${col};font-family:'Syne',sans-serif;margin-top:3px">${val}</div></div>`;
      risk.innerHTML = rf("VaR (95%)", pct(rm.var_95, 1), "var(--pink)") + rf("CVaR (95%)", pct(rm.cvar_95, 1), "var(--pink)") +
        rf("Expected Ret", pctSigned(rm.expected_return), "var(--cyan)") +
        rf("Median Price", rm.p50_price != null ? "$" + Number(rm.p50_price).toFixed(0) : "—", "var(--blue)");
    }
    const meta = document.getElementById("mc-meta");
    if (meta) meta.innerHTML = `<span style="color:var(--txt-m)">Model: <span style="color:var(--cyan)">${(d.model || "gbm").toUpperCase()}</span></span><span style="color:var(--txt-m)">Horizon: <span style="color:var(--txt)">${d.horizon}d</span></span><span style="color:var(--txt-m)">Paths: <span style="color:var(--txt)">2,000</span></span><span style="color:var(--txt-m)">Start: <span style="color:var(--txt)">$${Number(d.start_price).toFixed(0)}</span></span>`;
    // Trade setup panel
    const tradeSetup = document.getElementById("mc-trade-setup");
    if (tradeSetup && d.bands && d.start_price) {
      const bands = d.bands;
      const n = (bands.p50 || []).length;
      const step = Math.max(1, Math.round(d.horizon / 80));
      const idx30 = Math.min(Math.round(30 / step), n - 1);
      const idx60 = Math.min(Math.round(60 / step), n - 1);
      const idx90 = Math.min(Math.round(90 / step), n - 1);
      const cur = d.start_price;
      const t30 = bands.p50 && bands.p50[idx30];
      const t60 = bands.p50 && bands.p50[idx60];
      const t90 = bands.p50 && bands.p50[idx90];
      const stop30 = bands.p10 && bands.p10[idx30];
      const bull90 = bands.p90 && bands.p90[idx90];
      const upside90 = t90 ? (t90 / cur - 1) * 100 : null;
      let sigLabel = "HOLD", sigColor = "var(--amber)";
      if (upside90 != null && upside90 > 7) { sigLabel = "LONG"; sigColor = "var(--lime)"; }
      else if (upside90 != null && upside90 < -7) { sigLabel = "SHORT"; sigColor = "var(--pink)"; }
      const stopPct = stop30 ? ((stop30 / cur - 1) * 100).toFixed(1) : null;
      const rr = (t90 && stop30 && stop30 < cur) ? ((t90 - cur) / (cur - stop30)).toFixed(1) : null;
      const cell = (lbl, val, col, sub) => `<div class="dcf-field" style="text-align:center">
        <div class="dcf-lbl">${lbl}</div>
        <div style="font-size:14px;font-weight:700;color:${col || "var(--txt)"};font-family:'Syne',sans-serif;margin-top:3px">${val}</div>
        ${sub ? `<div style="font-size:9px;color:var(--txt-d);margin-top:1px">${sub}</div>` : ""}
      </div>`;
      tradeSetup.innerHTML =
        cell("Signal", sigLabel, sigColor, "MC-derived") +
        cell("Entry", `$${cur.toFixed(0)}`, "var(--txt)", "current price") +
        cell("Stop Loss", stop30 ? `$${stop30.toFixed(0)}` : "—", "var(--pink)", stopPct != null ? `${stopPct}% · 30d P10` : "30d P10") +
        cell("Target (90d)", t90 ? `$${t90.toFixed(0)}` : "—", "var(--lime)", upside90 != null ? `${upside90 >= 0 ? "+" : ""}${upside90.toFixed(1)}% upside` : "") +
        cell("Bull Target", bull90 ? `$${bull90.toFixed(0)}` : "—", "var(--cyan)", "90d P90") +
        (rr ? `<div class="dcf-field" style="text-align:center"><div class="dcf-lbl">Risk/Reward</div><div style="font-size:14px;font-weight:700;color:${parseFloat(rr) >= 2 ? "var(--lime)" : "var(--amber)"};font-family:'Syne',sans-serif;margin-top:3px">${rr} : 1</div><div style="font-size:9px;color:var(--txt-d);margin-top:1px">target vs stop</div></div>` : "");
    }
  } catch (e) {
    if (kp) kp.innerHTML = `<div class="kpi c" style="grid-column:1/-1;text-align:center;color:var(--pink)">Simulation failed: ${e.message}</div>`;
  }
}

// ── Strategy Library (module 5) ──────────────────────────────────────
function renderPerfBarsPlotly(divId, strats) {
  const div = document.getElementById(divId);
  if (!div) return;
  if (!strats.length) {
    div.innerHTML = `<div style="height:240px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-family:'DM Mono',monospace;font-size:11px">No strategy data</div>`;
    return;
  }
  const names = strats.map(s => (s.name || "").replace(/ /g, "<br>"));
  const rets = strats.map(s => +((s.total_return || 0) * 100).toFixed(1));
  const sharpes = strats.map(s => +(s.sharpe || 0).toFixed(2));
  const colors = rets.map(r => r >= 0 ? "rgba(184,242,100,0.5)" : "rgba(255,95,160,0.45)");
  const borderColors = rets.map(r => r >= 0 ? "#b8f264" : "#ff5fa0");
  const traces = [{
    x: strats.map(s => s.name || ""),
    y: rets,
    type: "bar",
    marker: { color: colors, line: { color: borderColors, width: 1 } },
    customdata: sharpes,
    hovertemplate: "<b>%{x}</b><br>Return: %{y:.1f}%<br>Sharpe: %{customdata:.2f}<extra></extra>",
  }];
  const layout = {
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    margin: { l: 36, r: 10, t: 6, b: 70 },
    xaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 8, family: "DM Mono" },
             tickangle: -30, zeroline: false },
    yaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             ticksuffix: "%", zeroline: true, zerolinecolor: "rgba(180,189,212,0.25)", zerolinewidth: 1 },
    bargap: 0.4, showlegend: false,
    hovermode: "closest",
    hoverlabel: { bgcolor: "#131929", bordercolor: "#243559", font: { color: "#e2e8f7", size: 10, family: "DM Mono" } },
  };
  Plotly.react(div, traces, layout, { responsive: true, displayModeBar: false });
}
function stratDecision(s) {
  if (!s || s.error) return { label: "N/A", color: "var(--txt-d)", note: "Could not backtest on this ticker." };
  const sh = s.sharpe || 0, ret = s.total_return || 0;
  if (sh >= 1.5 && ret >= 0.10) return { label: "BUY", color: "var(--lime)",  note: `Strong risk-adjusted returns (Sharpe ${fmt(sh,2)}). Favorable conditions for this strategy.` };
  if (sh < 0.3 || ret < -0.05)  return { label: "AVOID", color: "var(--pink)", note: `Weak performance on this ticker. Consider waiting for better conditions.` };
  return { label: "HOLD", color: "var(--amber)", note: `Moderate performance (Sharpe ${fmt(sh,2)}). Worth monitoring but not a strong signal.` };
}

async function loadStrategies() {
  const kp = document.getElementById("sl-kpis"), cards = document.getElementById("sl-cards"),
        rec = document.getElementById("sl-recommended"),
        recName = document.getElementById("sl-rec-name"), recNote = document.getElementById("sl-rec-note");
  if (cards) cards.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--txt-m);padding:20px">Backtesting strategies…</div>`;
  if (rec) rec.style.display = "none";
  try {
    const res = await fetch(`/api/strategies?ticker=${DD_TICKER}`);
    const d = await res.json();
    if (!res.ok || (d.error && !(d.strategies || []).length)) throw new Error(d.error || `API ${res.status}`);
    const list = d.strategies || [], valid = list.filter(s => !s.error && s.sharpe != null);
    if (kp) {
      const best = valid.reduce((a, b) => ((b.sharpe || -99) > (a.sharpe || -99) ? b : a), valid[0] || {});
      const avgRet = valid.length ? valid.reduce((a, b) => a + (b.total_return || 0), 0) / valid.length : null;
      kp.innerHTML = `
        <div class="kpi b"><div class="kpi-lbl">Strategies</div><div class="kpi-val b">${list.length}</div><div class="kpi-sub">on ${d.ticker}</div></div>
        <div class="kpi l"><div class="kpi-lbl">Best Sharpe</div><div class="kpi-val l">${fmt(best.sharpe, 2)}</div><div class="kpi-sub">${(best.name || "").slice(0, 18)}</div></div>
        <div class="kpi c"><div class="kpi-lbl">Avg Total Return</div><div class="kpi-val c">${pctSigned(avgRet)}</div><div class="kpi-sub">2021–24 on ${d.ticker}</div></div>
        <div class="kpi a"><div class="kpi-lbl">Reference</div><div class="kpi-val w" style="font-size:16px;padding-top:5px">${d.ticker}</div><div class="kpi-sub">single-name test</div></div>`;
      if (rec && best.name) {
        const dec = stratDecision(best);
        if (recName) recName.textContent = best.name;
        if (recNote) recNote.innerHTML = `<span style="color:${dec.color};font-weight:700">${dec.label}</span> — ${dec.note}`;
        rec.style.display = "block";
      }
    }
    if (cards) cards.innerHTML = list.map(s => {
      const dec = stratDecision(s);
      const tag = s.error
        ? `<span class="strat-tag" style="color:var(--pink)">n/a here</span>`
        : `<span class="strat-tag">Sharpe ${fmt(s.sharpe, 2)}</span><span class="strat-tag" style="color:${(s.total_return || 0) >= 0 ? "var(--lime)" : "var(--pink)"}">${pctSigned(s.total_return)}</span>`;
      const decBadge = `<span class="strat-tag" style="color:${dec.color};border-color:${dec.color};opacity:0.85">${dec.label}</span>`;
      const safeName = (s.name || "").replace(/&/g,"&amp;").replace(/"/g,"&quot;");
      return `<div class="strat-card" title="Click to backtest this strategy" data-strat="${safeName}">
        <div class="strat-name">${s.name}</div>
        <div class="strat-desc">${s.description || ""}</div>
        <div style="font-size:9px;color:var(--txt-d);margin:4px 0 6px">${dec.note}</div>
        <div class="strat-meta">${tag}${decBadge}</div>
        <div style="font-size:9px;color:var(--blue);margin-top:6px;opacity:0.7">▶ Click to backtest →</div>
      </div>`;
    }).join("");
    renderPerfBarsPlotly("sl-perfchart", valid);
  } catch (e) {
    if (cards) cards.innerHTML = `<div style="grid-column:1/-1;text-align:center;color:var(--pink);padding:20px">Could not load strategies: ${e.message}</div>`;
  }
}

window.sendToBacktester = function(stratName) {
  BT.strategy = stratName;
  const sel = document.getElementById("bt-strategy-sel");
  if (sel) sel.value = stratName;
  delete loaded[3];
  window.switchModule(3, null);
};

// ── Portfolio Optimizer (module 6) ───────────────────────────────────
let PO_BASKET = ["NVDA", "META", "LLY", "AVGO", "AAPL", "MSFT", "JPM", "UNH"];

function renderPoChips() {
  const el = document.getElementById("po-chips");
  if (!el) return;
  el.innerHTML = PO_BASKET.map(sym =>
    `<span style="display:inline-flex;align-items:center;gap:3px;background:rgba(79,158,255,0.12);border:1px solid rgba(79,158,255,0.3);border-radius:4px;padding:2px 6px;font-size:10px;font-family:'DM Mono',monospace;color:var(--blue)">
      ${sym}
      <span data-rm="${sym}" style="cursor:pointer;color:#6b7a99;font-size:11px;line-height:1;margin-left:1px" title="Remove">✕</span>
    </span>`
  ).join("");
  el.querySelectorAll("[data-rm]").forEach(btn => {
    btn.addEventListener("click", () => {
      PO_BASKET = PO_BASKET.filter(s => s !== btn.dataset.rm);
      renderPoChips();
    });
  });
}

function renderFrontierPlotly(divId, frontier, maxSharpe, minVol) {
  const div = document.getElementById(divId);
  if (!div) return;
  if (!frontier || !frontier.length) {
    div.innerHTML = `<div style="height:230px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-family:'DM Mono',monospace;font-size:11px">No frontier data</div>`;
    return;
  }
  const fVols = frontier.map(p => +(p[0] * 100).toFixed(2));
  const fRets = frontier.map(p => +(p[1] * 100).toFixed(2));
  const traces = [
    { x: fVols, y: fRets, mode: "markers", name: "Portfolios",
      marker: { color: "rgba(255,255,255,0.12)", size: 3 },
      hovertemplate: "Vol: %{x:.1f}%<br>Ret: %{y:.1f}%<extra></extra>" },
    { x: [+(minVol[0] * 100).toFixed(2)], y: [+(minVol[1] * 100).toFixed(2)],
      mode: "markers+text", name: "Min Vol", text: ["Min Vol"],
      textposition: "top right", textfont: { color: "#b4bdd4", size: 9, family: "DM Mono" },
      marker: { color: "#b4bdd4", size: 9, symbol: "diamond" },
      hovertemplate: "Min Vol<br>Vol: %{x:.1f}%<br>Ret: %{y:.1f}%<extra></extra>" },
    { x: [+(maxSharpe[0] * 100).toFixed(2)], y: [+(maxSharpe[1] * 100).toFixed(2)],
      mode: "markers+text", name: "★ Max Sharpe", text: ["★ Max Sharpe"],
      textposition: "top right", textfont: { color: "#b8f264", size: 9, family: "DM Mono" },
      marker: { color: "#b8f264", size: 11, symbol: "star" },
      hovertemplate: "Max Sharpe<br>Vol: %{x:.1f}%<br>Ret: %{y:.1f}%<extra></extra>" },
  ];
  const layout = {
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    margin: { l: 40, r: 10, t: 6, b: 30 },
    xaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             ticksuffix: "%", title: { text: "Volatility", font: { color: "#6b7a99", size: 9 } }, zeroline: false },
    yaxis: { gridcolor: "rgba(255,255,255,0.04)", tickfont: { color: "#6b7a99", size: 9, family: "DM Mono" },
             ticksuffix: "%", title: { text: "Return", font: { color: "#6b7a99", size: 9 } }, zeroline: false },
    legend: { font: { color: "#b4bdd4", size: 9, family: "DM Mono" }, x: 0.01, y: 0.01,
               bgcolor: "rgba(8,11,18,0.6)", bordercolor: "rgba(255,255,255,0.06)", borderwidth: 1 },
    hovermode: "closest",
    hoverlabel: { bgcolor: "#131929", bordercolor: "#243559", font: { color: "#e2e8f7", size: 10, family: "DM Mono" } },
  };
  Plotly.react(div, traces, layout, { responsive: true, displayModeBar: false });
}

function renderCorrPlotly(divId, corr) {
  const div = document.getElementById(divId);
  if (!div) return;
  const syms = corr.symbols || [], m = corr.matrix || [];
  if (!syms.length) {
    div.innerHTML = `<div style="height:200px;display:flex;align-items:center;justify-content:center;color:#b4bdd4;font-family:'DM Mono',monospace;font-size:11px">No correlation data</div>`;
    return;
  }
  const zVals = m;
  const traces = [{
    z: zVals, x: syms, y: syms, type: "heatmap",
    colorscale: [
      [0, "rgba(255,95,160,0.85)"], [0.5, "rgba(20,28,46,0.9)"], [1, "rgba(0,229,204,0.85)"]
    ],
    zmin: -1, zmax: 1,
    text: zVals.map(row => row.map(v => v.toFixed(2))),
    texttemplate: "%{text}",
    textfont: { color: "#e2e8f7", size: 10, family: "DM Mono" },
    hovertemplate: "%{y} / %{x}<br>Correlation: %{z:.3f}<extra></extra>",
    showscale: false,
  }];
  const nSym = syms.length;
  const tickFontSize = nSym > 8 ? 8 : nSym > 6 ? 9 : 10;
  const leftMargin = nSym > 8 ? 62 : 54;
  const layout = {
    paper_bgcolor: "transparent", plot_bgcolor: "transparent",
    margin: { l: leftMargin, r: 4, t: 4, b: leftMargin },
    xaxis: { tickfont: { color: "#b4bdd4", size: tickFontSize, family: "DM Mono" }, side: "bottom", tickangle: nSym > 6 ? -30 : 0 },
    yaxis: { tickfont: { color: "#b4bdd4", size: tickFontSize, family: "DM Mono" }, autorange: "reversed" },
    hovermode: "closest",
    hoverlabel: { bgcolor: "#131929", bordercolor: "#243559", font: { color: "#e2e8f7", size: 10, family: "DM Mono" } },
  };
  Plotly.react(div, traces, layout, { responsive: true, displayModeBar: false });
}

async function loadPortfolio() {
  const kp = document.getElementById("po-kpis"), wts = document.getElementById("po-weights");
  if (wts) wts.innerHTML = `<div style="text-align:center;color:var(--txt-m);padding:14px">Optimizing portfolio…</div>`;
  try {
    const tickerParam = PO_BASKET.join(",");
    const res = await fetch(`/api/portfolio?tickers=${encodeURIComponent(tickerParam)}`);
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
    renderFrontierPlotly("po-frontierchart", d.frontier || [], d.max_sharpe || [0, 0], d.min_vol || [0, 0]);
    renderCorrPlotly("po-corr", d.correlation || {});

    // Position summary table
    const poSummary = document.getElementById("po-position-summary");
    if (poSummary && d.weights && d.weights.length) {
      const n = d.weights.length;
      const eqWt = 100 / n;
      const maxW = Math.max(...d.weights.map(w => w.weight));
      const riskCols = { high: "var(--pink)", medium: "var(--amber)", low: "var(--lime)" };
      poSummary.innerHTML = d.weights.map(w => {
        const wPct = (w.weight * 100).toFixed(1);
        const barW = Math.round(w.weight / maxW * 100);
        const retCol = (w.ret || 0) >= 0 ? "var(--lime)" : "var(--pink)";
        const diffW = (w.weight * 100 - eqWt);
        const diffStr = (diffW >= 0 ? "+" : "") + diffW.toFixed(1) + "pp";
        const diffCol = diffW >= 0 ? "var(--cyan)" : "var(--txt-d)";
        const risk = w.risk || "low";
        const riskCol = riskCols[risk] || "var(--txt-d)";
        const riskIcon = risk === "high" ? "⚠" : risk === "medium" ? "◎" : "✓";
        return `<tr>
          <td style="font-weight:600;color:var(--txt);font-size:11px;padding-left:4px">${w.symbol}</td>
          <td style="text-align:center;color:var(--cyan)">${wPct}%</td>
          <td style="text-align:center;color:${diffCol};font-size:10px">${eqWt.toFixed(1)}% <span style="font-size:9px">(${diffStr})</span></td>
          <td style="text-align:center;color:${retCol}">${pctSigned(w.ret)}</td>
          <td style="text-align:center" title="β ${w.beta != null ? Number(w.beta).toFixed(2) : "—"} · σ ${w.ann_vol != null ? pct(w.ann_vol) : "—"}">
            <span style="color:${riskCol};font-size:10px;font-weight:600">${riskIcon} ${risk}</span>
          </td>
          <td style="padding-left:12px">
            <div style="height:7px;background:rgba(255,255,255,0.06);border-radius:4px;overflow:hidden">
              <div style="width:${barW}%;height:100%;background:var(--blue);border-radius:4px"></div>
            </div>
          </td>
        </tr>`;
      }).join("");
    }
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

// ── Search autocomplete ──────────────────────────────────────────────
let _searchTimer = null, _ddIdx = -1;

function _buildDropdown(results) {
  const dd = document.getElementById("search-dropdown");
  if (!dd) return;
  if (!results || !results.length) { dd.style.display = "none"; return; }
  dd.innerHTML = results.map((r, i) =>
    `<div class="search-item" data-sym="${r.symbol}" data-i="${i}">
      <span class="si-sym">${r.symbol}</span>
      <span class="si-name">${r.name || ""}</span>
      <span class="si-exch">${r.exch || ""}</span>
    </div>`
  ).join("");
  dd.style.display = "block";
  _ddIdx = -1;
  dd.querySelectorAll(".search-item").forEach(el => {
    el.addEventListener("click", () => _pickSearch(el.dataset.sym));
    el.addEventListener("mouseenter", () => {
      dd.querySelectorAll(".search-item").forEach(e => e.classList.remove("hi"));
      el.classList.add("hi");
      _ddIdx = parseInt(el.dataset.i);
    });
  });
}

let _lastSearchedSym = "";
function _pickSearch(sym) {
  const dd = document.getElementById("search-dropdown");
  const inp = document.getElementById("ticker-search");
  const wlBtn = document.getElementById("search-wl-btn");
  if (dd) dd.style.display = "none";
  if (inp) { inp.value = ""; inp.blur(); }
  _lastSearchedSym = sym;
  if (wlBtn) { wlBtn.textContent = `+ ${sym}`; wlBtn.style.display = "inline-flex"; }
  selectTicker(sym);
}

async function resolveAndSelect(q) {
  q = (q || "").trim();
  if (!q) return;
  try {
    const r = await (await fetch(`/api/search?q=${encodeURIComponent(q)}`)).json();
    const sym = (r.results && r.results[0] && r.results[0].symbol) || q.toUpperCase();
    _pickSearch(sym);
  } catch (e) { _pickSearch(q.toUpperCase()); }
}

// ── Sidebar watchlist ────────────────────────────────────────────────
async function loadSidebarWatchlist() {
  const el = document.getElementById("sidebar-watchlist");
  if (!el) return;
  try {
    const res = await fetch("/api/watchlist");
    const d = await res.json();
    const items = d.tickers || [];
    if (!items.length) {
      el.innerHTML = `<div style="font-size:10px;color:var(--txt-d);padding:4px 0">Empty — add tickers below</div>`;
      return;
    }
    el.innerHTML = items.map(it => {
      const chg = it.change_pct;
      const chgStr = chg != null ? (chg >= 0 ? `+${chg.toFixed(2)}%` : `${chg.toFixed(2)}%`) : "—";
      const cls = chg == null ? "" : chg >= 0 ? "wl-up" : "wl-dn";
      const rmBtn = `<span data-wl-rm="${it.symbol}" style="margin-left:auto;cursor:pointer;color:#3d4f70;font-size:10px;padding:0 2px" title="Remove">✕</span>`;
      return `<div class="wl-row" style="gap:4px"><span class="wl-sym" style="cursor:pointer" onclick="selectTicker('${it.symbol}')">${it.symbol}</span><span class="${cls}">${chgStr}</span>${rmBtn}</div>`;
    }).join("");
    el.querySelectorAll("[data-wl-rm]").forEach(btn => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/watchlist/${btn.dataset.wlRm}`, { method: "DELETE" });
        loadSidebarWatchlist();
      });
    });
  } catch (e) {
    el.innerHTML = `<div style="font-size:10px;color:var(--txt-d)">—</div>`;
  }
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

  // Search: autocomplete dropdown + Enter/arrow keys
  const search = document.getElementById("ticker-search");
  const dd = document.getElementById("search-dropdown");
  if (search) {
    search.addEventListener("input", () => {
      const q = search.value.trim();
      clearTimeout(_searchTimer);
      if (!q) { if (dd) dd.style.display = "none"; return; }
      _searchTimer = setTimeout(async () => {
        try {
          const r = await (await fetch(`/api/search?q=${encodeURIComponent(q)}`)).json();
          _buildDropdown(r.results || []);
        } catch (_) {}
      }, 280);
    });
    search.addEventListener("keydown", e => {
      const items = dd ? [...dd.querySelectorAll(".search-item")] : [];
      if (e.key === "ArrowDown") {
        e.preventDefault();
        _ddIdx = Math.min(_ddIdx + 1, items.length - 1);
        items.forEach((el, i) => el.classList.toggle("hi", i === _ddIdx));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        _ddIdx = Math.max(_ddIdx - 1, 0);
        items.forEach((el, i) => el.classList.toggle("hi", i === _ddIdx));
      } else if (e.key === "Enter") {
        if (_ddIdx >= 0 && items[_ddIdx]) { _pickSearch(items[_ddIdx].dataset.sym); }
        else { resolveAndSelect(search.value); }
      } else if (e.key === "Escape") {
        if (dd) dd.style.display = "none";
      }
    });
  }
  document.addEventListener("click", ev => {
    const wrap = document.querySelector(".search");
    if (dd && wrap && !wrap.contains(ev.target)) dd.style.display = "none";
  });

  // Deep Dive interval + indicator chips
  const iv = document.getElementById("dd-interval");
  if (iv) iv.addEventListener("change", () => { ddInterval = iv.value; loadCandles(); });
  document.querySelectorAll(".ind-btn").forEach(b => b.addEventListener("click", () => {
    if (b.id === "mc-run" || b.id === "bt-run-btn") return;
    const k = b.dataset.ind;
    if (!k) return;
    if (ddIndicators.has(k)) { ddIndicators.delete(k); b.classList.remove("on"); }
    else { ddIndicators.add(k); b.classList.add("on"); }
    loadCandles();
  }));

  // Backtester: strategy selector + run button
  const btSel = document.getElementById("bt-strategy-sel");
  if (btSel) btSel.addEventListener("change", () => { BT.strategy = btSel.value; });
  const btRun = document.getElementById("bt-run-btn");
  if (btRun) btRun.addEventListener("click", () => { BT.strategy = (btSel && btSel.value) || BT.strategy; delete loaded[3]; loadBacktester(); });

  // Strategy Library → Backtester interlink (event delegation — cards are dynamically rendered)
  const slCards = document.getElementById("sl-cards");
  if (slCards) slCards.addEventListener("click", e => {
    const card = e.target.closest("[data-strat]");
    if (card && card.dataset.strat) window.sendToBacktester(card.dataset.strat);
  });

  // Topbar refresh
  const rf = document.getElementById("topbar-refresh");
  if (rf) rf.addEventListener("click", () => { delete loaded[_curModule]; if (loaders[_curModule]) loaders[_curModule](); });

  // Monte Carlo
  const mcRun = document.getElementById("mc-run");
  if (mcRun) mcRun.addEventListener("click", () => loadMonteCarlo());
  const mcModel = document.getElementById("mc-model");
  if (mcModel) mcModel.addEventListener("change", () => loadMonteCarlo());

  // Search bar "+" to add to watchlist
  const searchWlBtn = document.getElementById("search-wl-btn");
  if (searchWlBtn) {
    searchWlBtn.addEventListener("click", async () => {
      const sym = _lastSearchedSym;
      if (!sym) return;
      await fetch(`/api/watchlist/${sym}`, { method: "POST" });
      searchWlBtn.textContent = `✓ ${sym}`;
      searchWlBtn.style.color = "var(--lime)";
      setTimeout(() => { searchWlBtn.style.display = "none"; searchWlBtn.style.color = ""; }, 1500);
      loadSidebarWatchlist();
    });
  }

  // Portfolio basket editor with autocomplete
  renderPoChips();
  const poAddBtn = document.getElementById("po-add-btn");
  const poAddInput = document.getElementById("po-add-input");
  const poRunBtn = document.getElementById("po-run-btn");
  let _poDdTimer = null;
  // Build a separate dropdown element for portfolio add input
  const poDd = document.createElement("div");
  poDd.style.cssText = "display:none;position:absolute;z-index:9999;top:calc(100% + 4px);left:0;right:0;background:#131929;border:1px solid #243559;border-radius:8px;max-height:200px;overflow-y:auto;box-shadow:0 6px 20px rgba(0,0,0,0.6)";
  if (poAddInput && poAddInput.parentElement) {
    poAddInput.parentElement.style.position = "relative";
    poAddInput.parentElement.appendChild(poDd);
  }
  function _poBuildDd(results) {
    if (!results || !results.length) { poDd.style.display = "none"; return; }
    poDd.innerHTML = results.map(r =>
      `<div data-sym="${r.symbol}" style="padding:7px 12px;cursor:pointer;font-family:'DM Mono',monospace;font-size:11px;display:flex;gap:8px;align-items:center;border-bottom:1px solid rgba(255,255,255,0.04)">
        <span style="color:var(--txt);font-weight:600">${r.symbol}</span>
        <span style="color:#6b7a99;font-size:10px;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${r.name || ""}</span>
        <span style="color:#3d4f70;font-size:9px">${r.exch || ""}</span>
      </div>`).join("");
    poDd.style.display = "block";
    poDd.querySelectorAll("[data-sym]").forEach(el => {
      el.addEventListener("mouseenter", () => el.style.background = "rgba(79,158,255,0.08)");
      el.addEventListener("mouseleave", () => el.style.background = "");
      el.addEventListener("click", () => {
        const sym = el.dataset.sym;
        if (sym && !PO_BASKET.includes(sym)) { PO_BASKET.push(sym); renderPoChips(); }
        if (poAddInput) poAddInput.value = "";
        poDd.style.display = "none";
      });
    });
  }
  if (poAddInput) {
    poAddInput.addEventListener("input", () => {
      const q = poAddInput.value.trim();
      clearTimeout(_poDdTimer);
      if (!q) { poDd.style.display = "none"; return; }
      _poDdTimer = setTimeout(async () => {
        try {
          const r = await (await fetch(`/api/search?q=${encodeURIComponent(q)}`)).json();
          _poBuildDd(r.results || []);
        } catch (_) {}
      }, 280);
    });
    poAddInput.addEventListener("keydown", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        const sym = poAddInput.value.trim().toUpperCase();
        if (sym && !PO_BASKET.includes(sym)) { PO_BASKET.push(sym); renderPoChips(); }
        poAddInput.value = ""; poDd.style.display = "none";
      } else if (e.key === "Escape") { poDd.style.display = "none"; }
    });
  }
  if (poAddBtn) poAddBtn.addEventListener("click", () => {
    const sym = (poAddInput ? poAddInput.value.trim().toUpperCase() : "");
    if (sym && !PO_BASKET.includes(sym)) { PO_BASKET.push(sym); renderPoChips(); if (poAddInput) poAddInput.value = ""; }
  });
  if (poRunBtn) poRunBtn.addEventListener("click", () => {
    delete loaded[6];
    loadPortfolio();
  });
  document.addEventListener("click", ev => {
    if (poAddInput && !poAddInput.contains(ev.target) && !poDd.contains(ev.target)) poDd.style.display = "none";
  });

  // Sidebar watchlist + auto-refresh
  loadSidebarWatchlist();
  setInterval(loadSidebarWatchlist, 30000);  // refresh prices every 30s
  const wlAddBtn = document.getElementById("wl-add-btn");
  const wlAddRow = document.getElementById("wl-add-row");
  const wlAddInput = document.getElementById("wl-add-input");
  if (wlAddBtn) {
    wlAddBtn.addEventListener("click", () => {
      if (!wlAddRow) return;
      const visible = wlAddRow.style.display !== "none";
      wlAddRow.style.display = visible ? "none" : "block";
      if (!visible && wlAddInput) wlAddInput.focus();
    });
  }
  if (wlAddInput) {
    wlAddInput.addEventListener("keydown", async e => {
      if (e.key !== "Enter") return;
      const sym = wlAddInput.value.trim().toUpperCase();
      if (!sym) return;
      await fetch(`/api/watchlist/${sym}`, { method: "POST" });
      wlAddInput.value = "";
      if (wlAddRow) wlAddRow.style.display = "none";
      loadSidebarWatchlist();
    });
  }

  onModule(0);  // Screener active on load
});
