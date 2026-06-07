# tests/test_universe.py
from unittest.mock import patch, MagicMock


def _html_table(symbol_col="Symbol", n=60):
    rows = "".join(f"<tr><td>SYM{i}</td><td>Co {i}</td></tr>" for i in range(n))
    return f"<table><tr><th>{symbol_col}</th><th>Security</th></tr>{rows}</table>"


def _mock_resp(text):
    m = MagicMock()
    m.text = text
    m.raise_for_status = MagicMock()
    return m


def test_scrape_parses_symbol_column():
    from data.universe import _scrape
    with patch("data.universe.requests.get", return_value=_mock_resp(_html_table("Symbol"))):
        syms = _scrape("http://x", ("Symbol", "Ticker"))
    assert len(syms) == 60
    assert "SYM0" in syms


def test_scrape_uppercases_and_strips():
    from data.universe import _scrape
    rows = "".join(f"<tr><td> sym{i} </td></tr>" for i in range(55))
    html = f"<table><tr><th>Symbol</th></tr>{rows}</table>"
    with patch("data.universe.requests.get", return_value=_mock_resp(html)):
        syms = _scrape("http://x", ("Symbol",))
    assert syms[0] == "SYM0"


def test_scrape_skips_small_tables():
    """A table with fewer than 50 symbols is treated as a navbox, not constituents."""
    from data.universe import _scrape
    html = "<table><tr><th>Symbol</th></tr><tr><td>AAA</td></tr><tr><td>BBB</td></tr></table>"
    with patch("data.universe.requests.get", return_value=_mock_resp(html)):
        syms = _scrape("http://x", ("Symbol",))
    assert syms == []


def test_fetch_sp500_falls_back_on_error():
    import data.universe as u
    u.fetch_sp500_tickers.cache_clear()
    with patch("data.universe.requests.get", side_effect=Exception("network down")):
        out = u.fetch_sp500_tickers()
    u.fetch_sp500_tickers.cache_clear()
    assert "AAPL" in out
    assert out == tuple(u._FALLBACK)


def test_fetch_constituents_returns_fresh_list():
    import data.universe as u
    u.fetch_sp500_tickers.cache_clear()
    with patch("data.universe.requests.get", return_value=_mock_resp(_html_table("Symbol"))):
        out = u.fetch_constituents("S&P 500")
    u.fetch_sp500_tickers.cache_clear()
    assert isinstance(out, list)
    assert len(out) == 60


def test_fetch_constituents_nasdaq_uses_ticker_column():
    import data.universe as u
    u.fetch_nasdaq100_tickers.cache_clear()
    with patch("data.universe.requests.get", return_value=_mock_resp(_html_table("Ticker"))):
        out = u.fetch_constituents("NASDAQ 100")
    u.fetch_nasdaq100_tickers.cache_clear()
    assert len(out) == 60
