# data/macro.py
import pandas as pd
import pandas_datareader.data as web
from datetime import datetime, timedelta
from config import YIELD_CURVE_TICKERS, MACRO_REGIME_SERIES


def fetch_fred_series(series_id: str, years: int = 5) -> pd.Series:
    """Fetch a FRED series and return it as a pd.Series indexed by date."""
    end = datetime.today()
    start = end - timedelta(days=365 * years)
    df = web.DataReader(series_id, "fred", start, end)
    return df[series_id].dropna()


def fetch_yield_curve(country: str = "US") -> pd.Series:
    """Return the current yield curve as a Series indexed by maturity label.

    Uses config.YIELD_CURVE_TICKERS. Returns NaN for any maturity that fails.
    Phase 1 supports US only; other countries return NaN across all maturities.
    """
    tickers = YIELD_CURVE_TICKERS.get(country)
    if tickers is None:
        maturities = list(YIELD_CURVE_TICKERS["US"].keys())
        return pd.Series({m: float("nan") for m in maturities})
    rates = {}
    for maturity, series_id in tickers.items():
        try:
            s = fetch_fred_series(series_id, years=1)
            rates[maturity] = float(s.iloc[-1])
        except Exception:
            rates[maturity] = float("nan")
    return pd.Series(rates)


def fetch_macro_regime(country: str = "US") -> dict:
    """Return a snapshot of current macro regime indicators for the US.

    Keys:
      yield_curve_shape  — "normal" | "flat" | "inverted"
      credit_spread_level — float (OAS in %)
      policy_rate         — float (current central bank rate %)
      inflation_yoy       — float (CPI year-over-year %)

    Non-US countries return partial data (policy_rate sourced from COUNTRY_RISK
    rf_ticker; credit spread and inflation are US proxies in Phase 1).
    """
    series = MACRO_REGIME_SERIES
    result: dict = {}

    # Yield curve shape (3M vs 10Y spread)
    try:
        rate_3m = float(fetch_fred_series(series["us_3m_yield"], years=1).iloc[-1])
        rate_10y = float(fetch_fred_series(series["us_10y_yield"], years=1).iloc[-1])
        spread = rate_10y - rate_3m
        if spread > 0.25:
            result["yield_curve_shape"] = "normal"
        elif spread < -0.25:
            result["yield_curve_shape"] = "inverted"
        else:
            result["yield_curve_shape"] = "flat"
    except Exception:
        result["yield_curve_shape"] = "unknown"

    # Credit spreads (ICE BofA US Corporate OAS)
    try:
        result["credit_spread_level"] = float(
            fetch_fred_series(series["us_credit_spread"], years=1).iloc[-1]
        )
    except Exception:
        result["credit_spread_level"] = float("nan")

    # Policy rate
    try:
        result["policy_rate"] = float(
            fetch_fred_series(series["us_policy_rate"], years=1).iloc[-1]
        )
    except Exception:
        result["policy_rate"] = float("nan")

    # YoY CPI inflation
    try:
        cpi = fetch_fred_series(series["us_cpi"], years=2)
        yoy = (cpi.iloc[-1] / cpi.iloc[-13] - 1) * 100 if len(cpi) >= 13 else float("nan")
        result["inflation_yoy"] = yoy
    except Exception:
        result["inflation_yoy"] = float("nan")

    return result
