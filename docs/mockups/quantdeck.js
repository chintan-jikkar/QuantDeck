/* QuantDeck — shared shell + theme + Plotly helpers (mockups) */
(function () {
  const I = {
    screener:  '<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
    deepdive:  '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    valuation: '<path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    simulation:'<path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/>',
    backtester:'<path d="M3 3v18h18"/><rect x="7" y="10" width="3" height="7"/><rect x="13" y="6" width="3" height="11"/>',
    watchlist: '<path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>',
    settings:  '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/>',
    moon: '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    sun:  '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  };
  const svg = (p, w) => `<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w||2}">${p}</svg>`;
  const NAV = [
    ['ANALYSIS', [['screener','Screener','1-screener.html'],['deepdive','Deep Dive','2-deep-dive.html'],['valuation','Valuation','3-valuation.html']]],
    ['MODELING', [['simulation','Simulation','4-simulation.html'],['backtester','Backtester','5-backtester.html']]],
  ];

  function sidebarHTML(active) {
    let h = `<a class="brand" href="index.html" style="text-decoration:none;color:inherit"><div class="logo">Q</div><div class="name">Quant<span>Deck</span></div></a>`;
    NAV.forEach(([label, items]) => {
      h += `<div class="nav-label">${label}</div>`;
      items.forEach(([key, name, href]) => {
        h += `<a class="nav-item ${key===active?'active':''}" href="${href}">${svg(I[key])} ${name}</a>`;
      });
    });
    h += `<div class="spacer"></div>`;
    h += `<a class="nav-item" href="#">${svg(I.watchlist)} Watchlist</a>`;
    h += `<a class="nav-item" href="#">${svg(I.settings)} Settings</a>`;
    return h;
  }
  function topbarHTML(placeholder) {
    return `<div class="search">${svg(I.search,2)}<input placeholder="${placeholder||'Search ticker: AAPL, EURUSD=X, GC=F'}"></div>
      <div class="grow"></div>
      <button class="icon-btn" id="themeToggle" title="Toggle theme">
        <svg id="moonIcon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${I.moon}</svg>
        <svg id="sunIcon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:none">${I.sun}</svg>
      </button>
      <button class="icon-btn" title="Notifications"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${I.bell}</svg></button>
      <div class="avatar">CJ</div>`;
  }

  const themeCbs = [];
  function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function onTheme(cb) { themeCbs.push(cb); cb(); }
  function plotlyBase() {
    const grid = cssVar('--border-strong'), txt = cssVar('--text-muted');
    return {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Space Grotesk', size: 11, color: txt },
      xaxis: { gridcolor: grid, griddash: 'dot', zeroline: false },
      yaxis: { gridcolor: grid, griddash: 'dot', zeroline: false },
      hoverlabel: { bgcolor: cssVar('--panel-2'), bordercolor: cssVar('--border-strong'), font: { family: 'Space Grotesk', color: cssVar('--text') } },
      margin: { l: 44, r: 14, t: 10, b: 36 }, showlegend: false,
    };
  }
  function logoBadge(tk, cls) {
    return `<div class="badge ${cls||''}"><img src="https://financialmodelingprep.com/image-stock/${tk}.png" alt="${tk}"
      onerror="this.parentElement.style.background='var(--violet)';this.parentElement.style.padding='0';this.parentElement.textContent='${tk.slice(0,2)}';"></div>`;
  }

  function shell(active, opts) {
    opts = opts || {};
    const sb = document.getElementById('sidebar'); if (sb) sb.innerHTML = sidebarHTML(active);
    const tb = document.getElementById('topbar'); if (tb) tb.innerHTML = topbarHTML(opts.placeholder);
    const btn = document.getElementById('themeToggle');
    if (btn) btn.addEventListener('click', () => {
      const light = document.documentElement.getAttribute('data-theme') === 'light';
      document.documentElement.setAttribute('data-theme', light ? 'dark' : 'light');
      document.getElementById('moonIcon').style.display = light ? 'block' : 'none';
      document.getElementById('sunIcon').style.display = light ? 'none' : 'block';
      themeCbs.forEach(cb => cb());
    });
  }

  window.QuantDeck = { shell, cssVar, onTheme, plotlyBase, logoBadge };
})();
