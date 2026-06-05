# tests/test_backtester.py
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def trend_prices():
    dates = pd.date_range("2022-01-01", periods=100, freq="B")
    return pd.Series(np.linspace(100, 150, 100), index=dates)


def test_run_engine_equity_curve_rises_when_long_in_uptrend(trend_prices):
    from layers.backtester import run_engine
    signals = pd.Series(1, index=trend_prices.index)
    result = run_engine(trend_prices, signals, initial_capital=10_000,
                        commission_bps=0, slippage_pct=0)
    eq = result["equity_curve"]
    assert eq.iloc[-1] > eq.iloc[0]


def test_run_engine_flat_signal_holds_capital(trend_prices):
    from layers.backtester import run_engine
    signals = pd.Series(0, index=trend_prices.index)
    result = run_engine(trend_prices, signals, initial_capital=10_000,
                        commission_bps=0, slippage_pct=0)
    eq = result["equity_curve"]
    assert np.isclose(eq.iloc[-1], 10_000, rtol=1e-6)


def test_run_engine_uses_lagged_signal_no_lookahead(trend_prices):
    from layers.backtester import run_engine
    signals = pd.Series(0, index=trend_prices.index)
    signals.iloc[-1] = 1
    result = run_engine(trend_prices, signals, initial_capital=10_000,
                        commission_bps=0, slippage_pct=0)
    assert np.isclose(result["equity_curve"].iloc[-1], 10_000, rtol=1e-6)


def test_run_engine_commission_reduces_return(trend_prices):
    from layers.backtester import run_engine
    signals = pd.Series(1, index=trend_prices.index)
    no_cost = run_engine(trend_prices, signals, initial_capital=10_000,
                         commission_bps=0, slippage_pct=0)["equity_curve"].iloc[-1]
    with_cost = run_engine(trend_prices, signals, initial_capital=10_000,
                           commission_bps=50, slippage_pct=0.001)["equity_curve"].iloc[-1]
    assert with_cost < no_cost


def test_run_engine_short_profits_in_downtrend():
    from layers.backtester import run_engine
    dates = pd.date_range("2022-01-01", periods=100, freq="B")
    prices = pd.Series(np.linspace(150, 100, 100), index=dates)
    signals = pd.Series(-1, index=dates)
    result = run_engine(prices, signals, initial_capital=10_000,
                        commission_bps=0, slippage_pct=0)
    assert result["equity_curve"].iloc[-1] > 10_000


def test_run_engine_returns_trades_dataframe(trend_prices):
    from layers.backtester import run_engine
    signals = pd.Series([0]*50 + [1]*50, index=trend_prices.index)
    result = run_engine(trend_prices, signals, initial_capital=10_000)
    assert "trades" in result
    assert isinstance(result["trades"], pd.DataFrame)
