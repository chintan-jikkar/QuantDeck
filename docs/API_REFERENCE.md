# QuantDeck — API Reference

Every endpoint is a `GET` returning JSON unless noted. The server runs at `http://localhost:8000`; the frontend is served from the same origin so calls are relative (`/api/...`). All DataFrame/NumPy values are passed through `to_jsonable()` — `NaN`/`Inf` become `null`.

Base: `api/main.py`. There is no auth and no rate-limiting (it's a single-user local tool).

---

## Health

### `GET /api/health`
```json
{ "status": "ok" }
```

---

## 01 · Screener

### `GET /api/screener`
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `universe` | string | `"Dow Jones 30"` | Named universe (used only when `custom` is absent). |
| `custom` | string | — | Comma-separated tickers; takes precedence. The frontend always sends this. |

```json
{
  "universe": "Dow Jones 30",
  "rows": [
    { "symbol": "NVDA", "composite_score": 82, "peRatio": 34.2,
      "evToEbitda": 28.1, "roe": 1.14, "...": "..." }
  ]
}
```
Filters are intentionally wide (`_WIDE_FILTERS`); the UI does any narrowing. Rows arrive ranked by composite score.

---

## 02 · Deep Dive

### `GET /api/deep-dive/{ticker}`
Equity only — non-equities return `{ "ticker", "asset_type", "error" }`.

```json
{
  "ticker": "AAPL",
  "kpis":         { "marketCap": 4.28e12, "revenue": 4.16e11, "net_margin": 0.269, "peRatio": 35.3 },
  "fundamentals": { "peRatio": 35.3, "evToEbitda": 26.9, "pbRatio": 40.2, "roe": 1.41,
                    "debtToEquity": 0.8, "netProfitMargin": 0.27, "currentRatio": 1.1, "revenueGrowth": 0.166 },
  "revenue_series": [ { "date": "2021-09-25", "revenue": 3.65e11, "gross_margin": 0.41, "net_margin": 0.25 } ],
  "earnings_quality": { "ccr": 1.08, "accruals_ratio": -0.03, "beneish_mscore": -2.71 },
  "memo": { "bull": ["High gross margin (47%) ..."], "bear": [] },
  "analyst": { "target": 312, "target_high": 400, "rec_key": "buy", "n_analysts": 43,
               "upside": 7.2, "buy_pct": 62, "hold_pct": 31, "sell_pct": 6 },
  "news":   [ { "title": "...", "link": "https://...", "publisher": "Reuters",
               "date": "Jun 10", "summary": "..." } ],
  "sector_info": { "sector": "Technology", "industry": "Consumer Electronics", "country": "United States",
                   "exchange": "NMS", "currency": "USD", "beta": 1.1, "dividend_yield": 0.0036,
                   "macro": { "erp": 0.0472, "crp": 0.0, "rf_pct": 4.2, "country_key": "US" } }
}
```

### `GET /api/prices/{ticker}`
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `interval` | string | `"1d"` | `1m/2m/5m/15m/30m/60m/1h/1d/1wk/1mo`; the lookback period is auto-selected to fit. |

```json
{ "ticker": "AAPL", "interval": "1d",
  "candles": [ { "t": "2025-06-10", "o": 198.1, "h": 201.4, "l": 197.8, "c": 200.9, "v": 5.1e7 } ] }
```
Works for any tradable symbol (equity / FX `=X` / commodity `=F`). Capped at the last 400 candles.

---

## 03 · Valuation

### `GET /api/valuation/{ticker}`
Equity only. Substitutes a per-country risk-free proxy for live FRED.

```json
{
  "ticker": "AAPL", "current_price": 291.2, "shares_outstanding": 1.49e10,
  "wacc": { "wacc": 0.084, "ke": 0.089, "rf": 0.042, "beta": 1.1, "kd": 0.03,
            "tax_rate": 0.21, "terminal_growth": 0.025 },
  "dcf":  { "price_base": 305.0, "price_bull": 360.0, "price_bear": 250.0,
            "fcf_series": [1.0e11, "..."], "disc_fcf": ["..."],
            "terminal_value": 5.0e12, "equity_value": 4.5e12 },
  "comps": null,
  "comps_implied": { "price_from_pe": 280.0, "price_from_ev_ebitda": 295.0 },
  "ddm": { "applicable": true, "price": 240.0 }
}
```
`comps` is currently `null` (no yfinance peer source).

---

## 04 · Backtester

### `GET /api/backtest`
| Param | Default |
|-------|---------|
| `strategy` | `"MA Crossover"` |
| `ticker` | `"AAPL"` |
| `start` | `"2021-01-01"` |
| `end` | `"2024-12-31"` |

```json
{
  "strategy": "MA Crossover", "ticker": "AAPL", "benchmark_ticker": "SPY",
  "tearsheet": { "total_return": 0.42, "sharpe": 1.1, "sortino": 1.6, "max_drawdown": -0.18,
                 "win_rate": 0.55, "cagr": 0.12, "calmar": 0.7, "profit_factor": 1.8 },
  "equity": [100, 101.2, "..."],        "equity_dates": ["2021-01-04", "..."],
  "benchmark": [100, 100.5, "..."],     "benchmark_dates": ["2021-01-04", "..."],
  "trades": [ { "date": "2024-11-01", "action": "Long", "price": 222.4 } ],
  "trade_markers": [ { "date": "2024-11-01", "action": "buy", "val": 138.2 } ],
  "monthly": [ { "month": "Jan", "ret": 0.03 } ]
}
```
Curves are normalised to 100 and downsampled (~110 pts); `trade_markers` are snapped onto the equity curve and capped at ~60.

---

## 05 · Monte Carlo

### `GET /api/simulation/{ticker}`
| Param | Default | Notes |
|-------|---------|-------|
| `model` | `"gbm"` | `gbm` / `garch` / `ou` |
| `horizon` | `252` | trading days |

```json
{
  "ticker": "AAPL", "model": "gbm", "horizon": 252, "start_price": 291.2,
  "returns_pct": { "p5": -0.22, "p50": 0.18, "p95": 0.64 },
  "prob_profit": 0.73,
  "risk_metrics": { "var_95": -0.21, "cvar_95": -0.28, "expected_return": 0.16,
                    "median_return": 0.15, "p50_price": 343.0, "mean_price": 350.0 },
  "bands": { "p10": ["..."], "p25": ["..."], "p50": ["..."], "p75": ["..."], "p90": ["..."] },
  "sample_paths": [ ["..."] ],
  "histogram": [ { "x": 320.5, "count": 142 } ]
}
```
2,000 paths; bands downsampled to ~80 points.

---

## 06 · Strategy Library

### `GET /api/strategies`
| Param | Default |
|-------|---------|
| `ticker` | `"AAPL"` |

```json
{
  "ticker": "AAPL",
  "strategies": [
    { "name": "12-1 Momentum", "description": "...", "sharpe": 1.4, "total_return": 0.62, "cagr": 0.2 },
    { "name": "Pairs Trading (Stat Arb)", "error": "needs a second leg" }
  ]
}
```
Each registered strategy is back-tested once over 2021–2024 on the ticker.

---

## 07 · Portfolio Optimizer

### `GET /api/portfolio`
| Param | Default |
|-------|---------|
| `tickers` | `"NVDA,META,LLY,AVGO,AAPL,MSFT,JPM,UNH"` |

```json
{
  "tickers": ["NVDA", "..."],
  "expected_return": 0.32, "volatility": 0.24, "sharpe": 1.37, "positions": 8,
  "weights": [ { "symbol": "JPM", "weight": 0.28, "ret": 0.29, "ann_vol": 0.22,
                 "beta": 1.05, "risk": "medium" } ],
  "frontier":   [ [0.18, 0.21], "..." ],
  "max_sharpe": [0.24, 0.32], "min_vol": [0.16, 0.19],
  "correlation": { "symbols": ["..."], "matrix": [[1.0, 0.34], [0.34, 1.0]] }
}
```
Requires ≥2 tickers with sufficient overlapping history.

---

## Utility

### `GET /api/search?q=`
Resolves a company name or partial ticker to symbols via Yahoo Finance search.
```json
{ "q": "tata steel", "results": [ { "symbol": "TATASTEEL.NS", "name": "Tata Steel Limited",
                                    "exch": "NSI", "type": "EQUITY" } ] }
```

### Watchlist (server-side, persisted to `~/.quantdeck_watchlist.json`)
| Method | Path | Effect |
|--------|------|--------|
| `GET` | `/api/watchlist` | List tickers with latest price + 1d change. |
| `POST` | `/api/watchlist/{ticker}` | Add a ticker. |
| `DELETE` | `/api/watchlist/{ticker}` | Remove a ticker. |

```json
// GET /api/watchlist
{ "tickers": [ { "symbol": "AAPL", "price": 200.9, "change_pct": 0.35 } ] }
```

---

## Error shape

Endpoints return a `200` with an `error` field for soft failures (e.g. non-equity sent to Deep Dive) and a `502`/`404` with `{ "error": "..." }` for upstream/data failures. The frontend checks `res.ok` and the presence of the primary data key before treating a response as an error.
