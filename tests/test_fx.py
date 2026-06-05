# tests/test_fx.py
from unittest.mock import patch
import pandas as pd
import pytest


def _make_fx_df(rate: float = 1.085) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    return pd.DataFrame({"Close": [rate] * 5}, index=dates)


def test_currency_to_usd_same_currency():
    from data.fx import currency_to_usd
    assert currency_to_usd(100.0, "USD") == 100.0


@patch("data.fx.yf.download")
def test_get_fx_rate_returns_latest_close(mock_dl):
    mock_dl.return_value = _make_fx_df(1.085)
    from data.fx import get_fx_rate
    rate = get_fx_rate("EUR", "USD")
    assert isinstance(rate, float)
    assert rate == pytest.approx(1.085, rel=1e-4)


@patch("data.fx.yf.download")
def test_get_fx_rate_uses_correct_ticker(mock_dl):
    mock_dl.return_value = _make_fx_df(1.085)
    from data.fx import get_fx_rate
    get_fx_rate("EUR", "USD")
    call_args = mock_dl.call_args
    assert call_args[0][0] == "EURUSD=X"


@patch("data.fx.yf.download")
def test_currency_to_usd_converts(mock_dl):
    mock_dl.return_value = _make_fx_df(1.085)
    from data.fx import currency_to_usd
    result = currency_to_usd(100.0, "EUR")
    assert result == pytest.approx(108.5, rel=1e-3)


@patch("data.fx.yf.download")
def test_get_fx_rate_raises_on_empty_data(mock_dl):
    mock_dl.return_value = pd.DataFrame()
    from data.fx import get_fx_rate
    with pytest.raises(ValueError, match="Could not fetch FX rate"):
        get_fx_rate("EUR", "USD")
