# layers/valuation.py — no Streamlit imports
import pandas as pd
import numpy as np
from data.fundamentals import (
    fetch_income_statement, fetch_balance_sheet, fetch_cash_flow,
    fetch_key_metrics, fetch_peers,
)
from data.prices import fetch_prices, compute_returns, compute_rolling_beta, detect_asset_type, market_index_for_country
from data.macro import fetch_fred_series
from config import COUNTRY_RISK


# ── Pure financial formulas (tested) ──────────────────────────────────────────

def compute_ke(rf: float, beta: float, erp: float, crp: float) -> float:
    """Cost of equity: Ke = Rf + β×ERP + CRP  (Damodaran)."""
    return rf + beta * erp + crp


def compute_wacc(ke: float, kd: float, tax_rate: float, equity: float, debt: float) -> float:
    """WACC = Ke×E/(D+E) + Kd×(1−t)×D/(D+E)."""
    total = equity + debt
    if total <= 0:
        raise ValueError("Equity + Debt must be positive")
    return ke * (equity / total) + kd * (1 - tax_rate) * (debt / total)


def compute_terminal_value(fcf_final: float, wacc: float, growth_rate: float) -> float:
    """Gordon Growth terminal value: FCF_final × (1+g) / (WACC − g)."""
    if wacc <= growth_rate:
        raise ValueError(
            f"WACC ({wacc:.2%}) must exceed terminal growth rate ({growth_rate:.2%})"
        )
    return fcf_final * (1 + growth_rate) / (wacc - growth_rate)


def project_fcf(
    base_revenue: float,
    growth_rates: list[float],
    ebit_margin: float,
    capex_pct: float,
    da_pct: float,
    tax_rate: float,
    years: int | None = None,
) -> list[float]:
    """Project unlevered FCF = NOPAT + D&A − Capex for each year.

    EBIT = Revenue × ebit_margin; NOPAT = EBIT × (1 − tax_rate);
    D&A = Revenue × da_pct; Capex = Revenue × capex_pct.
    """
    n = years or len(growth_rates)
    rates = growth_rates[:n]
    fcfs = []
    revenue = base_revenue
    for g in rates:
        revenue *= (1 + g)
        ebit  = revenue * ebit_margin
        nopat = ebit * (1 - tax_rate)
        da    = revenue * da_pct
        capex = revenue * capex_pct
        fcfs.append(nopat + da - capex)
    return fcfs


def compute_dcf_price(
    fcf_series: list[float],
    terminal_value: float,
    wacc: float,
    net_debt: float,
    shares_outstanding: float,
) -> float:
    """Implied equity price per share from a DCF.

    EV = Σ FCF_t/(1+WACC)^t + TV/(1+WACC)^n; equity = EV − net_debt;
    price = equity / shares_outstanding.
    """
    n = len(fcf_series)
    pv_fcfs = sum(fcf / (1 + wacc) ** (i + 1) for i, fcf in enumerate(fcf_series))
    pv_tv = terminal_value / (1 + wacc) ** n
    equity_value = pv_fcfs + pv_tv - net_debt
    return equity_value / shares_outstanding


def compute_dcf_sensitivity(
    fcf_series: list[float],
    base_fcf_final: float,
    wacc_values: list[float],
    growth_values: list[float],
    net_debt: float,
    shares_outstanding: float,
) -> pd.DataFrame:
    """5×5 (WACC rows × terminal-growth cols) sensitivity grid of implied price."""
    rows = []
    for wacc in wacc_values:
        row = []
        for g in growth_values:
            try:
                tv = compute_terminal_value(base_fcf_final, wacc, g)
                price = compute_dcf_price(fcf_series, tv, wacc, net_debt, shares_outstanding)
            except ValueError:
                price = float("nan")
            row.append(price)
        rows.append(row)
    index = [f"{w:.1%}" for w in wacc_values]
    cols  = [f"{g:.1%}" for g in growth_values]
    return pd.DataFrame(rows, index=index, columns=cols)


def compute_ddm_price(
    current_dividend: float,
    growth_rates: list[float],
    ke: float,
    stable_growth: float,
) -> float:
    """Two-stage Dividend Discount Model.

    Stage 1: explicit dividend growth for len(growth_rates) years.
    Stage 2: Gordon Growth perpetuity at stable_growth, discounted back.
    """
    if ke <= stable_growth:
        raise ValueError(
            f"cost of equity ({ke:.2%}) must exceed stable growth rate ({stable_growth:.2%})"
        )
    div = current_dividend
    pv_stage1 = 0.0
    for i, g in enumerate(growth_rates, start=1):
        div *= (1 + g)
        pv_stage1 += div / (1 + ke) ** i
    div_next = div * (1 + stable_growth)
    tv = div_next / (ke - stable_growth)
    pv_tv = tv / (1 + ke) ** len(growth_rates)
    return pv_stage1 + pv_tv


