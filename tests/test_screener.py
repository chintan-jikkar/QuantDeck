# tests/test_screener.py
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
import pytest


def _mock_key_metrics(tickers: list[str]) -> list[dict]:
    return [
        {
            "symbol": t,
            "peRatio": 20.0 + i * 2,
            "pbRatio": 3.0 + i * 0.5,
            "evToEbitda": 12.0 + i,
            "roe": 0.18 - i * 0.02,
            "debtToEquity": 0.5 + i * 0.1,
            "revenueGrowth": 0.08 - i * 0.01,
            "netProfitMargin": 0.15 - i * 0.01,
            "currentRatio": 2.0 - i * 0.1,
            "marketCap": 500_000_000_000 - i * 10_000_000_000,
        }
        for i, t in enumerate(tickers)
    ]


def test_apply_fundamental_filters_pe():
    from layers.screener import apply_fundamental_filters
    df = pd.DataFrame(_mock_key_metrics(["AAPL", "MSFT", "GOOG"]))
    df = df.set_index("symbol")
    result = apply_fundamental_filters(df, {"pe_max": 22})
    assert "AAPL" in result.index   # PE 20 < 22
    assert "MSFT" in result.index   # PE 22 == 22
    assert "GOOG" not in result.index  # PE 24 > 22


def test_apply_fundamental_filters_roe():
    from layers.screener import apply_fundamental_filters
    df = pd.DataFrame(_mock_key_metrics(["AAPL", "MSFT", "GOOG"]))
    df = df.set_index("symbol")
    result = apply_fundamental_filters(df, {"roe_min": 0.16})
    assert "AAPL" in result.index   # ROE 0.18 > 0.16
    assert "MSFT" in result.index   # ROE 0.16 == 0.16
    assert "GOOG" not in result.index  # ROE 0.14 < 0.16


def test_compute_composite_score_range():
    from layers.screener import compute_composite_score
    df = pd.DataFrame({
        "peRatio":       [10.0, 20.0, 30.0],
        "roe":           [0.25, 0.15, 0.05],
        "revenueGrowth": [0.20, 0.10, 0.01],
    }, index=["A", "B", "C"])
    scores = compute_composite_score(df)
    assert isinstance(scores, pd.Series)
    assert (scores >= 0).all() and (scores <= 100).all()
    assert scores["A"] > scores["B"] > scores["C"]


def test_compute_composite_score_returns_series_indexed_like_df():
    from layers.screener import compute_composite_score
    df = pd.DataFrame({"peRatio": [15.0, 25.0], "roe": [0.20, 0.10]}, index=["X", "Y"])
    scores = compute_composite_score(df)
    assert scores.index.tolist() == ["X", "Y"]


def test_apply_technical_filters_rsi():
    from layers.screener import apply_technical_filters
    df = pd.DataFrame({
        "rsi": [25.0, 50.0, 75.0],
        "above_50sma": [True, True, True],
        "above_200sma": [True, True, True],
    }, index=["A", "B", "C"])
    result = apply_technical_filters(df, {"rsi_min": 30, "rsi_max": 70})
    assert "B" in result.index
    assert "A" not in result.index
    assert "C" not in result.index


def test_run_screener_returns_dataframe_with_required_columns(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test_key")
    tickers = ["AAPL", "MSFT"]
    with patch("layers.screener._fetch_universe_tickers") as mock_univ, \
         patch("layers.screener._fetch_key_metrics_batch") as mock_km, \
         patch("layers.screener._fetch_technical_indicators") as mock_tech:

        mock_univ.return_value = tickers
        mock_km.return_value = pd.DataFrame(_mock_key_metrics(tickers)).set_index("symbol")
        mock_tech.return_value = pd.DataFrame({
            "rsi": [45.0, 55.0],
            "above_50sma": [True, True],
            "above_200sma": [True, False],
        }, index=tickers)

        from layers.screener import run_screener
        result = run_screener("S&P 500", {})

    assert isinstance(result, pd.DataFrame)
    assert "composite_score" in result.columns
    assert "peRatio" in result.columns
    assert "rsi" in result.columns
    assert len(result) == 2


# ── FX + Commodity Screener ───────────────────────────────────────────────────

def _mock_tech_df(tickers):
    return pd.DataFrame({
        "rsi":              [45.0, 55.0, 65.0][:len(tickers)],
        "momentum_12_1":    [0.05, -0.02, 0.08][:len(tickers)],
        "realized_vol_30d": [0.07, 0.09, 0.06][:len(tickers)],
        "last_price":       [1.10, 1.25, 0.65][:len(tickers)],
    }, index=tickers)


def test_run_fx_screener_returns_dataframe():
    tickers = ["EURUSD=X", "GBPUSD=X", "AUDUSD=X"]
    with patch("layers.screener._fetch_asset_technicals",
               return_value=_mock_tech_df(tickers)):
        from layers.screener import run_fx_screener
        result = run_fx_screener("G10 Majors")
    assert isinstance(result, pd.DataFrame)
    assert "momentum_12_1" in result.columns
    assert "rsi" in result.columns
    assert "composite_score" in result.columns


def test_run_fx_screener_sorted_descending():
    tickers = ["EURUSD=X", "GBPUSD=X"]
    with patch("layers.screener._fetch_asset_technicals",
               return_value=_mock_tech_df(tickers)):
        from layers.screener import run_fx_screener
        result = run_fx_screener("G10 Majors")
    scores = result["composite_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_run_fx_screener_unknown_group_returns_empty():
    from layers.screener import run_fx_screener
    result = run_fx_screener("NonexistentGroup")
    assert result.empty


def test_run_commodity_screener_returns_dataframe():
    tickers = ["GC=F", "SI=F", "CL=F"]
    with patch("layers.screener._fetch_asset_technicals",
               return_value=_mock_tech_df(tickers)):
        from layers.screener import run_commodity_screener
        result = run_commodity_screener("Precious Metals")
    assert isinstance(result, pd.DataFrame)
    assert "momentum_12_1" in result.columns


def test_run_commodity_screener_all_groups():
    tickers = ["GC=F", "CL=F"]
    with patch("layers.screener._fetch_asset_technicals",
               return_value=_mock_tech_df(tickers)):
        from layers.screener import run_commodity_screener
        result = run_commodity_screener("all")
    assert not result.empty
