# api/main.py
"""QuantDeck backend: exposes the existing layers/ as JSON endpoints and serves
the vanilla frontend. Run from the project root:

    uvicorn api.main:app --reload --port 8000
"""
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from api.serialize import to_jsonable

app = FastAPI(title="QuantDeck API")


@app.middleware("http")
async def _no_cache(request, call_next):
    """Dev convenience: never let the browser cache the frontend, so edits show
    up on a normal refresh instead of a hard-reload."""
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp


_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Permissive defaults: the API returns the full ranked universe; the UI narrows it.
_WIDE_FILTERS = {
    "pe_max": 1e9, "pb_max": 1e9, "ev_ebitda_max": 1e9, "roe_min": -1e9,
    "debt_equity_max": 1e9, "revenue_growth_min": -1e9, "net_margin_min": -1e9,
    "current_ratio_min": -1e9, "rsi_min": 0, "rsi_max": 100,
}


@app.get("/api/screener")
def screener(universe: str = "Dow Jones 30", custom: str | None = None):
    """Composite-score screen for a universe (or a comma-separated custom list)."""
    from layers.screener import run_screener
    tickers = [t.strip().upper() for t in custom.split(",") if t.strip()] if custom else None
    key = "custom" if tickers else universe
    df = run_screener(key, dict(_WIDE_FILTERS), custom_tickers=tickers)
    return JSONResponse(to_jsonable({"universe": universe, "rows": df}))


def _g0(df, col):
    """First-row value of a DataFrame column, or None (NaN-safe)."""
    try:
        if df is not None and not df.empty and col in df.columns:
            v = float(df.iloc[0][col])
            return None if v != v else v
    except Exception:
        pass
    return None


def _build_memo(margins, mscore, macro):
    """Bull/bear bullets, ported from the Streamlit Deep Dive memo logic."""
    bull, bear = [], []
    gm = _g0(margins, "gross_margin")
    if gm is not None:
        if gm > 0.40:
            bull.append(f"High gross margin ({gm*100:.0f}%) - strong pricing power")
        elif gm < 0.20:
            bear.append(f"Low gross margin ({gm*100:.0f}%) - thin margins at risk")
    rg = _g0(margins, "revenue_yoy")
    if rg is not None:
        if rg > 0.10:
            bull.append(f"Strong revenue growth ({rg*100:.0f}% YoY)")
        elif rg < 0:
            bear.append(f"Revenue declining ({rg*100:.0f}% YoY)")
    if mscore is not None and mscore == mscore:
        if mscore < -2.22:
            bull.append("Beneish M-Score clean - no earnings-manipulation signal")
        else:
            bear.append(f"Beneish M-Score {mscore:.2f} - earnings-quality concern")
    shape = (macro or {}).get("yield_curve_shape")
    if shape == "inverted":
        bear.append("Inverted yield curve - historically precedes a slowdown")
    elif shape == "normal":
        bull.append("Normal yield curve - constructive macro backdrop")
    return {"bull": bull, "bear": bear}


