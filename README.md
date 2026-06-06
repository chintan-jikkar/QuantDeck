# QuantDeck

A single, coherent quantitative analysis platform — walk in with a ticker, walk out with a full investment thesis.

QuantDeck is organized as a sequence of five analytical **layers**. A user enters at the Screener, narrows a universe to a shortlist, drills into one name, values it, simulates its future path, and backtests strategies against it. Each layer feeds the next.

> **Built by a finance analyst, not a software engineer** — the complexity lives in the financial logic, not the infrastructure.

---

## Features

### Layer 1 — Screener
Rank and filter a universe down to a shortlist.
- **Equity universes:** Dow Jones 30, S&P 500, NASDAQ 100, international exchanges (FTSE, DAX, Nikkei, Nifty 50, and more), custom paste-your-own, **watchlist**
- **FX screener:** G10 Majors, Crosses, Emerging Markets — ranked by momentum, RSI, realized vol
- **Commodity screener:** Precious Metals, Energy, Base Metals, Agricultural — same ranking
- **Smart Suggestions panel:** live headlines → themed chips (AI & Tech, Energy & Oil, Rates…) → pre-populate the Custom universe
- **Composite score:** weighted percentile rank, color-coded green/amber/red
- **Scatter plot:** P/E vs Revenue Growth, bubble = market cap, color = composite score

### Layer 2 — Deep Dive
A complete, interpreted picture of one name.
- **Live price chart:** candlestick with 50/200 SMA and Bollinger Bands overlays; **1D mode auto-refreshes every 60s** with "🔴 Live" badge
- **Asset-class routing:** equity → full fundamental analysis; FX/commodity → Market Drivers panel
- **Macro Context tab:** yield curve shape, credit spreads, policy rate, inflation — live FRED data
- **Micro Fundamentals tab (equity):** revenue & margins combo chart, capital allocation stacked bar, balance sheet health, earnings quality (Beneish M-Score)
- **Market Drivers tab (FX/commodity):** momentum (12-1), realized vol, RSI, price vs 5Y mean
- **Investment Memo:** auto-populated bull/bear case from quantitative signals

### Layer 3 — Valuation Engine
Equity only; FX/commodity shows a clean not-applicable state.
- **DCF:** Damodaran WACC (Rf + β×ERP + CRP, country-correct for 12 markets), FCF projection, 5×5 sensitivity heatmap
- **Comparable Company Analysis:** FMP peer set, bubble chart, multiple range bars, implied price
- **Dividend Discount Model:** two-stage DDM, gated on ≥3 years of dividends
- **Football Field Chart:** DCF bear/base/bull + comps + DDM as horizontal ranges vs current price

### Layer 4 — Monte Carlo Simulation
Applies to all asset classes.
- **Three models:** GBM (bootstrap), GARCH(1,1) with Student-t innovations, Ornstein-Uhlenbeck (mean reversion for commodities)
- **Simulation Cone:** P10/P25/P50/P75/P90 bands + 50 individual paths
- **Risk Metrics:** VaR 95%, CVaR 95%, probability of profit, expected return
- **Cross-Layer Decision Signal:** fundamental health (Deep Dive) + valuation (Layer 3) + simulation odds → combined signal with reward/risk ratio

### Layer 5 — Backtester
Full strategy tearsheet against historical data.
- **Strategy library (3 tiers):** MA Crossover, RSI Mean Reversion, 12-1 Momentum
- **Benchmark auto-selection:** SPY for US equity, EWU/EWG/EWJ/etc. for international, UUP for FX, DJP for commodities — buy-and-hold curve overlaid on equity curve
- **Tearsheet:** CAGR, Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor, Calmar
- **Drawdown chart** synced to equity curve

---

## Asset Universe

