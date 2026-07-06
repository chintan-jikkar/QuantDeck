# tests/test_macro.py
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
from data import macro as mac


def _make_fred_df(series_id: str, values: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(values), freq="ME")
    return pd.DataFrame({series_id: values}, index=dates)


@patch("data.macro.web.DataReader")
def test_fetch_fred_series_returns_series(mock_dr):
    mock_dr.return_value = _make_fred_df("DGS10", [4.1, 4.2, 4.3])
    from data.macro import fetch_fred_series
    s = fetch_fred_series("DGS10")
    assert isinstance(s, pd.Series)
    assert len(s) == 3


@patch("data.macro.web.DataReader")
def test_fetch_yield_curve_returns_series_with_maturities(mock_dr):
    mac._CACHE.clear()
    mock_dr.return_value = _make_fred_df("ANY", [4.5])
    from data.macro import fetch_yield_curve
    curve = fetch_yield_curve("US")
    assert isinstance(curve, pd.Series)
    assert set(curve.index) == {"3M", "2Y", "5Y", "10Y", "30Y"}


@patch("data.macro.web.DataReader")
def test_fetch_macro_regime_returns_required_keys(mock_dr):
    mac._CACHE.clear()
    def side_effect(series_id, *args, **kwargs):
        values_map = {
            "DTB3":         [5.3],
            "DGS10":        [4.2],
            "BAMLC0A0CM":   [1.2],
            "FEDFUNDS":     [5.25],
            "CPIAUCSL":     [310.0, 314.0],
        }
        return _make_fred_df(series_id, values_map.get(series_id, [4.0]))
    mock_dr.side_effect = side_effect
    from data.macro import fetch_macro_regime
    regime = fetch_macro_regime("US")
    assert "yield_curve_shape" in regime
    assert "credit_spread_level" in regime
    assert "policy_rate" in regime
    assert "inflation_yoy" in regime


@patch("data.macro.web.DataReader")
def test_fetch_macro_regime_inverted_yield_curve(mock_dr):
    mac._CACHE.clear()
    # 3M (5.3%) > 10Y (4.2%) → inverted
    def side_effect(series_id, *args, **kwargs):
        values_map = {
            "DTB3":       [5.3],
            "DGS10":      [4.2],
            "BAMLC0A0CM": [1.2],
            "FEDFUNDS":   [5.25],
            "CPIAUCSL":   [310.0, 314.0],
        }
        return _make_fred_df(series_id, values_map.get(series_id, [4.0]))
    mock_dr.side_effect = side_effect
    from data.macro import fetch_macro_regime
    regime = fetch_macro_regime("US")
    assert regime["yield_curve_shape"] == "inverted"


@patch("data.macro.web.DataReader")
def test_fetch_macro_regime_normal_yield_curve(mock_dr):
    mac._CACHE.clear()
    # 3M (4.2%) < 10Y (5.3%) → normal
    def side_effect(series_id, *args, **kwargs):
        values_map = {
            "DTB3":       [4.2],
            "DGS10":      [5.3],
            "BAMLC0A0CM": [1.2],
            "FEDFUNDS":   [5.25],
            "CPIAUCSL":   [310.0, 314.0],
        }
        return _make_fred_df(series_id, values_map.get(series_id, [4.0]))
    mock_dr.side_effect = side_effect
    from data.macro import fetch_macro_regime
    regime = fetch_macro_regime("US")
    assert regime["yield_curve_shape"] == "normal"


@patch("data.macro.web.DataReader")
def test_fetch_macro_regime_cpi_yoy_computed_over_12_months(mock_dr):
    mac._CACHE.clear()
    # 13 monthly CPI points: index -13 = 300.0, index -1 = 309.0 → YoY = +3.0%.
    # The intermediate months are filled so iloc[-13] and iloc[-1] are the load-bearing values.
    cpi_series = [300.0, 301.0, 302.0, 303.0, 304.0, 305.0, 306.0,
                  306.5, 307.0, 307.5, 308.0, 308.5, 309.0]
    assert len(cpi_series) == 13

    def side_effect(series_id, *args, **kwargs):
        values_map = {
            "DTB3":       [4.2],
            "DGS10":      [5.3],
            "BAMLC0A0CM": [1.2],
            "FEDFUNDS":   [5.25],
            "CPIAUCSL":   cpi_series,
        }
        return _make_fred_df(series_id, values_map.get(series_id, [4.0]))
    mock_dr.side_effect = side_effect
    from data.macro import fetch_macro_regime
    regime = fetch_macro_regime("US")
    # (309.0 / 300.0 - 1) * 100 == 3.0
    assert regime["inflation_yoy"] == pytest.approx(3.0, abs=1e-6)
