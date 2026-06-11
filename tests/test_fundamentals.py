# tests/test_fundamentals.py
import pandas as pd
from unittest.mock import patch, MagicMock
import data.fundamentals as fund


def _mk(income=None, balance=None, cashflow=None, info=None):
    m = MagicMock()
    m.income_stmt = income if income is not None else pd.DataFrame()
    m.balance_sheet = balance if balance is not None else pd.DataFrame()
    m.cashflow = cashflow if cashflow is not None else pd.DataFrame()
    m.info = info if info is not None else {}
    return m


def _income():
    # yfinance shape: rows = line-item labels, columns = period timestamps (newest first)
    return pd.DataFrame({
        pd.Timestamp("2023-12-31"): {
            "Total Revenue": 100.0, "Cost Of Revenue": 60.0, "Gross Profit": 40.0,
            "Operating Income": 20.0, "Net Income": 15.0, "Pretax Income": 18.0,
            "Tax Provision": 3.0, "Diluted Average Shares": 1000.0,
            "Reconciled Depreciation": 5.0,
        },
        pd.Timestamp("2022-12-31"): {"Total Revenue": 90.0, "Net Income": 12.0},
    })


def test_income_statement_maps_yf_labels():
    fund._CACHE.clear()
    with patch.object(fund.yf, "Ticker", return_value=_mk(income=_income())):
        df = fund.fetch_income_statement("AAPL")
    assert not df.empty and len(df) == 2
    assert df.loc[0, "revenue"] == 100.0
    assert df.loc[0, "netIncome"] == 15.0
    assert df.loc[0, "operatingIncome"] == 20.0
    assert df.loc[0, "weightedAverageShsOut"] == 1000.0
    assert df.loc[0, "depreciationAndAmortization"] == 5.0


def test_income_da_backfilled_from_cashflow():
    fund._CACHE.clear()
    inc = pd.DataFrame({pd.Timestamp("2023-12-31"): {"Total Revenue": 100.0}})  # no D&A
    cf = pd.DataFrame({pd.Timestamp("2023-12-31"): {"Operating Cash Flow": 30.0,
                                                    "Depreciation And Amortization": 7.0}})
    with patch.object(fund.yf, "Ticker", return_value=_mk(income=inc, cashflow=cf)):
        df = fund.fetch_income_statement("AAPL")
    assert df.loc[0, "depreciationAndAmortization"] == 7.0


def test_balance_sheet_maps():
    fund._CACHE.clear()
    bal = pd.DataFrame({pd.Timestamp("2023-12-31"): {
        "Total Assets": 500.0, "Stockholders Equity": 200.0, "Total Debt": 100.0}})
    with patch.object(fund.yf, "Ticker", return_value=_mk(balance=bal)):
        df = fund.fetch_balance_sheet("AAPL")
    assert df.loc[0, "totalAssets"] == 500.0
    assert df.loc[0, "totalEquity"] == 200.0
    assert df.loc[0, "totalDebt"] == 100.0


def test_cash_flow_maps():
    fund._CACHE.clear()
    cf = pd.DataFrame({pd.Timestamp("2023-12-31"): {
        "Operating Cash Flow": 30.0, "Capital Expenditure": -5.0, "Free Cash Flow": 25.0}})
    with patch.object(fund.yf, "Ticker", return_value=_mk(cashflow=cf)):
        df = fund.fetch_cash_flow("AAPL")
    assert df.loc[0, "operatingCashFlow"] == 30.0
    assert df.loc[0, "capitalExpenditure"] == -5.0
    assert df.loc[0, "freeCashFlow"] == 25.0


def test_key_metrics_from_info_normalizes_debt_equity():
    fund._CACHE.clear()
    info = {"trailingPE": 28.5, "priceToBook": 4.2, "returnOnEquity": 0.18,
            "debtToEquity": 154.0, "profitMargins": 0.25, "marketCap": 3e12,
            "currentRatio": 1.1, "enterpriseToEbitda": 22.0, "revenueGrowth": 0.08,
            "sharesOutstanding": 1.5e10}
    with patch.object(fund.yf, "Ticker", return_value=_mk(info=info)):
        df = fund.fetch_key_metrics("AAPL")
    assert df.loc[0, "peRatio"] == 28.5
    assert df.loc[0, "roe"] == 0.18
    assert df.loc[0, "debtToEquity"] == 1.54   # 154% -> 1.54x
    assert df.loc[0, "marketCap"] == 3e12


def test_key_metrics_empty_info_returns_empty():
    fund._CACHE.clear()
    with patch.object(fund.yf, "Ticker", return_value=_mk(info={})):
        df = fund.fetch_key_metrics("AAPL")
    assert df.empty


def test_fetch_peers_curated_map():
    """Known tickers resolve to a curated peer set; the ticker itself is excluded."""
    peers = fund.fetch_peers("AAPL")
    assert isinstance(peers, list) and len(peers) > 0
    assert "AAPL" not in peers


def test_fetch_peers_sector_fallback():
    """Unlisted tickers fall back to a sector bucket via yfinance info.sector."""
    fund._CACHE.clear()
    with patch.object(fund.yf, "Ticker", return_value=_mk(info={"sector": "Healthcare"})):
        peers = fund.fetch_peers("ZZZZ")
    assert peers and "ZZZZ" not in peers


def test_fetch_peers_unknown_returns_empty():
    """No curated entry and no usable sector → empty list."""
    fund._CACHE.clear()
    with patch.object(fund.yf, "Ticker", return_value=_mk(info={})):
        assert fund.fetch_peers("ZZZZ") == []
