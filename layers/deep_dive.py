# layers/deep_dive.py — no Streamlit imports
import pandas as pd
import numpy as np
from data.prices import (
    fetch_prices, fetch_intraday, compute_returns, compute_rolling_beta,
    detect_asset_type, market_index_for_country, country_from_ticker,
)
from data.fundamentals import (
    fetch_income_statement, fetch_balance_sheet,
    fetch_cash_flow, fetch_key_metrics, fetch_peers,
)
from data.macro import fetch_yield_curve, fetch_macro_regime
from data.news import fetch_headlines, group_by_theme
from config import COUNTRY_RISK, EQUITY_UNIVERSES


# ── Margins ───────────────────────────────────────────────────────────────────

def compute_margins(income: pd.DataFrame) -> pd.DataFrame:
    """Add gross_margin, operating_margin, net_margin, revenue_yoy to income df copy."""
    df = income.copy()
    df["gross_margin"]     = df["grossProfit"]      / df["revenue"]
    df["operating_margin"] = df["operatingIncome"]  / df["revenue"]
    df["net_margin"]       = df["netIncome"]        / df["revenue"]
    # FMP returns most-recent-first; pct_change(-1) compares each row to the row below
    # it (the prior year), giving year-over-year revenue growth for the recent row.
    df["revenue_yoy"] = df["revenue"].pct_change(-1)
    return df


# ── Balance Sheet Ratios ──────────────────────────────────────────────────────

def compute_balance_sheet_ratios(
    balance: pd.DataFrame,
    income: pd.DataFrame,
) -> pd.DataFrame:
    """Return DataFrame with debt_equity, current_ratio, interest_coverage per year.

    Interest coverage joins income to balance on the shared `date` key so that a
    mismatch in row counts between the two statements (FMP can return different
    history depth per statement) degrades to NaN for unmatched years rather than
    raising a length-mismatch error.
    """
    df = balance.copy()
    df["debt_equity"] = df["totalDebt"] / df["totalEquity"]
    df["current_ratio"] = df["totalCurrentAssets"] / df["totalCurrentLiabilities"]

    income_by_date = income.set_index("date")
    op_income = df["date"].map(income_by_date["operatingIncome"])
    interest  = df["date"].map(income_by_date["interestExpense"])
    df["interest_coverage"] = op_income.values / interest.values

    return df[["date", "debt_equity", "current_ratio", "interest_coverage"]]


# ── Earnings Quality ──────────────────────────────────────────────────────────

def compute_earnings_quality(
    income: pd.DataFrame,
    cashflow: pd.DataFrame,
    balance: pd.DataFrame,
) -> pd.DataFrame:
    """Compute Cash Conversion Ratio and Accruals Ratio per year.

    CCR = operating cash flow / net income (>1.0 = earnings backed by cash).
    Accruals Ratio = (net income − operating cash flow) / average total assets.
    """
    df = pd.DataFrame()
    df["date"] = income["date"]
    df["ccr"] = cashflow["operatingCashFlow"].values / income["netIncome"].values
    avg_assets = (balance["totalAssets"].values + balance["totalAssets"].shift(-1).values) / 2
    df["accruals_ratio"] = (
        (income["netIncome"].values - cashflow["operatingCashFlow"].values) / avg_assets
    )
    return df.reset_index(drop=True)


# ── Beneish M-Score ───────────────────────────────────────────────────────────

def compute_beneish_mscore(
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cashflow: pd.DataFrame,
) -> float:
    """Beneish (1999) M-Score for the most recent year using two years of data.

    Score > -2.22 → potential earnings manipulator. The 8 indices and coefficients
    are from the published model and are not adjustable. Returns NaN if <2 years.
    """
    if len(income) < 2 or len(balance) < 2:
        return float("nan")

    rev_t  = income.loc[0, "revenue"]
    rev_p  = income.loc[1, "revenue"]
    cogs_t = income.loc[0, "costOfRevenue"]
    cogs_p = income.loc[1, "costOfRevenue"]
    sga_t  = income.loc[0, "sellingGeneralAndAdministrativeExpenses"]
    sga_p  = income.loc[1, "sellingGeneralAndAdministrativeExpenses"]
    ni_t   = income.loc[0, "netIncome"]
    dep_t  = income.loc[0, "depreciationAndAmortization"]
    dep_p  = income.loc[1, "depreciationAndAmortization"]

    ar_t   = balance.loc[0, "netReceivables"]
    ar_p   = balance.loc[1, "netReceivables"]
    ca_t   = balance.loc[0, "totalCurrentAssets"]
    ca_p   = balance.loc[1, "totalCurrentAssets"]
    ppe_t  = balance.loc[0, "propertyPlantEquipmentNet"]
    ppe_p  = balance.loc[1, "propertyPlantEquipmentNet"]
    ta_t   = balance.loc[0, "totalAssets"]
    ta_p   = balance.loc[1, "totalAssets"]
    cl_t   = balance.loc[0, "totalCurrentLiabilities"]
    cl_p   = balance.loc[1, "totalCurrentLiabilities"]
    ltd_t  = balance.loc[0, "longTermDebt"]
    ltd_p  = balance.loc[1, "longTermDebt"]

    cfo_t  = cashflow.loc[0, "operatingCashFlow"]

    dsri = (ar_t / rev_t) / (ar_p / rev_p)
    gm_t = (rev_t - cogs_t) / rev_t
    gm_p = (rev_p - cogs_p) / rev_p
    gmi  = (gm_p / gm_t) if gm_t != 0 else 1.0
    nca_ratio_t = 1 - (ca_t + ppe_t) / ta_t
    nca_ratio_p = 1 - (ca_p + ppe_p) / ta_p
    aqi = (nca_ratio_t / nca_ratio_p) if nca_ratio_p != 0 else 1.0
    sgi = rev_t / rev_p
    depi_denom = dep_t / (ppe_t + dep_t) if (ppe_t + dep_t) != 0 else 1.0
    depi_numer = dep_p / (ppe_p + dep_p) if (ppe_p + dep_p) != 0 else 1.0
    depi = depi_numer / depi_denom if depi_denom != 0 else 1.0
    sgai = (sga_t / rev_t) / (sga_p / rev_p)
    lev_t = (cl_t + ltd_t) / ta_t
    lev_p = (cl_p + ltd_p) / ta_p
    lvgi = lev_t / lev_p if lev_p != 0 else 1.0
    tata = (ni_t - cfo_t) / ta_t

    m_score = (
        -4.84
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )
    return float(m_score)


