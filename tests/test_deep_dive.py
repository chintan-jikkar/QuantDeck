# tests/test_deep_dive.py
import pandas as pd
import numpy as np
import pytest


def _income(years=2):
    return pd.DataFrame([
        {
            "date": "2023-12-31",
            "revenue": 400_000_000,
            "costOfRevenue": 240_000_000,
            "grossProfit": 160_000_000,
            "operatingIncome": 80_000_000,
            "netIncome": 60_000_000,
            "sellingGeneralAndAdministrativeExpenses": 40_000_000,
            "depreciationAndAmortization": 20_000_000,
            "interestExpense": 5_000_000,
            "incomeTaxExpense": 15_000_000,
            "incomeBeforeTax": 75_000_000,
            "eps": 3.00,
        },
        {
            "date": "2022-12-31",
            "revenue": 360_000_000,
            "costOfRevenue": 216_000_000,
            "grossProfit": 144_000_000,
            "operatingIncome": 70_000_000,
            "netIncome": 52_000_000,
            "sellingGeneralAndAdministrativeExpenses": 37_000_000,
            "depreciationAndAmortization": 18_000_000,
            "interestExpense": 5_000_000,
            "incomeTaxExpense": 13_000_000,
            "incomeBeforeTax": 65_000_000,
            "eps": 2.60,
        },
    ])


def _balance(years=2):
    return pd.DataFrame([
        {
            "date": "2023-12-31",
            "totalAssets": 500_000_000,
            "totalCurrentAssets": 150_000_000,
            "propertyPlantEquipmentNet": 200_000_000,
            "netReceivables": 50_000_000,
            "totalCurrentLiabilities": 100_000_000,
            "longTermDebt": 80_000_000,
            "totalDebt": 180_000_000,
            "totalEquity": 220_000_000,
            "cashAndCashEquivalents": 30_000_000,
        },
        {
            "date": "2022-12-31",
            "totalAssets": 450_000_000,
            "totalCurrentAssets": 130_000_000,
            "propertyPlantEquipmentNet": 185_000_000,
            "netReceivables": 42_000_000,
            "totalCurrentLiabilities": 90_000_000,
            "longTermDebt": 80_000_000,
            "totalDebt": 170_000_000,
            "totalEquity": 190_000_000,
            "cashAndCashEquivalents": 25_000_000,
        },
    ])


def _cashflow(years=2):
    return pd.DataFrame([
        {
            "date": "2023-12-31",
            "operatingCashFlow": 72_000_000,
            "capitalExpenditure": -25_000_000,
            "dividendsPaid": -10_000_000,
            "commonStockRepurchased": -15_000_000,
            "freeCashFlow": 47_000_000,
        },
        {
            "date": "2022-12-31",
            "operatingCashFlow": 60_000_000,
            "capitalExpenditure": -20_000_000,
            "dividendsPaid": -8_000_000,
            "commonStockRepurchased": -10_000_000,
            "freeCashFlow": 40_000_000,
        },
    ])


def test_compute_margins_gross():
    from layers.deep_dive import compute_margins
    result = compute_margins(_income())
    assert result.loc[0, "gross_margin"] == pytest.approx(0.40, rel=1e-4)


def test_compute_margins_operating():
    from layers.deep_dive import compute_margins
    result = compute_margins(_income())
    assert result.loc[0, "operating_margin"] == pytest.approx(0.20, rel=1e-4)


def test_compute_margins_net():
    from layers.deep_dive import compute_margins
    result = compute_margins(_income())
    assert result.loc[0, "net_margin"] == pytest.approx(0.15, rel=1e-4)


def test_compute_margins_revenue_yoy():
    from layers.deep_dive import compute_margins
    result = compute_margins(_income())
    assert result.loc[0, "revenue_yoy"] == pytest.approx(0.1111, rel=1e-3)


