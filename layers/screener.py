# layers/screener.py — no Streamlit imports
import pandas as pd
import numpy as np
import yfinance as yf
from data.fundamentals import _get

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
    endpoint_map = {
        "S&P 500":    "sp500_constituent",
        "NASDAQ 100": "nasdaq_constituent",
    }
    endpoint = endpoint_map.get(universe, "sp500_constituent")
    data = _get(endpoint)
    tickers = [row["symbol"] for row in data if row.get("symbol")]
    return tickers[:100]


def _fetch_key_metrics_batch(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        try:
            data = _get(f"key-metrics/{ticker}", {"limit": 1})
            if data:
                row = data[0]
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
