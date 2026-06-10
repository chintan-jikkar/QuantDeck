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
                                    fetch_cash_flow, fetch_key_metrics)
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
    orig = val.fetch_fred_series
    val.fetch_fred_series = lambda *a, **k: pd.Series([rf_pct])
    try:
        v = val.run_valuation(ticker, country=country)
    except Exception as e:
        return JSONResponse({"ticker": ticker, "error": str(e)}, status_code=502)
    finally:
        val.fetch_fred_series = orig

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
        try:
            vals = series.dropna().tolist()
        except Exception:
            return []
        if not vals:
            return []
        base = vals[0] if vals[0] else 1.0
        step = max(1, len(vals) // n)
        return [round(vals[i] / base * 100.0, 2) for i in range(0, len(vals), step)]

    out = {
        "strategy": strategy, "ticker": ticker.upper(),
        "benchmark_ticker": r.get("benchmark_ticker"),
        "tearsheet": {k: ts.get(k) for k in
                      ("total_return", "sharpe", "sortino", "max_drawdown",
                       "win_rate", "cagr", "calmar", "profit_factor")},
        "equity": norm_ds(r.get("equity_curve")),
        "benchmark": norm_ds(r.get("benchmark_curve")),
    }

    trades = r.get("trades")
    tl = []
    if trades is not None and not trades.empty:
        for _, row in trades.tail(6).iloc[::-1].iterrows():
            sig = row.get("signal")
            action = "Long" if sig == 1 else "Short" if sig == -1 else "Flat"
            tl.append({"date": str(row.get("date"))[:10], "action": action,
                       "price": row.get("price")})
    out["trades"] = tl

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


# Static frontend, mounted last so /api/* routes take precedence.
# html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")