@app.get("/api/deep-dive/{ticker}")
def deep_dive(ticker: str):
    """Single-name analysis: KPIs, fundamentals, margins series, memo.

    Uses only fast/reliable sources (FMP fundamentals + FRED macro) so the panel
    loads quickly; skips the heavier 5y price history, intraday and news that the
    Streamlit Deep Dive also pulls.
    """
    from data.prices import detect_asset_type
    from data.fundamentals import (fetch_income_statement, fetch_balance_sheet,
                                    fetch_cash_flow, fetch_key_metrics, fetch_analyst_info,
                                    fetch_news, fetch_sector_info)
    from layers.deep_dive import (compute_margins, compute_earnings_quality,
                                   compute_beneish_mscore)

    ticker = ticker.upper()
    asset_type = detect_asset_type(ticker)
    if asset_type != "equity":
        return JSONResponse({"ticker": ticker, "asset_type": asset_type,
                             "error": "Deep Dive is currently wired for equities"})

    try:
        income = fetch_income_statement(ticker, limit=5)
        balance = fetch_balance_sheet(ticker, limit=5)
        cashflow = fetch_cash_flow(ticker, limit=5)
        km = fetch_key_metrics(ticker, limit=5)
    except Exception as e:
        return JSONResponse({"ticker": ticker, "error": f"data source: {e}"}, status_code=502)

    if income is None or income.empty:
        return JSONResponse({"ticker": ticker, "error": "No fundamentals available for this ticker"})

    margins = eq = mscore = None
    try:
        if len(income) >= 2:
            margins = compute_margins(income)
    except Exception:
        pass
    try:
        eq = compute_earnings_quality(income, cashflow, balance)
    except Exception:
        pass
    try:
        if len(income) >= 2 and len(balance) >= 2:
            mscore = compute_beneish_mscore(income, balance, cashflow)
    except Exception:
        pass
    out = {"ticker": ticker, "asset_type": "equity"}
    out["kpis"] = {
        "marketCap": _g0(km, "marketCap"),
        "revenue": _g0(income, "revenue"),
        "net_margin": _g0(margins, "net_margin"),
        "peRatio": _g0(km, "peRatio"),
    }
    out["fundamentals"] = {k: _g0(km, k) for k in
                           ("peRatio", "evToEbitda", "pbRatio", "roe",
                            "debtToEquity", "netProfitMargin", "currentRatio", "revenueGrowth")}

    # Revenue + margins series, oldest -> newest (FMP returns newest-first).
    series = []
    for i in range(len(income) - 1, -1, -1):
        row = {
            "date": income.iloc[i]["date"] if "date" in income.columns else None,
            "revenue": income.iloc[i]["revenue"] if "revenue" in income.columns else None,
        }
        if margins is not None and i < len(margins):
            for mc in ("gross_margin", "operating_margin", "net_margin"):
                if mc in margins.columns:
                    row[mc] = margins.iloc[i][mc]
        series.append(row)
    out["revenue_series"] = series

    out["earnings_quality"] = {
        "ccr": _g0(eq, "ccr"),
        "accruals_ratio": _g0(eq, "accruals_ratio"),
        "beneish_mscore": float(mscore) if (mscore is not None and mscore == mscore) else None,
    }
    out["memo"] = _build_memo(margins, mscore, {})
    try:
        out["analyst"] = fetch_analyst_info(ticker)
    except Exception:
        out["analyst"] = {}
    try:
        out["news"] = fetch_news(ticker, max_items=6)
    except Exception:
        out["news"] = []
    try:
        out["sector_info"] = fetch_sector_info(ticker)
    except Exception:
        out["sector_info"] = {}
    return JSONResponse(to_jsonable(out))


# Recent 10Y government-bond yields (%) used as a risk-free proxy, because the
# live FRED fetch frequently stalls ~30s. The valuation layer's own fallback is
# ~4%; these keep WACC sensible per country without the stall.
_RF_PROXY = {"US": 4.2, "UK": 4.5, "India": 7.0, "Canada": 3.4,
             "Germany": 2.5, "Japan": 1.1, "Australia": 4.3, "France": 3.1}


@app.get("/api/valuation/{ticker}")
def valuation(ticker: str):
    """DCF + comps + DDM. Substitutes a recent risk-free proxy for the slow FRED
    fetch so the endpoint returns in a few seconds."""
    import layers.valuation as val
    from data.prices import detect_asset_type, country_from_ticker

    ticker = ticker.upper()
    if detect_asset_type(ticker) != "equity":
        return JSONResponse({"ticker": ticker, "error": "Valuation applies to equities only"})

    country = country_from_ticker(ticker)
    rf_pct = _RF_PROXY.get(country, 4.2)
    try:
        v = val.run_valuation(ticker, country=country, overrides={"rf": rf_pct / 100})
    except Exception as e:
        return JSONResponse({"ticker": ticker, "error": str(e)}, status_code=502)

    if not v.get("applicable"):
        return JSONResponse({"ticker": ticker, "error": v.get("reason", "not applicable")})

    w = v.get("wacc_inputs", {}) or {}
    dcf = v.get("dcf_base")
    cur = v.get("current_price")
    shares = v.get("shares_outstanding")

    out = {"ticker": ticker, "current_price": cur, "shares_outstanding": shares,
           "wacc": {k: w.get(k) for k in ("wacc", "ke", "rf", "beta", "kd", "tax_rate")}}
    out["wacc"]["terminal_growth"] = 0.025

    if dcf:
        wacc = w.get("wacc") or 0.09
        fcfs = dcf.get("fcf_series") or []
        disc = [fcfs[i] / ((1 + wacc) ** (i + 1)) for i in range(len(fcfs))]
        eqv = ((dcf.get("price_base") or 0) * (shares or 0)) or None
        out["dcf"] = {
            "price_base": dcf.get("price_base"), "price_bull": dcf.get("price_bull"),
            "price_bear": dcf.get("price_bear"), "fcf_series": fcfs, "disc_fcf": disc,
            "terminal_value": dcf.get("terminal_value"), "equity_value": eqv,
        }
    else:
        out["dcf"] = None

    out["comps"] = v.get("comps")
    out["comps_implied"] = v.get("comps_implied")
    out["ddm"] = v.get("ddm")
    return JSONResponse(to_jsonable(out))


