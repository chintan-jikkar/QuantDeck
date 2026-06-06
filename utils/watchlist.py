# utils/watchlist.py
import json
import os
from pathlib import Path


def _watchlist_path() -> Path:
    """Return the path to the watchlist JSON file.

    Overridable via QUANTDECK_WATCHLIST_PATH env var (used in tests).
    Defaults to ~/.quantdeck_watchlist.json.
    """
    override = os.getenv("QUANTDECK_WATCHLIST_PATH")
    if override:
        return Path(override)
    return Path.home() / ".quantdeck_watchlist.json"


def load_watchlist() -> list[str]:
    """Return the saved watchlist as a list of ticker strings."""
    path = _watchlist_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_watchlist(tickers: list[str]) -> None:
    """Persist the watchlist to disk."""
    path = _watchlist_path()
    path.write_text(json.dumps(tickers))


def add_ticker(ticker: str) -> None:
    """Add a ticker to the watchlist (no-op if already present)."""
    tickers = load_watchlist()
    if ticker not in tickers:
        tickers.append(ticker)
        save_watchlist(tickers)


def remove_ticker(ticker: str) -> None:
    """Remove a ticker from the watchlist (no-op if not present)."""
    tickers = load_watchlist()
    if ticker in tickers:
        tickers.remove(ticker)
        save_watchlist(tickers)