# ── Capital Allocation ────────────────────────────────────────────────────────

def compute_capital_allocation(
    income: pd.DataFrame,
    cashflow: pd.DataFrame,
    balance: pd.DataFrame,
) -> pd.DataFrame:
    """Return % FCF split into Capex, Dividends, Buybacks, Retained per year."""
    df = pd.DataFrame()
    df["date"] = income["date"]
    cfo = cashflow["operatingCashFlow"].abs()
    capex     = cashflow["capitalExpenditure"].abs()
    dividends = cashflow["dividendsPaid"].abs()
    buybacks  = cashflow["commonStockRepurchased"].abs()
    retained  = (cfo - capex - dividends - buybacks).clip(lower=0)

    total = capex + dividends + buybacks + retained
    total = total.replace(0, float("nan"))

    df["capex_pct"]     = capex     / total
    df["dividends_pct"] = dividends / total
    df["buybacks_pct"]  = buybacks  / total
    df["retained_pct"]  = retained  / total
    df["fcf_abs"]       = cashflow["freeCashFlow"].values
    return df.reset_index(drop=True)


# ── FX Market Drivers ─────────────────────────────────────────────────────────

def run_fx_market_drivers(ticker: str) -> dict:
    """Compute market driver metrics for an FX pair.

    Returns a dict consumed by Deep Dive Tab 2 when asset_type == "fx":
      prices — OHLCV DataFrame (2 years)
      momentum_12_1 — 12-1 month price return (float, NaN if history <252d)
      realized_vol_30d — 30-day realized vol annualized (float)
      rsi — current RSI(14)
      pair — display string e.g. "EURUSD"
      asset_type — "fx"
    """
    from data.prices import compute_rsi

    prices = fetch_prices(ticker, period="2y")
    close = prices["Close"]
    result: dict = {"prices": prices, "asset_type": "fx"}
    result["pair"] = ticker.upper().replace("=X", "")

    # 12-1 momentum: price 21 bars ago vs price 252 bars ago
    n = len(close)
    try:
        past = float(close.iloc[-22]) if n >= 22 else float("nan")
        ref  = float(close.iloc[max(0, n - 253)]) if n >= 30 else float("nan")
        result["momentum_12_1"] = (past / ref - 1.0) if (ref and ref == ref and past == past) else float("nan")
    except Exception:
        result["momentum_12_1"] = float("nan")

    # 30-day realized vol (annualized)
    try:
        rets = close.pct_change().dropna()
        result["realized_vol_30d"] = float(rets.iloc[-30:].std() * (252 ** 0.5)) if len(rets) >= 30 else float("nan")
    except Exception:
        result["realized_vol_30d"] = float("nan")

    # RSI(14)
    try:
        rsi_series = compute_rsi(close)
        valid = rsi_series.dropna()
        result["rsi"] = float(valid.iloc[-1]) if not valid.empty else float("nan")
    except Exception:
        result["rsi"] = float("nan")

    return result


# ── Commodity Market Drivers ──────────────────────────────────────────────────