# ── Derived WACC inputs from live data ────────────────────────────────────────

def _derive_wacc_inputs(
    ticker: str,
    income: pd.DataFrame,
    balance: pd.DataFrame,
    country: str,
) -> dict:
    """Derive WACC inputs from FMP statements + FRED/yfinance risk-free + config risk premia.

    For US, uses DGS10 (FRED) for Rf and ^GSPC for beta — preserving test compatibility.
    For non-US, uses the country's rf_ticker from COUNTRY_RISK (FRED series) and
    the country's local market index for beta calculation.
    """
    cr = COUNTRY_RISK.get(country, COUNTRY_RISK["US"])
    erp = cr["erp"]
    crp = cr["crp"]
    rf_ticker = cr["rf_ticker"]

    # Risk-free rate: US uses DGS10 (preserves existing test mocking);
    # non-US uses the country's FRED series from COUNTRY_RISK.
    try:
        if country == "US":
            rf_series = fetch_fred_series("DGS10", years=1)
        else:
            rf_series = fetch_fred_series(rf_ticker, years=1)
        rf = float(rf_series.iloc[-1]) / 100
    except Exception:
        rf = 0.04

    # Beta vs local market index (country-correct for non-US equities)
    local_index = market_index_for_country(country)
    try:
        prices = fetch_prices(ticker, period="5y")
        market = fetch_prices(local_index, period="5y")
        sr = compute_returns(prices)
        mr = compute_returns(market)
        idx = sr.index.intersection(mr.index)
        beta_s = compute_rolling_beta(sr.loc[idx], mr.loc[idx], window=252)
        beta = float(beta_s.dropna().iloc[-1])
    except Exception:
        beta = 1.0

    ke = compute_ke(rf=rf, beta=beta, erp=erp, crp=crp)

    try:
        kd = abs(float(income.loc[0, "interestExpense"])) / float(balance.loc[0, "totalDebt"])
        kd = min(kd, 0.20)
    except Exception:
        kd = 0.04

    try:
        tax_rate = float(income.loc[0, "incomeTaxExpense"]) / float(income.loc[0, "incomeBeforeTax"])
        tax_rate = max(0, min(tax_rate, 0.50))
    except Exception:
        tax_rate = 0.21

    try:
        equity = float(balance.loc[0, "totalEquity"])
        debt   = float(balance.loc[0, "totalDebt"])
        wacc   = compute_wacc(ke, kd, tax_rate, equity, debt)
    except Exception:
        equity = debt = float("nan")
        wacc = ke

    return {
        "rf": rf, "beta": beta, "erp": erp, "crp": crp,
        "ke": ke, "kd": kd, "tax_rate": tax_rate,
        "equity": equity, "debt": debt, "wacc": wacc,
    }


