# api/main.py
"""QuantDeck backend: exposes the existing layers/ as JSON endpoints and serves
the vanilla frontend. Run from the project root:

    uvicorn api.main:app --reload --port 8000
"""
from pathlib import Path
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


# Static frontend, mounted last so /api/* routes take precedence.
# html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")