def test_balance_sheet_debt_equity():
    from layers.deep_dive import compute_balance_sheet_ratios
    result = compute_balance_sheet_ratios(_balance(), _income())
    assert result.loc[0, "debt_equity"] == pytest.approx(0.818, rel=1e-3)


def test_balance_sheet_current_ratio():
    from layers.deep_dive import compute_balance_sheet_ratios
    result = compute_balance_sheet_ratios(_balance(), _income())
    assert result.loc[0, "current_ratio"] == pytest.approx(1.5, rel=1e-4)


def test_balance_sheet_interest_coverage():
    from layers.deep_dive import compute_balance_sheet_ratios
    result = compute_balance_sheet_ratios(_balance(), _income())
    assert result.loc[0, "interest_coverage"] == pytest.approx(16.0, rel=1e-4)


def test_cash_conversion_ratio():
    from layers.deep_dive import compute_earnings_quality
    result = compute_earnings_quality(_income(), _cashflow(), _balance())
    assert result["ccr"].iloc[0] == pytest.approx(1.2, rel=1e-4)


def test_accruals_ratio():
    from layers.deep_dive import compute_earnings_quality
    result = compute_earnings_quality(_income(), _cashflow(), _balance())
    assert result["accruals_ratio"].iloc[0] == pytest.approx(-0.02526, rel=1e-2)


def test_beneish_clean_company_below_threshold():
    from layers.deep_dive import compute_beneish_mscore
    score = compute_beneish_mscore(_income(), _balance(), _cashflow())
    assert isinstance(score, float)
    assert score < -2.22


def test_beneish_clean_company_exact_score():
    """Pin the EXACT M-score on the clean fixture, not just the threshold.

    A regression in any of the 8 coefficients — or the DEPI orientation
    (numerator/denominator swap) — would move this value while possibly
    keeping it below -2.22, so the threshold test alone would miss it.
    """
    from layers.deep_dive import compute_beneish_mscore
    score = compute_beneish_mscore(_income(), _balance(), _cashflow())
    assert score == pytest.approx(-2.4103, abs=1e-4)


def test_beneish_manipulator_above_threshold():
    from layers.deep_dive import compute_beneish_mscore
    income_bad = _income()
    balance_bad = _balance()
    cashflow_bad = _cashflow()
    balance_bad.loc[0, "netReceivables"] = 120_000_000
    income_bad.loc[0, "costOfRevenue"] = 320_000_000
    income_bad.loc[0, "grossProfit"] = 80_000_000
    cashflow_bad.loc[0, "operatingCashFlow"] = 10_000_000
    score = compute_beneish_mscore(income_bad, balance_bad, cashflow_bad)
    assert score > -2.22


def test_capital_allocation_exact_split():
    """Pin the exact %FCF split for the clean fixture (2023 row).

    CFO=72M; capex=25M, dividends=10M, buybacks=15M (all abs of negatives);
    retained = (72−25−10−15).clip(lower=0) = 22M; total = 72M.
    """
    from layers.deep_dive import compute_capital_allocation
    result = compute_capital_allocation(_income(), _cashflow(), _balance())
    row = result.iloc[0]
    assert row["capex_pct"]     == pytest.approx(25 / 72, rel=1e-6)
    assert row["dividends_pct"] == pytest.approx(10 / 72, rel=1e-6)
    assert row["buybacks_pct"]  == pytest.approx(15 / 72, rel=1e-6)
    assert row["retained_pct"]  == pytest.approx(22 / 72, rel=1e-6)


def test_capital_allocation_pct_columns_sum_to_one():
    from layers.deep_dive import compute_capital_allocation
    result = compute_capital_allocation(_income(), _cashflow(), _balance())
    pct_cols = ["capex_pct", "dividends_pct", "buybacks_pct", "retained_pct"]
    assert result[pct_cols].iloc[0].sum() == pytest.approx(1.0, abs=1e-9)


