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