def run_commodity_market_drivers(ticker: str) -> dict:
    """Compute market driver metrics for a commodity futures ticker.

    Returns a dict consumed by Deep Dive Tab 2 when asset_type == "commodity":
      prices — OHLCV DataFrame (5 years)
      momentum_12_1 — 12-1 month price return
      realized_vol_30d — 30-day realized vol annualized
      rsi — current RSI(14)
      price_vs_5y_mean_pct — % deviation of current price from 5Y rolling mean
        (positive = above average = historically expensive)
      asset_type — "commodity"
    """
    from data.prices import compute_rsi

    prices = fetch_prices(ticker, period="5y")
    close = prices["Close"]
    result: dict = {"prices": prices, "asset_type": "commodity"}

    # 12-1 momentum
    n = len(close)
    try:
        past = float(close.iloc[-22]) if n >= 22 else float("nan")
        ref  = float(close.iloc[max(0, n - 253)]) if n >= 30 else float("nan")
        result["momentum_12_1"] = (past / ref - 1.0) if (ref and ref == ref and past == past) else float("nan")
    except Exception:
        result["momentum_12_1"] = float("nan")

    # 30-day realized vol (annualized)
    try:
        rets = close.pct_change().dropna()
        result["realized_vol_30d"] = float(rets.iloc[-30:].std() * (252 ** 0.5)) if len(rets) >= 30 else float("nan")
    except Exception:
        result["realized_vol_30d"] = float("nan")

    # RSI(14)
    try:
        rsi_series = compute_rsi(close)
        valid = rsi_series.dropna()
        result["rsi"] = float(valid.iloc[-1]) if not valid.empty else float("nan")
    except Exception:
        result["rsi"] = float("nan")

    # Price vs 5Y rolling mean (measures whether commodity is historically rich/cheap)
    try:
        mean_5y = float(close.mean())
        last    = float(close.iloc[-1])
        result["price_vs_5y_mean_pct"] = (last / mean_5y - 1.0) if mean_5y != 0 else float("nan")
    except Exception:
        result["price_vs_5y_mean_pct"] = float("nan")

    return result


# ── Main entry point ──────────────────────────────────────────────────────────

def run_deep_dive(ticker: str, country: str | None = None,
                  asset_type: str | None = None) -> dict:
    """Assemble all data for the Deep Dive page, dispatching by asset type.

    For equity: runs the full fundamental analysis.
    For FX/commodity: runs only price + macro context + market drivers.

    asset_type is auto-detected from the ticker if not provided.
    country is auto-detected for equities if not provided.
    """
    if asset_type is None:
        asset_type = detect_asset_type(ticker)
    if country is None:
        country = country_from_ticker(ticker) if asset_type == "equity" else "US"

    result: dict = {"asset_type": asset_type, "country": country}

    # ── Price data (all asset classes) ─────────────────────────────────────
    result["prices"] = fetch_prices(ticker, period="5y")
    try:
        result["intraday"] = fetch_intraday(ticker)
    except Exception:
        result["intraday"] = None

    # ── Macro context (all asset classes) ──────────────────────────────────
    result["macro_regime"] = fetch_macro_regime(country)
    result["yield_curve"]  = fetch_yield_curve(country)

    # ── News themes (all asset classes) ────────────────────────────────────
    headlines = fetch_headlines(ticker=ticker)
    result["news_themes"] = group_by_theme(headlines)

    # ── Asset-class-specific analysis ──────────────────────────────────────
    if asset_type == "fx":
        result["market_drivers"] = run_fx_market_drivers(ticker)
        return result

    if asset_type == "commodity":
        result["market_drivers"] = run_commodity_market_drivers(ticker)
        return result

    # ── Equity: full fundamental analysis ──────────────────────────────────
    income      = fetch_income_statement(ticker, limit=5)
    balance     = fetch_balance_sheet(ticker, limit=5)
    cashflow    = fetch_cash_flow(ticker, limit=5)
    key_metrics = fetch_key_metrics(ticker, limit=5)
    result["income"]      = income
    result["balance"]     = balance
    result["cashflow"]    = cashflow
    result["key_metrics"] = key_metrics
    result["peers"]       = fetch_peers(ticker)

    result["margins"]            = pd.DataFrame()
    result["balance_ratios"]     = pd.DataFrame()
    result["earnings_quality"]   = pd.DataFrame()
    result["beneish_mscore"]     = float("nan")
    result["capital_allocation"] = pd.DataFrame()

    if not income.empty and len(income) >= 2:
        try:
            result["margins"] = compute_margins(income)
        except Exception:
            pass
        try:
            result["balance_ratios"] = compute_balance_sheet_ratios(balance, income)
        except Exception:
            pass
        try:
            result["earnings_quality"] = compute_earnings_quality(income, cashflow, balance)
        except Exception:
            pass
        try:
            result["beneish_mscore"] = compute_beneish_mscore(income, balance, cashflow)
        except Exception:
            pass
        try:
            result["capital_allocation"] = compute_capital_allocation(income, cashflow, balance)
        except Exception:
            pass

    # ── Rolling beta vs local market index ──────────────────────────────────
    try:
        local_index = market_index_for_country(country)
        market = fetch_prices(local_index, period="5y")
        stock_ret  = compute_returns(result["prices"])
        market_ret = compute_returns(market)
        idx = stock_ret.index.intersection(market_ret.index)
        beta_series = compute_rolling_beta(stock_ret.loc[idx], market_ret.loc[idx], window=252)
        valid = beta_series.dropna()
        result["beta"] = float(valid.iloc[-1]) if not valid.empty else float("nan")
    except Exception:
        result["beta"] = float("nan")

    return result