def run_valuation(ticker: str, country: str = "US", overrides: dict | None = None) -> dict:
    """Main valuation entry point for equity tickers.

    Returns a dict with: wacc_inputs, dcf_base, dcf_sensitivity, comps,
    comps_implied, ddm, current_price, shares_outstanding.
    Every block is defensive — partial data degrades to None/empty, never crashes.
    """
    asset_type = detect_asset_type(ticker)
    if asset_type != "equity":
        return {
            "applicable": False,
            "asset_type": asset_type,
            "reason": (
                f"Valuation models (DCF, DDM, comparable comps) apply to equities only. "
                f"{ticker!r} is a {asset_type} instrument. "
                f"FX and commodity prices are driven by macro flows, not discounted cash flows."
            ),
        }

    ov = overrides or {}
    income      = fetch_income_statement(ticker, limit=5)
    balance     = fetch_balance_sheet(ticker, limit=5)
    cashflow    = fetch_cash_flow(ticker, limit=5)
    key_metrics = fetch_key_metrics(ticker, limit=5)

    result: dict = {"applicable": True}

    wacc_inputs = _derive_wacc_inputs(ticker, income, balance, country)
    for k in ("rf", "beta", "erp", "crp", "ke", "kd", "tax_rate", "wacc"):
        if k in ov:
            wacc_inputs[k] = ov[k]
    result["wacc_inputs"] = wacc_inputs
    wacc = wacc_inputs["wacc"]

    try:
        prices = fetch_prices(ticker, period="5d")
        current_price = float(prices["Close"].iloc[-1])
    except Exception:
        current_price = float("nan")
    result["current_price"] = current_price

    try:
        shares = float(key_metrics.loc[0, "sharesOutstanding"]) if "sharesOutstanding" in key_metrics.columns else float("nan")
    except Exception:
        shares = float("nan")
    result["shares_outstanding"] = shares

    # DCF
    try:
        base_revenue = float(income.loc[0, "revenue"])
        net_debt = float(balance.loc[0, "totalDebt"]) - float(balance.loc[0, "cashAndCashEquivalents"])
        ebit_margin = float(income.loc[0, "operatingIncome"]) / base_revenue
        capex_pct   = abs(float(cashflow.loc[0, "capitalExpenditure"])) / base_revenue
        da_pct      = float(income.loc[0, "depreciationAndAmortization"]) / base_revenue
        tax_rate    = ov.get("tax_rate", wacc_inputs["tax_rate"])
        rev_growth_base = ov.get("revenue_growth", [0.07, 0.07, 0.06, 0.06, 0.05,
                                                    0.04, 0.04, 0.03, 0.03, 0.03])
        rev_growth_bull = ov.get("revenue_growth_bull", [g * 1.3 for g in rev_growth_base])
        rev_growth_bear = ov.get("revenue_growth_bear", [g * 0.7 for g in rev_growth_base])
        terminal_g = ov.get("terminal_growth", 0.025)

        def _dcf(growth_rates):
            fcfs = project_fcf(base_revenue, growth_rates, ebit_margin, capex_pct, da_pct, tax_rate)
            tv   = compute_terminal_value(fcfs[-1], wacc, terminal_g)
            price = compute_dcf_price(fcfs, tv, wacc, net_debt, shares) if shares == shares and shares else float("nan")
            return fcfs, tv, price

        fcfs_base, tv_base, price_base = _dcf(rev_growth_base)
        _, _, price_bull = _dcf(rev_growth_bull)
        _, _, price_bear = _dcf(rev_growth_bear)

        wacc_range   = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
        growth_range = [0.005, 0.01, 0.02, 0.03, 0.035]
        sensitivity  = compute_dcf_sensitivity(fcfs_base, fcfs_base[-1], wacc_range, growth_range, net_debt, shares)

        result["dcf_base"] = {
            "fcf_series": fcfs_base, "terminal_value": tv_base,
            "price_base": price_base, "price_bull": price_bull, "price_bear": price_bear,
        }
        result["dcf_sensitivity"] = sensitivity
    except Exception:
        result["dcf_base"] = None
        result["dcf_sensitivity"] = pd.DataFrame()
        net_debt = float("nan")

    # Comps
    try:
        peers = fetch_peers(ticker)[:6]
        rows = []
        for p in [ticker] + peers:
            km = fetch_key_metrics(p, limit=1)
            if not km.empty:
                cols = [c for c in ["peRatio", "pbRatio", "evToEbitda", "netProfitMargin", "revenueGrowth"] if c in km.columns]
                row = km.iloc[0][cols].to_dict()
                row["symbol"] = p
                rows.append(row)
        comps = pd.DataFrame(rows).set_index("symbol") if rows else pd.DataFrame()
        result["comps"] = comps

        if not comps.empty and ticker in comps.index and "peRatio" in comps.columns:
            median_pe = comps["peRatio"].median()
            median_ev_ebitda = comps["evToEbitda"].median() if "evToEbitda" in comps.columns else float("nan")
            try:
                eps = float(income.loc[0, "eps"]) if "eps" in income.columns else float("nan")
                ebitda = float(income.loc[0, "operatingIncome"]) + float(income.loc[0, "depreciationAndAmortization"])
                ev_from_ebitda = median_ev_ebitda * ebitda
                equity_from_ev = ev_from_ebitda - net_debt
                price_from_ev  = equity_from_ev / shares if shares == shares and shares else float("nan")
                price_from_pe  = median_pe * eps
                result["comps_implied"] = {
                    "price_from_pe": price_from_pe,
                    "price_from_ev_ebitda": price_from_ev,
                }
            except Exception:
                result["comps_implied"] = None
        else:
            result["comps_implied"] = None
    except Exception:
        result["comps"] = pd.DataFrame()
        result["comps_implied"] = None

    # DDM
    try:
        divs = cashflow["dividendsPaid"].abs() if "dividendsPaid" in cashflow.columns else pd.Series(dtype=float)
        has_3yr_div = (len(divs) >= 3) and (divs.head(3) > 0).all()
        if has_3yr_div:
            current_div = float(divs.iloc[0])
            div_growth = float(divs.pct_change(-1).iloc[0]) if len(divs) >= 2 else 0.05
            div_growth = max(0, min(div_growth, 0.20))
            ddm_price = compute_ddm_price(
                current_dividend=current_div / (shares or 1),
                growth_rates=[div_growth] * 5,
                ke=wacc_inputs["ke"],
                stable_growth=0.03,
            )
            result["ddm"] = {
                "applicable": True, "price": ddm_price,
                "current_dividend_per_share": current_div / (shares or 1),
            }
        else:
            result["ddm"] = {"applicable": False, "reason": "Insufficient dividend history (need ≥3 years)"}
    except Exception:
        result["ddm"] = {"applicable": False, "reason": "Could not compute DDM"}

    return result
