# data/news.py
import os
import requests
import yfinance as yf

NEWSAPI_BASE = "https://newsapi.org/v2"

THEME_KEYWORDS: dict[str, list[str]] = {
    "AI & Technology": ["AI", "artificial intelligence", "chip", "semiconductor", "tech", "software", "cloud"],
    "Energy & Oil": ["oil", "crude", "OPEC", "energy", "gas", "petroleum"],
    "Interest Rates & Monetary Policy": ["Fed", "Federal Reserve", "rate", "inflation", "CPI", "yield", "interest"],
    "Emerging Markets": ["India", "China", "emerging", "EM", "developing"],
    "Healthcare & Pharma": ["pharma", "drug", "biotech", "FDA", "healthcare", "medical"],
    "Financial Services": ["bank", "finance", "credit", "lending", "insurance"],
    "Commodities & Metals": ["gold", "silver", "copper", "commodity", "metals"],
}


def fetch_headlines(ticker: str | None = None, page_size: int = 20) -> list[dict]:
    """Fetch financial headlines.

    Tries NewsAPI first (if NEWSAPI_KEY is set). Falls back to yfinance ticker news
    when NEWSAPI_KEY is absent or ticker is provided without a key.

    Each returned dict has at minimum: "title", "url", "publishedAt".
    """
    api_key = os.getenv("NEWSAPI_KEY", "")
    if api_key and ticker is None:
        return _fetch_from_newsapi(api_key, page_size)
    return _fetch_from_yfinance(ticker or "SPY")


def _fetch_from_newsapi(api_key: str, page_size: int) -> list[dict]:
    params = {
        "apiKey": api_key,
        "q": "stock market OR earnings OR Federal Reserve OR inflation",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": page_size,
    }
    resp = requests.get(f"{NEWSAPI_BASE}/everything", params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    articles = data.get("articles", [])
    return [
        {"title": a["title"], "url": a["url"], "publishedAt": a.get("publishedAt", "")}
        for a in articles
        if a.get("title")
    ]


def _fetch_from_yfinance(ticker: str) -> list[dict]:
    t = yf.Ticker(ticker)
    raw = t.news or []
    return [
        {"title": item.get("title", ""), "url": item.get("link", ""), "publishedAt": ""}
        for item in raw
        if item.get("title")
    ]


def group_by_theme(headlines: list[dict]) -> dict[str, list[dict]]:
    """Group a list of headline dicts by financial theme using keyword matching.

    Each headline may appear in multiple themes. Headlines that match no theme
    are excluded. Returns an empty dict for an empty headline list.
    """
    if not headlines:
        return {}
    grouped: dict[str, list[dict]] = {}
    for headline in headlines:
        title_lower = headline.get("title", "").lower()
        for theme, keywords in THEME_KEYWORDS.items():
            if any(kw.lower() in title_lower for kw in keywords):
                grouped.setdefault(theme, []).append(headline)
    return grouped
