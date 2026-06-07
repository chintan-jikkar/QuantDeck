# tests/test_fundamentals.py
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest


def _mock_get(json_data):
    m = MagicMock()
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


def test_fetch_income_statement_returns_dataframe(sample_income_statement, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test_key")
    with patch("data.fundamentals.requests.get") as mock_get:
        mock_get.return_value = _mock_get(sample_income_statement)
        from data.fundamentals import fetch_income_statement
        df = fetch_income_statement("AAPL")
    assert not df.empty
    assert "revenue" in df.columns
    assert "netIncome" in df.columns
    assert len(df) == 2


def test_fetch_income_statement_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    from data.fundamentals import fetch_income_statement
    with pytest.raises(EnvironmentError, match="FMP_API_KEY"):
        fetch_income_statement("AAPL")


def test_fetch_balance_sheet_returns_dataframe(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test_key")
    payload = [{"date": "2023-12-31", "totalDebt": 50_000_000, "totalEquity": 100_000_000}]
    with patch("data.fundamentals.requests.get") as mock_get:
        mock_get.return_value = _mock_get(payload)
        from data.fundamentals import fetch_balance_sheet
        df = fetch_balance_sheet("AAPL")
    assert "totalDebt" in df.columns
    assert "totalEquity" in df.columns


def test_fetch_cash_flow_returns_dataframe(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test_key")
    payload = [{"date": "2023-12-31", "operatingCashFlow": 30_000_000, "capitalExpenditure": -5_000_000}]
    with patch("data.fundamentals.requests.get") as mock_get:
        mock_get.return_value = _mock_get(payload)
        from data.fundamentals import fetch_cash_flow
        df = fetch_cash_flow("AAPL")
    assert "operatingCashFlow" in df.columns


def test_fetch_key_metrics_returns_dataframe(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test_key")
    payload = [{"date": "2023-12-31", "peRatio": 28.5, "pbRatio": 4.2, "roe": 0.18}]
    with patch("data.fundamentals.requests.get") as mock_get:
        mock_get.return_value = _mock_get(payload)
        from data.fundamentals import fetch_key_metrics
        df = fetch_key_metrics("AAPL")
    assert "peRatio" in df.columns


def test_fetch_peers_returns_list(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test_key")
    # /stable/stock-peers returns a flat list of peer rows (not a nested peersList),
    # and the queried symbol itself is excluded from the result.
    payload = [
        {"symbol": "AAPL", "companyName": "Apple Inc.", "price": 307.0, "mktCap": 4.6e12},
        {"symbol": "MSFT", "companyName": "Microsoft", "price": 400.0, "mktCap": 3.0e12},
        {"symbol": "GOOG", "companyName": "Alphabet", "price": 150.0, "mktCap": 2.0e12},
        {"symbol": "META", "companyName": "Meta Platforms", "price": 500.0, "mktCap": 1.3e12},
    ]
    with patch("data.fundamentals.requests.get") as mock_get:
        mock_get.return_value = _mock_get(payload)
        from data.fundamentals import fetch_peers
        peers = fetch_peers("AAPL")
    assert isinstance(peers, list)
    assert "MSFT" in peers
    assert "AAPL" not in peers  # queried symbol excluded


def test_fetch_peers_returns_empty_list_when_no_data(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test_key")
    with patch("data.fundamentals.requests.get") as mock_get:
        mock_get.return_value = _mock_get([])
        from data.fundamentals import fetch_peers
        peers = fetch_peers("UNKNOWN")
    assert peers == []