def test_capital_allocation_fcf_abs_is_separate_notion():
    """fcf_abs comes from cashflow['freeCashFlow'] (47M), a DIFFERENT notion of
    free cash than the CFO-derived split total (72M) used for the percentages."""
    from layers.deep_dive import compute_capital_allocation
    result = compute_capital_allocation(_income(), _cashflow(), _balance())
    assert result.loc[0, "fcf_abs"] == pytest.approx(47_000_000, rel=1e-9)


def test_capital_allocation_retained_clips_at_zero():
    """When capex+dividends+buybacks exceed CFO, retained clips to 0 (not negative),
    and the remaining three percentages still sum to 1.0."""
    from layers.deep_dive import compute_capital_allocation
    cashflow = _cashflow()
    # CFO=72M but capex alone 80M → cfo−capex−div−buyback < 0 → retained=0
    cashflow.loc[0, "capitalExpenditure"] = -80_000_000
    result = compute_capital_allocation(_income(), cashflow, _balance())
    row = result.iloc[0]
    assert row["retained_pct"] == pytest.approx(0.0, abs=1e-12)
    pct_cols = ["capex_pct", "dividends_pct", "buybacks_pct", "retained_pct"]
    assert result[pct_cols].iloc[0].sum() == pytest.approx(1.0, abs=1e-9)


def test_balance_sheet_ratios_mismatched_row_counts():
    """FMP can return a different number of years per statement.

    Interest coverage should join on date and degrade to NaN for unmatched
    years rather than raising a length-mismatch error.
    """
    from layers.deep_dive import compute_balance_sheet_ratios
    balance = _balance()                   # 2 years: 2023, 2022
    income_one_year = _income().iloc[[0]]  # only 2023
    result = compute_balance_sheet_ratios(balance, income_one_year)
    # 2023 row matches → 80/5 = 16; 2022 row has no income match → NaN
    assert result.loc[0, "interest_coverage"] == pytest.approx(16.0, rel=1e-4)
    assert pd.isna(result.loc[1, "interest_coverage"])


# ── FX Market Drivers ─────────────────────────────────────────────────────────

from unittest.mock import patch as _patch


def _fx_prices(n=300):
    idx = pd.date_range("2022-01-01", periods=n, freq="B")
    rng = np.random.default_rng(7)
    close = 1.10 * (1 + rng.standard_normal(n) * 0.005).cumprod()
    return pd.DataFrame({"Open": close * 0.999, "High": close * 1.001,
                          "Low": close * 0.998, "Close": close,
                          "Volume": np.ones(n)}, index=idx)


def test_run_fx_market_drivers_required_keys():
    with _patch("layers.deep_dive.fetch_prices", return_value=_fx_prices()):
        from layers.deep_dive import run_fx_market_drivers
        result = run_fx_market_drivers("EURUSD=X")
    for k in ["prices", "momentum_12_1", "realized_vol_30d", "rsi", "asset_type", "pair"]:
        assert k in result


def test_run_fx_market_drivers_asset_type_is_fx():
    with _patch("layers.deep_dive.fetch_prices", return_value=_fx_prices()):
        from layers.deep_dive import run_fx_market_drivers
        result = run_fx_market_drivers("GBPUSD=X")
    assert result["asset_type"] == "fx"


def test_run_fx_realized_vol_is_positive():
    with _patch("layers.deep_dive.fetch_prices", return_value=_fx_prices()):
        from layers.deep_dive import run_fx_market_drivers
        result = run_fx_market_drivers("EURUSD=X")
    assert result["realized_vol_30d"] > 0


def test_run_fx_rsi_in_valid_range():
    with _patch("layers.deep_dive.fetch_prices", return_value=_fx_prices()):
        from layers.deep_dive import run_fx_market_drivers
        result = run_fx_market_drivers("EURUSD=X")
    rsi = result["rsi"]
    assert 0 <= rsi <= 100