| Class | Examples | yfinance format |
|-------|----------|-----------------|
| US Equities | S&P 500, NASDAQ 100, Dow 30 | `AAPL`, `MSFT` |
| International Equities | FTSE 100, DAX 40, Nikkei 225, Nifty 50, and 8 more | `BP.L`, `SIE.DE`, `7203.T`, `RELIANCE.NS` |
| FX Pairs | G10 Majors, Crosses, EM | `EURUSD=X`, `USDINR=X` |
| Commodities | Precious Metals, Energy, Base Metals, Agricultural | `GC=F`, `CL=F`, `HG=F` |

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/QuantDeck.git
cd QuantDeck
pip install -r requirements.txt
```

### 2. API keys

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Key | Where to get it | Required? |
|-----|-----------------|-----------|
| `FMP_API_KEY` | [financialmodelingprep.com](https://financialmodelingprep.com/) — free tier | Yes (fundamentals, valuation) |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org/) — free tier | Optional (Smart Suggestions) |

The app degrades gracefully without `NEWSAPI_KEY` — the Smart Suggestions panel shows a "no headlines" message; everything else works.

### 3. Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Architecture

```
QuantDeck/
├── app.py                  # Entry point — landing page
├── config.py               # Universes, COUNTRY_RISK, benchmark map
├── pages/                  # DISPLAY ONLY — Streamlit + Plotly, no business logic
│   ├── 1_Screener.py
│   ├── 2_Deep_Dive.py
│   ├── 3_Valuation.py
│   ├── 4_Simulation.py
│   └── 5_Backtester.py
├── layers/                 # Pure-Python quant logic — no Streamlit imports
│   ├── screener.py
│   ├── deep_dive.py
│   ├── valuation.py
│   ├── simulation.py
│   └── backtester.py
├── strategies/             # Pluggable strategy system
│   ├── base.py             # Abstract Strategy interface
│   └── signal/             # MA Crossover, RSI, Momentum
├── data/                   # Data fetching (yfinance, FMP, FRED, NewsAPI)
│   ├── prices.py           # All price data + asset-type detection
│   ├── fundamentals.py     # FMP financial statements
│   ├── macro.py            # FRED — yields, policy rates, credit spreads
│   └── news.py             # Headlines, theme extraction, ticker suggestions
├── utils/
│   ├── charts.py           # Reusable Plotly builders
│   ├── formatting.py       # Number/currency/percent formatters
│   └── watchlist.py        # JSON-backed watchlist persistence
└── tests/                  # pytest — math that must be correct
```

**Core design rule:** `layers/` and `strategies/` contain zero Streamlit imports. They are plain Python that accept parameters and return DataFrames and numbers. `pages/` is display-only — it calls the layers and renders results with Plotly. This makes every layer independently readable and testable.

### Country-correct valuation (Damodaran)

For non-US equities, valuation uses the **local** risk-free rate (FRED), **local** market index for beta, and country risk premium:

```
Ke = Rf_local + β_local × ERP + CRP
```

Covered: US, UK, Germany, France, Japan, India, Australia, Canada, Hong Kong.

---

## Tests

```bash
pytest
```

235+ tests covering: WACC/DCF/DDM math, backtester P&L accounting, Monte Carlo path generation, screener filters, asset-type detection, country helpers, watchlist persistence.

---

## Contributing

The architecture is designed for easy extension:

**Adding a strategy:** subclass `strategies/base.py` → implement `generate_signals(prices_df, **params) -> pd.Series` → register in `strategies/__init__.py`. The backtester picks it up automatically.

**Adding a universe:** add an entry to `config.EQUITY_UNIVERSES` (or `FX_PAIRS` / `COMMODITIES`) with `suffix`, `benchmark`, `market_index`, `country`. The screener and backtester inherit it.

**Adding a country:** add an entry to `config.COUNTRY_RISK` with `rf_ticker` (FRED series), `erp`, `crp`. Valuation inherits it via `_derive_wacc_inputs`.

---

## Disclaimers

QuantDeck is a quantitative analysis and educational tool. Every signal, valuation, and backtest is a model output, **not financial advice**. Models do not account for gap risk from earnings events, regulatory changes, or macro regime shifts. Backtested performance is not indicative of future results. These disclaimers appear in-app at every decision surface.
