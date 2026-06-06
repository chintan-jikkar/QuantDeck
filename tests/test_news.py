# tests/test_news.py
from unittest.mock import patch, MagicMock
import pytest

MOCK_NEWSAPI_RESPONSE = {
    "status": "ok",
    "articles": [
        {
            "title": "AI chip demand surges as tech companies invest billions",
            "url": "http://example.com/1",
            "publishedAt": "2024-06-01T10:00:00Z",
        },
        {
            "title": "Federal Reserve holds interest rates steady amid inflation",
            "url": "http://example.com/2",
            "publishedAt": "2024-06-01T09:00:00Z",
        },
        {
            "title": "Oil prices rise on OPEC supply cut announcement",
            "url": "http://example.com/3",
            "publishedAt": "2024-06-01T08:00:00Z",
        },
    ],
}


def test_fetch_headlines_newsapi_returns_list(monkeypatch):
    monkeypatch.setenv("NEWSAPI_KEY", "test_key")
    with patch("data.news.requests.get") as mock_get:
        m = MagicMock()
        m.json.return_value = MOCK_NEWSAPI_RESPONSE
        m.raise_for_status = MagicMock()
        mock_get.return_value = m
        from data.news import fetch_headlines
        headlines = fetch_headlines()
    assert isinstance(headlines, list)
    assert len(headlines) == 3
    assert all("title" in h for h in headlines)
    assert all("url" in h for h in headlines)


def test_fetch_headlines_yfinance_fallback(monkeypatch):
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    fake_news = [
        {"title": "AAPL hits new high", "link": "http://example.com"},
        {"title": "Market rally continues", "link": "http://example.com/2"},
    ]
    with patch("data.news.yf.Ticker") as mock_ticker_cls:
        mock_ticker = MagicMock()
        mock_ticker.news = fake_news
        mock_ticker_cls.return_value = mock_ticker
        from data.news import fetch_headlines
        headlines = fetch_headlines(ticker="AAPL")
    assert isinstance(headlines, list)
    assert len(headlines) == 2


def test_group_by_theme_returns_dict():
    from data.news import group_by_theme
    headlines = [
        {"title": "AI chip demand surges", "url": "http://a.com"},
        {"title": "Federal Reserve rate decision", "url": "http://b.com"},
        {"title": "Oil prices rise on OPEC cuts", "url": "http://c.com"},
    ]
    grouped = group_by_theme(headlines)
    assert isinstance(grouped, dict)
    for theme, items in grouped.items():
        assert isinstance(items, list)
        assert all("title" in h for h in items)


def test_group_by_theme_handles_empty():
    from data.news import group_by_theme
    result = group_by_theme([])
    assert result == {}


def test_group_by_theme_ai_keyword():
    from data.news import group_by_theme
    headlines = [{"title": "AI chip demand surges", "url": "http://a.com"}]
    grouped = group_by_theme(headlines)
    assert any("AI" in theme or "Tech" in theme for theme in grouped.keys())


# ── suggest_tickers_for_themes ─────────────────────────────────────────────────

def _finance_headlines():
    return [
        {"title": "AI chip stocks surge as Nvidia beats earnings", "url": "", "publishedAt": ""},
        {"title": "Federal Reserve signals rate hold for longer", "url": "", "publishedAt": ""},
        {"title": "Oil prices fall on OPEC+ production concerns", "url": "", "publishedAt": ""},
    ]


def test_suggest_tickers_for_themes_returns_list():
    from data.news import group_by_theme, suggest_tickers_for_themes
    grouped = group_by_theme(_finance_headlines())
    tickers = suggest_tickers_for_themes(grouped)
    assert isinstance(tickers, list)
    assert len(tickers) > 0


def test_suggest_tickers_no_duplicate():
    from data.news import group_by_theme, suggest_tickers_for_themes
    grouped = group_by_theme(_finance_headlines())
    tickers = suggest_tickers_for_themes(grouped)
    assert len(tickers) == len(set(tickers))


def test_suggest_tickers_unknown_theme_returns_empty():
    from data.news import suggest_tickers_for_themes
    assert suggest_tickers_for_themes({"Narnia Finance": []}) == []
