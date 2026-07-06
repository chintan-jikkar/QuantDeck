# QuantDeck — Architecture & Internals

This is the engineering companion to the [README](../README.md). It explains how a click becomes a chart, what each module does under the hood, the financial math, the front-end state model, and the honest list of blindspots.

---

## 1. The big picture

QuantDeck is a **two-tier app with no database**:

1. **Frontend** (`frontend/index.html` + `frontend/js/app.js`) — one HTML file holding all markup and CSS, one JS file holding all behaviour. Charts are drawn with Plotly.js (loaded from a CDN). Per-user state (watchlist, daily pick, portfolio basket, buy-tracking) lives in the browser's `localStorage`.
2. **Backend** (`api/main.py`) — a FastAPI app that exposes one JSON endpoint per module and serves the frontend as static files. It imports the pure-Python **layers** to do the actual quant work, and serialises their DataFrames/arrays to JSON.

There is no bundler, no framework, and no build step. You edit a file and refresh.

### Request lifecycle

```
user clicks "Deep Dive" on AAPL
        │
        ▼
app.js  switchModule(1) → onModule(1) → loadDeepDive()
        │   fetch("/api/deep-dive/AAPL")
        ▼
main.py deep_dive("AAPL")
        │   data/fundamentals.py  → yfinance (income, balance, cashflow, info, news)
        │   layers/deep_dive.py   → compute_margins, Beneish M-Score, earnings quality
        │   api/serialize.py      → to_jsonable(...)   (NaN→null, DataFrame→records)
        ▼
JSON  { ticker, kpis, fundamentals, revenue_series, memo, analyst, news, sector_info }
        │
        ▼
app.js renders KPI cards, fundamentals table, dual-axis Plotly chart, memo,
        sector/macro table, news with summaries, financial-doc links
        │   (loadCandles() runs in parallel → /api/prices/AAPL → Plotly candlestick)
```

### Caching & freshness

- **Backend:** `data/fundamentals.py` caches each `(ticker, statement)` for one hour in-process (`_CACHE`, `_CACHE_TTL = 3600`). Restarting the server clears it.
- **Frontend:** an HTTP middleware sets `Cache-Control: no-store` on every response so edits to `index.html`/`app.js` show up on an ordinary refresh.
- **Live polling:** the sidebar watchlist re-fetches prices every 30 s (`setInterval(loadSidebarWatchlist, 30000)`).

---

## 2. Front-end model

### Shared ticker flow
`DD_TICKER`, `VAL_TICKER`, `MC_TICKER`, and `BT.ticker` are module-level variables. `selectTicker(t)` sets all of them, invalidates the cached module loads for the ticker-bound modules (`TICKER_MODULES = {1,2,3,4}`), and jumps to Deep Dive. The Screener rows and the top-bar search both call it.

### Lazy module loading
`onModule(idx)` calls the module's loader only when it's first shown for a given ticker. A `loaded[idx]` map keyed by either the ticker (for ticker-bound modules) or the string `"once"` (for Screener/Strategies/Portfolio) prevents redundant fetches; the ↻ refresh button and the Optimize/Run buttons clear the relevant key to force a reload.

### Persistent state (`localStorage`)
| Key | Written by | Purpose |
|-----|-----------|---------|
| `qd-daily-pick` | `getDailyTopPick()` | Daily Screener top pick + no-repeat history |
| `qd-po-basket` | `_savePoBasket()` | Portfolio basket — survives reloads & sessions |
| `qd-po-tracking` | `savePoTracking()` | Per-ticker buy date / price / qty |

The watchlist is the one piece of cross-device state that lives **server-side** (`utils/watchlist.py` → `~/.quantdeck_watchlist.json`), exposed via `GET/POST/DELETE /api/watchlist`.

### Charting gotcha (documented because it bit us)
`Plotly.react()` silently no-ops on an element whose `innerHTML` was manually set to a loading message — Plotly loses its internal handle on the node. The fix used in `renderCandles()` is **`Plotly.purge(el); el.innerHTML = ""; Plotly.newPlot(...)`**. Reach for `purge + newPlot` (not `react`) any time a chart container may have been populated with placeholder HTML first.

---

## 3. Module internals

### 01 Screener — `layers/screener.py`
Fetches key metrics + technicals for the basket, applies (wide, UI-narrowed) fundamental/technical filters, and computes a **composite percentile score** across factors. The API default filters are deliberately permissive (`_WIDE_FILTERS`) so the endpoint returns the full ranked universe and the UI does any narrowing. The daily Top Pick rotation is purely front-end.

### 02 Deep Dive — `layers/deep_dive.py`
- **Margins:** gross/operating/net per period.
- **Earnings quality:** cash-conversion ratio, accruals ratio.
- **Beneish M-Score:** eight-variable earnings-manipulation detector; `< -2.22` reads as "clean".
- **Memo:** `_build_memo()` in `main.py` turns margin level, revenue trend, M-Score, and yield-curve shape into bull/bear bullets.
- **Sector/news/analyst:** `fetch_sector_info`, `fetch_news` (with article summaries), `fetch_analyst_info` from yfinance `info` + `recommendations_summary`.

> **yfinance dividend gotcha:** `info["dividendYield"]` returns the **dollar** dividend per share, not the yield fraction. QuantDeck uses `trailingAnnualDividendYield` (e.g. `0.0036` → `0.4%`).

