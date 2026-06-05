# layers/deep_dive.py — no Streamlit imports
import pandas as pd
import numpy as np


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
    """Return DataFrame with debt_equity, current_ratio, interest_coverage per year."""
    df = balance.copy()
    df["debt_equity"] = df["totalDebt"] / df["totalEquity"]
    df["current_ratio"] = df["totalCurrentAssets"] / df["totalCurrentLiabilities"]
    df["interest_coverage"] = (
        income["operatingIncome"].values / income["interestExpense"].values
    )
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


# ── Main entry point (data assembly in Task 3) ────────────────────────────────

def run_deep_dive(ticker: str) -> dict:
    """Assemble and compute all deep-dive data for one ticker.

    Implemented fully in Task 3 (data assembly step).
    """
    raise NotImplementedError("Data assembly implemented in Task 3")
