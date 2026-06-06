# tests/test_prices.py
from unittest.mock import patch
import pandas as pd
import numpy as np
import pytest


def _make_yf_df(n: int = 252) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 * (1 + rng.standard_normal(n) * 0.01).cumprod()
    return pd.DataFrame(
        {
            "Open":   close * 0.99,
            "High":   close * 1.01,
            "Low":    close * 0.98,
            "Close":  close,
            "Volume": rng.integers(1_000_000, 10_000_000, n).astype(float),
        },
        index=dates,
    )


@patch("data.prices.yf.download")
def test_fetch_prices_returns_dataframe(mock_dl):
    mock_dl.return_value = _make_yf_df()
    from data.prices import fetch_prices
    df = fetch_prices("AAPL")
    assert not df.empty
    assert {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns)


@patch("data.prices.yf.download")
def test_fetch_prices_raises_on_empty(mock_dl):
    mock_dl.return_value = pd.DataFrame()
    from data.prices import fetch_prices
    with pytest.raises(ValueError, match="No price data"):
        fetch_prices("INVALID")


@patch("data.prices.yf.download")
def test_fetch_prices_flattens_multiindex_columns(mock_dl):
    df = _make_yf_df()
    df.columns = pd.MultiIndex.from_tuples([(c, "AAPL") for c in df.columns])
    mock_dl.return_value = df
    from data.prices import fetch_prices
    result = fetch_prices("AAPL")
    assert not isinstance(result.columns, pd.MultiIndex)
    assert "Close" in result.columns


@patch("data.prices.yf.download")
def test_fetch_intraday_passes_5m_interval(mock_dl):
    mock_dl.return_value = _make_yf_df(78)  # ~78 5-min bars in a trading day
    from data.prices import fetch_intraday
    fetch_intraday("AAPL")
    _, kwargs = mock_dl.call_args
    assert kwargs.get("interval") == "5m" or mock_dl.call_args[0][1] == "5m"


def test_compute_returns_length(sample_prices):
    from data.prices import compute_returns
    returns = compute_returns(sample_prices)
    assert len(returns) == len(sample_prices) - 1


def test_compute_returns_index_aligned(sample_prices):
    from data.prices import compute_returns
    returns = compute_returns(sample_prices)
    assert returns.index.equals(sample_prices.index[1:])


def test_compute_rsi_bounds(sample_prices):
    from data.prices import compute_rsi
    rsi = compute_rsi(sample_prices["Close"])
    valid = rsi.dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_compute_rsi_first_n_are_nan(sample_prices):
    from data.prices import compute_rsi
    rsi = compute_rsi(sample_prices["Close"], period=14)
    # EWM with min_periods=period produces NaN until period bars have accumulated
    assert rsi.iloc[:13].isna().all()
    assert not rsi.iloc[14:].isna().any()


def test_compute_rolling_beta_self_is_one(sample_prices):
    from data.prices import compute_returns, compute_rolling_beta
    ret = compute_returns(sample_prices)
    beta = compute_rolling_beta(ret, ret, window=60)
    valid = beta.dropna()
    assert len(valid) > 0
    assert abs(valid.iloc[-1] - 1.0) < 0.001


# ── Asset-type detection ───────────────────────────────────────────────────────

def test_detect_asset_type_fx():
    from data.prices import detect_asset_type
    assert detect_asset_type("EURUSD=X") == "fx"
    assert detect_asset_type("USDINR=X") == "fx"


def test_detect_asset_type_commodity():
    from data.prices import detect_asset_type
    assert detect_asset_type("GC=F") == "commodity"
    assert detect_asset_type("CL=F") == "commodity"


def test_detect_asset_type_equity_us():
    from data.prices import detect_asset_type
    assert detect_asset_type("AAPL") == "equity"
    assert detect_asset_type("MSFT") == "equity"


def test_detect_asset_type_equity_intl():
    from data.prices import detect_asset_type
    assert detect_asset_type("BP.L") == "equity"
    assert detect_asset_type("SIE.DE") == "equity"


def test_detect_asset_type_case_insensitive():
    from data.prices import detect_asset_type
    assert detect_asset_type("eurusd=x") == "fx"
    assert detect_asset_type("gc=f") == "commodity"


def test_get_benchmark_fx_returns_uup():
    from data.prices import get_benchmark
    assert get_benchmark("EURUSD=X") == "UUP"


def test_get_benchmark_commodity_returns_djp():
    from data.prices import get_benchmark
    assert get_benchmark("GC=F") == "DJP"


def test_get_benchmark_us_equity_returns_spy():
    from data.prices import get_benchmark
    assert get_benchmark("AAPL") == "SPY"


def test_get_benchmark_uk_equity_returns_ewu():
    from data.prices import get_benchmark
    assert get_benchmark("BP.L") == "EWU"


def test_get_benchmark_japan_equity_returns_ewj():
    from data.prices import get_benchmark
    assert get_benchmark("7203.T") == "EWJ"


def test_get_benchmark_unknown_intl_suffix_returns_spy():
    from data.prices import get_benchmark
    assert get_benchmark("LOGN.S") == "SPY"


# ── Country helpers ────────────────────────────────────────────────────────────

def test_country_from_ticker_us_default():
    from data.prices import country_from_ticker
    assert country_from_ticker("AAPL") == "US"
    assert country_from_ticker("MSFT") == "US"


def test_country_from_ticker_uk():
    from data.prices import country_from_ticker
    assert country_from_ticker("BP.L") == "UK"


def test_country_from_ticker_germany():
    from data.prices import country_from_ticker
    assert country_from_ticker("SIE.DE") == "Germany"


def test_country_from_ticker_japan():
    from data.prices import country_from_ticker
    assert country_from_ticker("7203.T") == "Japan"


def test_country_from_ticker_india_nse():
    from data.prices import country_from_ticker
    assert country_from_ticker("RELIANCE.NS") == "India"


def test_country_from_ticker_australia():
    from data.prices import country_from_ticker
    assert country_from_ticker("CBA.AX") == "Australia"


def test_market_index_for_country_us():
    from data.prices import market_index_for_country
    assert market_index_for_country("US") == "^GSPC"


def test_market_index_for_country_uk():
    from data.prices import market_index_for_country
    assert market_index_for_country("UK") == "^FTSE"


def test_market_index_for_country_germany():
    from data.prices import market_index_for_country
    assert market_index_for_country("Germany") == "^GDAXI"


def test_market_index_for_country_unknown_defaults_gspc():
    from data.prices import market_index_for_country
    assert market_index_for_country("Narnia") == "^GSPC"
