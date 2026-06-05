# data/fundamentals.py
import os
import requests
import pandas as pd

FMP_BASE = "https://financialmodelingprep.com/api/v3"


def _get(endpoint: str, params: dict | None = None) -> list | dict:
    api_key = os.getenv("FMP_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "FMP_API_KEY is not set. Get a free key at https://financialmodelingprep.com/"
        )
    p = {"apikey": api_key, **(params or {})}
    resp = requests.get(f"{FMP_BASE}/{endpoint}", params=p, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_income_statement(ticker: str, limit: int = 5) -> pd.DataFrame:
    data = _get(f"income-statement/{ticker}", {"limit": limit})
    return pd.DataFrame(data)


def fetch_balance_sheet(ticker: str, limit: int = 5) -> pd.DataFrame:
    data = _get(f"balance-sheet-statement/{ticker}", {"limit": limit})
    return pd.DataFrame(data)


def fetch_cash_flow(ticker: str, limit: int = 5) -> pd.DataFrame:
    data = _get(f"cash-flow-statement/{ticker}", {"limit": limit})
    return pd.DataFrame(data)


def fetch_key_metrics(ticker: str, limit: int = 5) -> pd.DataFrame:
    data = _get(f"key-metrics/{ticker}", {"limit": limit})
    return pd.DataFrame(data)


def fetch_peers(ticker: str) -> list[str]:
    data = _get("stock_peers", {"symbol": ticker})
    if data and isinstance(data, list):
        return data[0].get("peersList", [])
    return []
