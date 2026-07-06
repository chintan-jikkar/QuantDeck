# data/universe.py — no Streamlit imports
"""Free index-constituent lists for the Screener.

No free live API returns S&P 500 / NASDAQ 100 membership, so it's scraped
from Wikipedia and cached for the life of the process. A small mega-cap
fallback keeps the Screener usable if Wikipedia is unreachable or
restructures its tables.

Symbols are returned in Wikipedia's form (e.g. "BRK.B"). The handful of
dotted tickers will not resolve on yfinance for the technical overlay and
are skipped there gracefully.
"""
from io import StringIO
import functools
import pandas as pd
import requests

_UA = {"User-Agent": "Mozilla/5.0 (QuantDeck screener)"}
_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# Resilience fallback (mega-caps) used only if a scrape fails entirely.
_FALLBACK = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "JPM",
    "LLY", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "JNJ", "WMT", "ORCL",
]


def _scrape(url: str, symbol_cols: tuple[str, ...]) -> list[str]:
    """Return the ticker column from the first Wikipedia table that has one.

    The >=50 guard skips small navbox/sidebar tables and only accepts the
    actual constituents table.
    """
    resp = requests.get(url, headers=_UA, timeout=15)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    for table in tables:
        for col in symbol_cols:
            if col in table.columns:
                syms = table[col].astype(str).str.strip().str.upper().tolist()
                syms = [s for s in syms if s and s != "NAN"]
                if len(syms) >= 50:
                    return syms
    return []


@functools.lru_cache(maxsize=1)
def fetch_sp500_tickers() -> tuple[str, ...]:
    try:
        syms = _scrape(_SP500_URL, ("Symbol", "Ticker"))
        return tuple(syms) if syms else tuple(_FALLBACK)
    except Exception:
        return tuple(_FALLBACK)


@functools.lru_cache(maxsize=1)
def fetch_nasdaq100_tickers() -> tuple[str, ...]:
    try:
        syms = _scrape(_NASDAQ100_URL, ("Ticker", "Symbol"))
        return tuple(syms) if syms else tuple(_FALLBACK)
    except Exception:
        return tuple(_FALLBACK)


def fetch_constituents(universe: str) -> list[str]:
    """Tickers for a named universe. Returns a fresh list (safe to mutate)."""
    if universe == "NASDAQ 100":
        return list(fetch_nasdaq100_tickers())
    return list(fetch_sp500_tickers())
