# data/fundamentals.py
import os
import requests
import pandas as pd

# FMP retired the legacy /api/v3/ endpoints (HTTP 403 on current keys).
# Everything now lives under /stable/ with the ticker passed as a `symbol`
# query parameter instead of a path segment.
FMP_BASE = "https://financialmodelingprep.com/stable"


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
    return pd.DataFrame(_get("income-statement", {"symbol": ticker, "limit": limit}))


def fetch_balance_sheet(ticker: str, limit: int = 5) -> pd.DataFrame:
    return pd.DataFrame(_get("balance-sheet-statement", {"symbol": ticker, "limit": limit}))


def fetch_cash_flow(ticker: str, limit: int = 5) -> pd.DataFrame:
    df = pd.DataFrame(_get("cash-flow-statement", {"symbol": ticker, "limit": limit}))
    # /stable/ renamed dividendsPaid → netDividendsPaid. Expose the legacy name
    # so downstream consumers (capital allocation, DDM) need no changes.
    if not df.empty and "dividendsPaid" not in df.columns:
        for alt in ("netDividendsPaid", "commonDividendsPaid"):
            if alt in df.columns:
                df["dividendsPaid"] = df[alt]
                break
    return df


def fetch_key_metrics(ticker: str, limit: int = 5) -> pd.DataFrame:
    """Per-ticker metrics normalized to QuantDeck's legacy schema.

    The /stable/ migration split valuation/profitability ratios out of
    key-metrics into separate /ratios and /financial-growth endpoints. This
    merges all three (aligned by period order) and re-exposes the legacy
    column names the rest of the app already expects — peRatio, pbRatio,
    evToEbitda, roe, debtToEquity, netProfitMargin, revenueGrowth,
    currentRatio — so the Screener, Valuation and Deep Dive layers are
    untouched by the API change.
    """
    km = pd.DataFrame(_get("key-metrics", {"symbol": ticker, "limit": limit}))
    if km.empty:
        return km

    # Fields native to /stable/key-metrics, under their new names.
    if "evToEBITDA" in km.columns:
        km["evToEbitda"] = km["evToEBITDA"]
    if "returnOnEquity" in km.columns:
        km["roe"] = km["returnOnEquity"]
    # currentRatio is already present under the same name on /stable/key-metrics.

    def _merge_aliases(endpoint: str, mapping: dict) -> None:
        try:
            other = pd.DataFrame(_get(endpoint, {"symbol": ticker, "limit": limit}))
        except Exception:
            return
        # Same ticker + limit returns the same periods in the same order, so a
        # positional copy is safe; bail if the shapes disagree.
        if other.empty or len(other) != len(km):
            return
        for src, alias in mapping.items():
            if src in other.columns:
                km[alias] = other[src].values

    _merge_aliases("ratios", {
        "priceToEarningsRatio": "peRatio",
        "priceToBookRatio":     "pbRatio",
        "debtToEquityRatio":    "debtToEquity",
        "netProfitMargin":      "netProfitMargin",
        "currentRatio":         "currentRatio",
    })
    _merge_aliases("financial-growth", {"revenueGrowth": "revenueGrowth"})

    return km


def fetch_peers(ticker: str) -> list[str]:
    """Peer tickers from /stable/stock-peers.

    The endpoint returns a flat list of {symbol, companyName, price, mktCap}
    rows (the old /api/v3/ shape nested them under a `peersList` key).
    """
    data = _get("stock-peers", {"symbol": ticker})
    if not isinstance(data, list):
        return []
    peers = []
    for row in data:
        if isinstance(row, dict):
            sym = row.get("symbol")
            if sym and sym != ticker:
                peers.append(sym)
    return peers