@app.get("/api/backtest")
def backtest(strategy: str = "MA Crossover", ticker: str = "AAPL",
             start: str = "2021-01-01", end: str = "2024-12-31"):
    """Run a strategy backtest; return tearsheet + downsampled equity/benchmark
    curves (normalized to 100), recent trade signals, and monthly returns."""
    from layers.backtester import run_backtest
    try:
        r = run_backtest(strategy, ticker.upper(), start, end)
    except Exception as e:
        return JSONResponse({"error": str(e), "strategy": strategy,
                             "ticker": ticker.upper()}, status_code=502)

    ts = r.get("tearsheet", {}) or {}

    def norm_ds(series, n=110):
        """Normalize to 100 and downsample. Returns (values, date_strings)."""
        try:
            series = series.dropna()
            vals = series.tolist()
            try:
                dates = series.index.strftime("%Y-%m-%d").tolist()
            except Exception:
                dates = []
        except Exception:
            return [], []
        if not vals:
            return [], []
        base = vals[0] if vals[0] else 1.0
        step = max(1, len(vals) // n)
        idxs = list(range(0, len(vals), step))
        return (
            [round(vals[i] / base * 100.0, 2) for i in idxs],
            [dates[i] for i in idxs] if dates else [],
        )

    eq_vals, eq_dates = norm_ds(r.get("equity_curve"))
    bm_vals, bm_dates = norm_ds(r.get("benchmark_curve"))

    out = {
        "strategy": strategy, "ticker": ticker.upper(),
        "benchmark_ticker": r.get("benchmark_ticker"),
        "tearsheet": {k: ts.get(k) for k in
                      ("total_return", "sharpe", "sortino", "max_drawdown",
                       "win_rate", "cagr", "calmar", "profit_factor")},
        "equity": eq_vals,
        "equity_dates": eq_dates,
        "benchmark": bm_vals,
        "benchmark_dates": bm_dates,
    }

    import bisect
    trades = r.get("trades")
    tl = []
    trade_markers = []
    if trades is not None and not trades.empty:
        for _, row in trades.tail(6).iloc[::-1].iterrows():
            sig = row.get("signal")
            action = "Long" if sig == 1 else "Short" if sig == -1 else "Flat"
            tl.append({"date": str(row.get("date"))[:10], "action": action,
                       "price": row.get("price")})
        if eq_dates:
            for _, row in trades.iterrows():
                sig = row.get("signal")
                if sig is None or sig == 0:
                    continue
                d = str(row.get("date", ""))[:10]
                if d < eq_dates[0] or d > eq_dates[-1]:
                    continue
                idx = min(bisect.bisect_left(eq_dates, d), len(eq_vals) - 1)
                trade_markers.append({
                    "date": d,
                    "action": "buy" if sig == 1 else "sell",
                    "val": eq_vals[idx] if idx < len(eq_vals) else None,
                })
            if len(trade_markers) > 60:
                step2 = max(1, len(trade_markers) // 60)
                trade_markers = trade_markers[::step2]
    out["trades"] = tl
    out["trade_markers"] = trade_markers

    rets = r.get("returns")
    monthly = []
    try:
        if rets is not None and len(rets):
            m = (1 + rets.dropna()).resample("ME").prod() - 1
            for idx, val in m.tail(12).items():
                monthly.append({"month": idx.strftime("%b"), "ret": float(val)})
    except Exception:
        pass
    out["monthly"] = monthly

    return JSONResponse(to_jsonable(out))


@app.get("/api/simulation/{ticker}")
def simulation(ticker: str, model: str = "gbm", horizon: int = 252):
    """Monte Carlo: percentile cone, sample paths, terminal histogram, risk metrics."""
    import numpy as np
    from layers.simulation import run_simulation
    try:
        s = run_simulation(ticker.upper(), model=model.lower(), n_paths=2000,
                           horizon=int(horizon), seed=42)
    except Exception as e:
        return JSONResponse({"ticker": ticker.upper(), "error": str(e)}, status_code=502)

    bands = s["bands"]; paths = s["paths"]; start = float(s["start_price"]); rm = s["risk_metrics"]
    n = len(bands); step = max(1, n // 80)
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    band_out = {col: [round(float(bands[col].iloc[i]), 2) for i in idx]
                for col in ("p10", "p25", "p50", "p75", "p90") if col in bands.columns}
    sample = [[round(float(paths[i, j]), 2) for i in idx]
              for j in range(min(14, paths.shape[1]))]

    terminal = paths[-1, :]
    returns = terminal / start - 1.0
    hist, edges = np.histogram(terminal, bins=22)
    histogram = [{"x": round(float((edges[i] + edges[i + 1]) / 2), 2), "count": int(hist[i])}
                 for i in range(len(hist))]

    return JSONResponse(to_jsonable({
        "ticker": ticker.upper(), "model": s["model"], "horizon": s["horizon"],
        "start_price": start,
        "returns_pct": {"p5": float(np.percentile(returns, 5)),
                        "p50": float(np.percentile(returns, 50)),
                        "p95": float(np.percentile(returns, 95))},
        "prob_profit": rm.get("prob_profit"),
        "risk_metrics": {k: rm.get(k) for k in
                         ("var_95", "cvar_95", "expected_return", "median_return",
                          "p50_price", "mean_price")},
        "bands": band_out, "sample_paths": sample, "histogram": histogram,
    }))


@app.get("/api/decision/{ticker}")
def decision(ticker: str):
    """Cross-layer decision signal: combines fundamental health (Deep Dive),
    valuation (DCF range), and simulation odds into a structured 1-5 framework.
    A quantitative summary — NOT financial advice."""
    import layers.valuation as val
    from data.prices import detect_asset_type, country_from_ticker
    from data.fundamentals import (fetch_income_statement, fetch_balance_sheet,
                                    fetch_cash_flow, fetch_key_metrics)
    from layers.deep_dive import compute_margins, compute_beneish_mscore
    from layers.simulation import run_simulation
    from layers.decision import build_decision_signal

    ticker = ticker.upper()
    if detect_asset_type(ticker) != "equity":
        return JSONResponse({"ticker": ticker, "error": "Decision signal applies to equities only"})

    # 1) Fundamental health summary
    dd_summary: dict = {}
    try:
        income = fetch_income_statement(ticker, limit=5)
        balance = fetch_balance_sheet(ticker, limit=5)
        cashflow = fetch_cash_flow(ticker, limit=5)
        km = fetch_key_metrics(ticker, limit=1)
        if income is not None and not income.empty and len(income) >= 2:
            margins = compute_margins(income)
            dd_summary["margins_net"] = _g0(margins, "net_margin")
            if len(balance) >= 2:
                m = compute_beneish_mscore(income, balance, cashflow)
                dd_summary["beneish_mscore"] = float(m) if (m is not None and m == m) else None
        dd_summary["debt_equity"] = _g0(km, "debtToEquity")
    except Exception:
        pass

    # 2) Valuation summary (DCF bear/bull as the fair-value range)
    val_summary: dict = {}
    country = country_from_ticker(ticker)
    rf_pct = _RF_PROXY.get(country, 4.2)
    try:
        v = val.run_valuation(ticker, country=country, overrides={"rf": rf_pct / 100})
        if v.get("applicable"):
            cur = v.get("current_price")
            dcf = v.get("dcf_base") or {}
            val_summary = {"current": cur,
                           "fair_low": dcf.get("price_bear") or cur,
                           "fair_high": dcf.get("price_bull") or cur}
    except Exception:
        pass

    # 3) Simulation odds (lighter run — we only need prob_profit + P50/P10)
    sim_summary: dict = {}
    try:
        s = run_simulation(ticker, model="gbm", n_paths=1000, horizon=252, seed=42)
        bands = s["bands"]
        sim_summary = {
            "prob_profit": s["risk_metrics"].get("prob_profit"),
            "current": float(s["start_price"]),
            "p50": float(bands["p50"].iloc[-1]) if "p50" in bands.columns else None,
            "p10": float(bands["p10"].iloc[-1]) if "p10" in bands.columns else None,
        }
    except Exception:
        pass

    if not val_summary and not sim_summary:
        return JSONResponse({"ticker": ticker, "error": "insufficient data for a decision signal"})

    signal = build_decision_signal(dd_summary, val_summary, sim_summary)
    signal["ticker"] = ticker
    return JSONResponse(to_jsonable(signal))


@app.get("/api/strategies")
def strategies(ticker: str = "AAPL"):
    """Strategy library: each registered strategy backtested on one ticker
    (prices fetched once) for its Sharpe and total return."""
    from strategies import list_strategies, get_strategy
    from layers.backtester import run_engine, compute_tearsheet
    from data.prices import fetch_prices
    ticker = ticker.upper()
    try:
        prices_df = fetch_prices(ticker, period="5y").loc["2021-01-01":"2024-12-31"]
    except Exception as e:
        return JSONResponse({"ticker": ticker, "error": f"prices: {e}", "strategies": []})
    close = prices_df["Close"]
    items = []
    for meta in list_strategies():
        name = meta.get("name")
        item = {"name": name, "description": meta.get("description", "")}
        try:
            signals = get_strategy(name).generate_signals(prices_df)
            res = run_engine(close, signals)
            ts = compute_tearsheet(res["equity_curve"], res["returns"])
            item["sharpe"] = ts.get("sharpe")
            item["total_return"] = ts.get("total_return")
            item["cagr"] = ts.get("cagr")
        except Exception as e:
            item["error"] = str(e)
        items.append(item)
    return JSONResponse(to_jsonable({"ticker": ticker, "strategies": items}))


@app.get("/api/portfolio")
def portfolio(tickers: str = "NVDA,META,LLY,AVGO,AAPL,MSFT,JPM,UNH"):
    """Markowitz mean-variance optimization via random portfolios: max-Sharpe
    weights, efficient-frontier cloud, and the correlation matrix."""
    import numpy as np
    import yfinance as yf

    syms = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    try:
        data = yf.download(syms, period="2y", progress=False, auto_adjust=True)["Close"]
    except Exception as e:
        return JSONResponse({"error": f"prices: {e}"}, status_code=502)
    # A single resolved symbol comes back as a Series; normalize to a 1-col frame.
    if isinstance(data, pd.Series):
        data = data.to_frame(name=syms[0] if syms else "Close")
    data = data.dropna(axis=1, how="all").dropna()
    rets = data.pct_change().dropna()
    syms = list(rets.columns)
    n = len(syms)
    if n < 2:
        return JSONResponse({"error": "not enough price history for these tickers (need at least 2)"}, status_code=502)
    # Latest close per symbol — lets the UI mark stored buy prices to market.
    last_prices = {s: float(data[s].iloc[-1]) for s in syms}

    mu = rets.mean().values * 252.0
    cov = rets.cov().values * 252.0
    rng = np.random.default_rng(42)
    best = {"sharpe": -1e9, "weights": None, "ret": 0.0, "vol": 0.0}
    minvol = {"vol": 1e9, "ret": 0.0}
    cloud = []
    for _ in range(5000):
        w = rng.random(n); w /= w.sum()
        r = float(w @ mu); v = float(np.sqrt(w @ cov @ w)); s = r / v if v > 0 else 0.0
        cloud.append([round(v, 4), round(r, 4)])
        if s > best["sharpe"]:
            best = {"sharpe": s, "ret": r, "vol": v, "weights": w.tolist()}
        if v < minvol["vol"]:
            minvol = {"vol": v, "ret": r}

    ann_vol = rets.std().values * (252 ** 0.5)
    # per-position beta vs equal-weight portfolio proxy
    eq_w = np.ones(n) / n
    portfolio_ret = (rets.values @ eq_w)
    betas = []
    for i in range(n):
        cov_ip = float(np.cov(rets.values[:, i], portfolio_ret)[0, 1])
        var_p = float(np.var(portfolio_ret, ddof=1))
        betas.append(cov_ip / var_p if var_p > 0 else 1.0)

    def _risk_label(beta, vol, weight):
        score = 0
        if abs(beta) > 1.5: score += 2
        elif abs(beta) > 1.2: score += 1
        if vol > 0.40: score += 2
        elif vol > 0.25: score += 1
        if weight > 0.25: score += 1
        if score >= 3: return "high"
        if score >= 1: return "medium"
        return "low"

    weights = sorted(
        [{"symbol": syms[i], "weight": best["weights"][i], "ret": float(mu[i]),
          "ann_vol": float(ann_vol[i]), "beta": float(betas[i]),
          "current_price": last_prices.get(syms[i]),
          "risk": _risk_label(betas[i], ann_vol[i], best["weights"][i])} for i in range(n)],
        key=lambda x: -x["weight"])
    corr = rets.corr()
    correlation = {"symbols": syms,
                   "matrix": [[round(float(corr.iloc[i, j]), 2) for j in range(n)] for i in range(n)]}

    return JSONResponse(to_jsonable({
        "tickers": syms,
        "expected_return": best["ret"], "volatility": best["vol"], "sharpe": best["sharpe"],
        "positions": n, "weights": weights,
        "frontier": cloud[::25],
        "max_sharpe": [best["vol"], best["ret"]], "min_vol": [minvol["vol"], minvol["ret"]],
        "correlation": correlation,
    }))


_INTERVAL_PERIOD = {
    "1m": "5d", "2m": "5d", "5m": "1mo", "15m": "1mo", "30m": "1mo",
    "60m": "3mo", "1h": "6mo", "1d": "1y", "1wk": "5y", "1mo": "10y",
}


@app.get("/api/prices/{ticker}")
def prices(ticker: str, interval: str = "1d"):
    """OHLCV candles for any tradable symbol (equity/FX/commodity) via yfinance.
    interval: 1m/5m/15m/1h/1d/1wk/1mo (period auto-selected to fit)."""
    from data.prices import fetch_prices
    ticker = ticker.upper()
    period = _INTERVAL_PERIOD.get(interval, "1y")
    try:
        df = fetch_prices(ticker, period=period, interval=interval)
    except Exception as e:
        return JSONResponse({"ticker": ticker, "error": str(e)}, status_code=502)
    if df is None or df.empty:
        return JSONResponse({"ticker": ticker, "error": "No price data for this symbol"}, status_code=404)
    df = df.dropna(subset=["Open", "High", "Low", "Close"]).tail(400)
    have_vol = "Volume" in df.columns
    intraday = interval.endswith("m") or interval.endswith("h")
    candles = [{
        "t": str(idx)[:16] if intraday else str(idx)[:10],
        "o": round(float(r["Open"]), 4), "h": round(float(r["High"]), 4),
        "l": round(float(r["Low"]), 4), "c": round(float(r["Close"]), 4),
        "v": (float(r["Volume"]) if have_vol and r["Volume"] == r["Volume"] else None),
    } for idx, r in df.iterrows()]
    return JSONResponse(to_jsonable({"ticker": ticker, "interval": interval, "candles": candles}))


@app.get("/api/search")
def search(q: str):
    """Resolve a company name or ticker to symbols via Yahoo Finance search."""
    import requests
    q = (q or "").strip()
    if not q:
        return JSONResponse({"q": q, "results": []})
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 7, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0 (QuantDeck)"}, timeout=8,
        )
        r.raise_for_status()
        results = [{
            "symbol": x.get("symbol"),
            "name": x.get("shortname") or x.get("longname") or "",
            "exch": x.get("exchDisp") or "",
            "type": x.get("quoteType") or "",
        } for x in r.json().get("quotes", []) if x.get("symbol")]
        return JSONResponse({"q": q, "results": results})
    except Exception as e:
        return JSONResponse({"q": q, "results": [], "error": str(e)})


@app.get("/api/watchlist")
def watchlist_get():
    """Return saved watchlist tickers with their latest price + 1d change."""
    from utils.watchlist import load_watchlist
    import yfinance as yf
    tickers = load_watchlist()
    items = []
    for sym in tickers:
        try:
            info = yf.Ticker(sym).info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev  = info.get("previousClose") or info.get("regularMarketPreviousClose")
            chg   = round((price / prev - 1) * 100, 2) if (price and prev and prev > 0) else None
            items.append({"symbol": sym, "price": price, "change_pct": chg})
        except Exception:
            items.append({"symbol": sym, "price": None, "change_pct": None})
    return JSONResponse({"tickers": items})


@app.post("/api/watchlist/{ticker}")
def watchlist_add(ticker: str):
    """Add a ticker to the watchlist."""
    from utils.watchlist import add_ticker
    add_ticker(ticker.upper())
    return JSONResponse({"ok": True, "ticker": ticker.upper()})


@app.delete("/api/watchlist/{ticker}")
def watchlist_remove(ticker: str):
    """Remove a ticker from the watchlist."""
    from utils.watchlist import remove_ticker
    remove_ticker(ticker.upper())
    return JSONResponse({"ok": True, "ticker": ticker.upper()})


# Static frontend, mounted last so /api/* routes take precedence.
# html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")
