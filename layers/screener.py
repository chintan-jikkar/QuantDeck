# layers/screener.py — no Streamlit imports
import pandas as pd
import numpy as np
import yfinance as yf
from data.fundamentals import fetch_key_metrics

DEFAULT_FILTERS = {
    "pe_max":            30.0,
    "pb_max":             5.0,
    "ev_ebitda_max":     15.0,
    "roe_min":            0.10,
    "debt_equity_max":    1.5,
    "revenue_growth_min": 0.0,
    "net_margin_min":     0.05,
    "current_ratio_min":  1.0,
    "rsi_min":            0.0,
    "rsi_max":          100.0,
    "above_50sma":       False,
    "above_200sma":      False,
}

_DOW30 = [
    "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
    "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
    "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WBA", "WMT",
]


def _fetch_universe_tickers(universe: str) -> list[str]:
    if universe == "Dow Jones 30":
        return _DOW30
    # S&P 500 / NASDAQ 100 constituents are scraped from Wikipedia and cached
    # (no free live constituents API exists for these indices). Capped at 100
    # tickers to keep a screen responsive.
    from data.universe import fetch_constituents
    return fetch_constituents(universe)[:100]


def _fetch_key_metrics_batch(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        try:
            km = fetch_key_metrics(ticker, limit=1)
            if not km.empty:
                row = km.iloc[0].to_dict()
                row["symbol"] = ticker
                rows.append(row)
        except Exception:
            pass
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("symbol")


def _fetch_technical_indicators(tickers: list[str]) -> pd.DataFrame:
    raw = yf.download(tickers, period="1y", interval="1d", auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame(index=tickers)

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:
        close = raw[["Close"]]
        close.columns = tickers[:1]

    rows = {}
    for ticker in tickers:
        if ticker not in close.columns:
            continue
        prices = close[ticker].dropna()
        if len(prices) < 30:
            continue
        from data.prices import compute_rsi
        rsi_series = compute_rsi(prices)
        sma50  = prices.rolling(50).mean()
        sma200 = prices.rolling(200).mean()
        last = prices.iloc[-1]
        rows[ticker] = {
            "rsi":          float(rsi_series.iloc[-1]) if not rsi_series.empty else float("nan"),
            "above_50sma":  bool(last > sma50.iloc[-1])  if not sma50.isna().all()  else False,
            "above_200sma": bool(last > sma200.iloc[-1]) if not sma200.isna().all() else False,
        }
    return pd.DataFrame(rows).T


def apply_fundamental_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    col_filter_map = [
        ("peRatio",         "pe_max",             "le"),
        ("pbRatio",         "pb_max",             "le"),
        ("evToEbitda",      "ev_ebitda_max",       "le"),
        ("roe",             "roe_min",             "ge"),
        ("debtToEquity",    "debt_equity_max",     "le"),
        ("revenueGrowth",   "revenue_growth_min",  "ge"),
        ("netProfitMargin", "net_margin_min",      "ge"),
        ("currentRatio",    "current_ratio_min",   "ge"),
    ]
    for col, key, direction in col_filter_map:
        if key in filters and col in df.columns:
            threshold = filters[key]
            col_vals = pd.to_numeric(df[col], errors="coerce")
            if direction == "le":
                mask &= col_vals.fillna(float("inf")) <= threshold
            else:
                mask &= col_vals.fillna(float("-inf")) >= threshold
    return df[mask]


def apply_technical_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if "rsi_min" in filters and "rsi" in df.columns:
        mask &= pd.to_numeric(df["rsi"], errors="coerce").fillna(50) >= filters["rsi_min"]
    if "rsi_max" in filters and "rsi" in df.columns:
        mask &= pd.to_numeric(df["rsi"], errors="coerce").fillna(50) <= filters["rsi_max"]
    if filters.get("above_50sma") and "above_50sma" in df.columns:
        mask &= df["above_50sma"].fillna(False)
    if filters.get("above_200sma") and "above_200sma" in df.columns:
        mask &= df["above_200sma"].fillna(False)
    return df[mask]


def compute_composite_score(df: pd.DataFrame, weight_mode: str = "equal") -> pd.Series:
    score_cols = {
        "peRatio":         ("lower_better", 1.0),
        "pbRatio":         ("lower_better", 1.0),
        "evToEbitda":      ("lower_better", 1.0),
        "roe":             ("higher_better", 1.5),
        "revenueGrowth":   ("higher_better", 1.5),
        "netProfitMargin": ("higher_better", 1.0),
    }
    scores = pd.DataFrame(index=df.index)
    for col, (direction, _weight) in score_cols.items():
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        ranked = numeric.rank(pct=True, na_option="bottom")
        if direction == "lower_better":
            ranked = 1.0 - ranked
        scores[col] = ranked

    if scores.empty:
        return pd.Series(50.0, index=df.index)

    weights = {col: w for col, (_, w) in score_cols.items() if col in scores.columns}
    total_weight = sum(weights.values())
    weighted = sum(scores[col] * w for col, w in weights.items() if col in scores.columns)
    return (weighted / total_weight * 100).rename("composite_score")


def run_screener(
    universe: str,
    filters: dict,
    custom_tickers: list[str] | None = None,
) -> pd.DataFrame:
    tickers = custom_tickers if universe == "custom" else _fetch_universe_tickers(universe)
    if not tickers:
        return pd.DataFrame()

    fund_df = _fetch_key_metrics_batch(tickers)
    if fund_df.empty:
        return pd.DataFrame()

    merged_filters = {**DEFAULT_FILTERS, **filters}
    fund_filtered = apply_fundamental_filters(fund_df, merged_filters)
    if fund_filtered.empty:
        return fund_filtered

    tech_df = _fetch_technical_indicators(fund_filtered.index.tolist())
    combined = fund_filtered.join(tech_df, how="left")
    tech_filtered = apply_technical_filters(combined, merged_filters)

    scores = compute_composite_score(tech_filtered)
    tech_filtered = tech_filtered.copy()
    tech_filtered["composite_score"] = scores

    return tech_filtered.sort_values("composite_score", ascending=False)


# ── FX + Commodity Screener ───────────────────────────────────────────────────

def _fetch_asset_technicals(tickers: list[str]) -> pd.DataFrame:
    """Fetch close prices for a list of yfinance tickers and compute technicals.

    Returns DataFrame indexed by ticker with columns:
    rsi, momentum_12_1, realized_vol_30d, last_price.
    """
    raw = yf.download(tickers, period="2y", interval="1d", auto_adjust=True, progress=False)
    if raw.empty:
        return pd.DataFrame(index=tickers)

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:
        close = raw[["Close"]]
        close.columns = [tickers[0]]

    rows = {}
    for ticker in tickers:
        if ticker not in close.columns:
            continue
        prices = close[ticker].dropna()
        n = len(prices)
        if n < 30:
            continue
        from data.prices import compute_rsi
        rsi_series = compute_rsi(prices)
        past = float(prices.iloc[-22]) if n >= 22 else float("nan")
        ref  = float(prices.iloc[max(0, n - 252)]) if n >= 252 else float(prices.iloc[0])
        mom  = (past / ref - 1.0) if (ref and ref == ref and past == past) else float("nan")
        vol  = float(prices.pct_change().iloc[-30:].std() * (252 ** 0.5))
        rows[ticker] = {
            "rsi":              float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else float("nan"),
            "momentum_12_1":    mom,
            "realized_vol_30d": vol,
            "last_price":       float(prices.iloc[-1]),
        }
    return pd.DataFrame(rows).T


def run_fx_screener(group: str = "G10 Majors") -> pd.DataFrame:
    """Screen FX pairs in a group by momentum, RSI, and realized vol.

    Returns a DataFrame sorted by |momentum| composite score descending,
    with display names as the index (not raw yfinance tickers).
    """
    from config import FX_PAIRS
    pairs = FX_PAIRS.get(group, {})
    if not pairs:
        return pd.DataFrame()
    tickers = list(pairs.values())
    tech_df = _fetch_asset_technicals(tickers)
    if tech_df.empty:
        return pd.DataFrame()
    ticker_to_name = {v: k for k, v in pairs.items()}
    tech_df.index = [ticker_to_name.get(t, t) for t in tech_df.index]
    tech_df["composite_score"] = (
        pd.to_numeric(tech_df["momentum_12_1"], errors="coerce").abs()
        .rank(pct=True) * 100
    )
    return tech_df.sort_values("composite_score", ascending=False)


def run_commodity_screener(group: str = "all") -> pd.DataFrame:
    """Screen commodities in a group by momentum, RSI, and realized vol.

    group: one of the COMMODITIES keys ("Precious Metals", "Energy", etc.)
    or "all" to screen across all groups.
    Returns a DataFrame sorted by |momentum| composite score descending.
    """
    from config import COMMODITIES
    if group == "all":
        pairs = {name: ticker for grp in COMMODITIES.values() for name, ticker in grp.items()}
    else:
        pairs = COMMODITIES.get(group, {})
    if not pairs:
        return pd.DataFrame()
    tickers = list(pairs.values())
    tech_df = _fetch_asset_technicals(tickers)
    if tech_df.empty:
        return pd.DataFrame()
    ticker_to_name = {v: k for k, v in pairs.items()}
    tech_df.index = [ticker_to_name.get(t, t) for t in tech_df.index]
    tech_df["composite_score"] = (
        pd.to_numeric(tech_df["momentum_12_1"], errors="coerce").abs()
        .rank(pct=True) * 100
    )
    return tech_df.sort_values("composite_score", ascending=False)