### 03 Valuation — `layers/valuation.py`
```
Ke   = Rf + β·ERP + CRP            (Damodaran cost of equity, country-correct)
WACC = (E/V)·Ke + (D/V)·Kd·(1−tax)
DCF  = Σ FCFₜ/(1+WACC)ᵗ + TV/(1+WACC)ⁿ ,  TV = FCF·(1+g)/(WACC−g)
```
`COUNTRY_RISK` (config.py) supplies `erp`/`crp`/`rf_ticker` for 12 markets. The API swaps the slow live FRED call for `_RF_PROXY` (a recent per-country 10Y yield) so the endpoint returns in seconds — see Blindspots for the thread-safety cost of that swap. DDM is gated on a positive, sane dividend. Comps use a curated peer map with a sector-bucket fallback (see Blindspots for coverage limits).

### 04 Backtester — `layers/backtester.py`
`run_engine(prices, signals)` applies position signals with commission (10 bps) and slippage (0.1%), producing an equity curve, returns, and a trade ledger. `compute_tearsheet` derives CAGR, Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor, Calmar. The API normalises curves to 100, downsamples to ~110 points, snaps trade markers onto the curve with `bisect`, and resamples monthly returns.

### 05 Monte Carlo — `layers/simulation.py`
Three calibrated models on log returns: **GBM** (bootstrap), **GARCH(1,1)** with Student-t innovations (`arch`), **Ornstein-Uhlenbeck** (mean-reverting, for commodities). Returns 2,000 paths → percentile bands (P10/25/50/75/90), sample paths, terminal histogram, and risk metrics (VaR/CVaR 95%, prob-of-profit, expected/median terminal). The front-end animates the cone by redrawing progressively larger slices.

### 06 Strategy Library — `strategies/`
Pluggable `Strategy` subclasses across `signal/` (MA crossover, RSI mean-reversion, 12-1 momentum), `factor/` (value, quality), and `arbitrage/` (pairs trading). `GET /api/strategies` fetches prices once and back-tests each on the active ticker for Sharpe/return; cards carry a BUY/HOLD/AVOID verdict and deep-link into the Backtester.

### 07 Portfolio Optimizer — `api/main.py::portfolio`
Markowitz max-Sharpe (tangency) and min-variance portfolios are solved directly via `scipy.optimize.minimize` (SLSQP, long-only, fully invested). A separate 5,000-point Dirichlet-sampled cloud (uniform over the weight simplex) renders the frontier scatter; it plays no part in picking the optimum. Also returns per-position annualised return, β (vs an equal-weight proxy), annualised σ, a heuristic risk label, and the correlation matrix.

---

## 4. Layer boundary (the one rule)

`layers/` and `strategies/` contain **no** FastAPI, Streamlit, or Plotly imports. They accept parameters and return pandas/NumPy objects. This is what lets `tests/` (235 functions) verify the math directly, and what let the project swap its entire UI from Streamlit to FastAPI+JS without touching the quant code. `api/main.py` is the only place that knows about HTTP; `frontend/` is the only place that knows about pixels.

---

## 5. Blindspots & roadmap

An honest register, current as of this revision. None block daily use; all are scoped, not accidental.

| Area | Blindspot | Severity | Note |
|------|-----------|----------|------|
| Valuation | `/api/valuation` and `/api/decision` monkeypatch the module-level `val.fetch_fred_series` to inject the risk-free proxy, then restore it in `finally` | Medium | Not thread-safe: concurrent requests racing on the same global can read the wrong rf. Should pass `rf` as a parameter into `run_valuation` instead. |
| Valuation | DCF excludes changes in net working capital | Low | `FCF = NOPAT + D&A − Capex`; overstates FCF slightly for working-capital-heavy sectors. |
| Valuation | Risk-free is a hardcoded per-country proxy, not live FRED | Low | Deliberate, for latency — but the constants are dated at write-time and duplicated in `api/main.py` and `data/fundamentals.py`. |
| Valuation | Comps peers come from a curated map + sector fallback, not a live peer endpoint | Low | yfinance has no reliable peer source; coverage is best for large/mega-caps. |
| Tooling | No CI runs the test suite | Low | See `.github/workflows/tests.yml`. |
| Tooling | `requirements.txt` still pins the retired Streamlit stack | Low | `app.py` / `pages/` are kept for reference; trim both once no longer needed. |
| Edge case | `/api/portfolio` assumes ≥2 valid tickers; a single-symbol `yf.download` returns a different shape | Low | Guarded by the UI (basket always ≥2). |

### Naming note
The UI title and sidebar logo previously read **"QuantDesk"** (the design-mockup name) while the project is **QuantDeck**; this was corrected to QuantDeck. The original mockups under `docs/mockups/` intentionally retain their own naming.

### Deliberate aesthetic
The lowercase sub-labels ("base case", "bull scenario", "most recent") and uppercased card titles are an intentional terminal aesthetic enforced by CSS `text-transform`, **not** unfinished copy — they were left as-is.

---

## 6. Running & verifying

```bash
uvicorn api.main:app --port 8000          # serve
pytest -q --ignore=tests/test_news.py     # 235 tests
```

The frontend is best viewed at a 16:9 / laptop-or-wider aspect ratio — the seven modules are laid out as a full-screen `100vw × 100vh` terminal, so narrow windows leave the two-column cards cramped.
