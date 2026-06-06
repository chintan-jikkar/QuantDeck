# tests/test_watchlist.py
import pytest


@pytest.fixture
def tmp_watchlist(tmp_path, monkeypatch):
    wl_path = tmp_path / "watchlist.json"
    monkeypatch.setenv("QUANTDECK_WATCHLIST_PATH", str(wl_path))
    return wl_path


def test_add_ticker(tmp_watchlist):
    from utils.watchlist import add_ticker, load_watchlist
    add_ticker("AAPL")
    assert "AAPL" in load_watchlist()


def test_add_ticker_deduplicates(tmp_watchlist):
    from utils.watchlist import add_ticker, load_watchlist
    add_ticker("AAPL")
    add_ticker("AAPL")
    assert load_watchlist().count("AAPL") == 1


def test_remove_ticker(tmp_watchlist):
    from utils.watchlist import add_ticker, remove_ticker, load_watchlist
    add_ticker("MSFT")
    remove_ticker("MSFT")
    assert "MSFT" not in load_watchlist()


def test_remove_nonexistent_ticker_does_not_raise(tmp_watchlist):
    from utils.watchlist import remove_ticker
    remove_ticker("NONEXISTENT")


def test_load_watchlist_empty_file(tmp_watchlist):
    from utils.watchlist import load_watchlist
    assert load_watchlist() == []


def test_watchlist_persists_across_calls(tmp_watchlist):
    from utils.watchlist import add_ticker, load_watchlist
    add_ticker("TSLA")
    add_ticker("NVDA")
    wl = load_watchlist()
    assert "TSLA" in wl
    assert "NVDA" in wl
