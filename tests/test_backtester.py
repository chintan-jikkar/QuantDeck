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


def test_cagr_simple():
    from layers.backtester import compute_cagr
    eq = pd.Series(np.linspace(100, 200, 253))
    cagr = compute_cagr(eq, periods_per_year=252)
    assert cagr == pytest.approx(1.0, rel=0.05)


def test_sharpe_zero_for_constant_returns():
    from layers.backtester import compute_sharpe
    rets = pd.Series([0.0] * 100)
    assert compute_sharpe(rets) == 0.0


def test_sharpe_positive_for_positive_drift():
    from layers.backtester import compute_sharpe
    rng = np.random.default_rng(0)
    rets = pd.Series(rng.standard_normal(1000) * 0.01 + 0.001)
    assert compute_sharpe(rets) > 0


def test_max_drawdown_simple():
    from layers.backtester import compute_max_drawdown
    eq = pd.Series([100, 120, 90, 110])
    assert compute_max_drawdown(eq) == pytest.approx(-0.25, rel=1e-4)


def test_max_drawdown_monotonic_is_zero():
    from layers.backtester import compute_max_drawdown
    eq = pd.Series([100, 110, 120, 130])
    assert compute_max_drawdown(eq) == pytest.approx(0.0, abs=1e-9)


def test_compute_tearsheet_keys():
    from layers.backtester import compute_tearsheet
    rng = np.random.default_rng(1)
    rets = pd.Series(rng.standard_normal(500) * 0.01 + 0.0005)
    eq = (1 + rets).cumprod() * 10_000
    ts = compute_tearsheet(eq, rets)
    for k in ["cagr", "sharpe", "sortino", "max_drawdown", "win_rate",
              "profit_factor", "calmar", "total_return"]:
        assert k in ts


def test_win_rate_bounds():
    from layers.backtester import compute_tearsheet
    rng = np.random.default_rng(3)
    rets = pd.Series(rng.standard_normal(300) * 0.01)
    eq = (1 + rets).cumprod() * 10_000
    ts = compute_tearsheet(eq, rets)
    assert 0.0 <= ts["win_rate"] <= 1.0


# ── Benchmark auto-selection ──────────────────────────────────────────────────

def _make_prices_df(n=200):
    dates = pd.date_range("2021-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Close": np.linspace(100, 150, n),
        "Open": 100.0, "High": 101.0, "Low": 99.0, "Volume": 1e6,
    }, index=dates)


def test_run_backtest_result_has_benchmark_curve():
    from unittest.mock import patch
    with patch("layers.backtester.fetch_prices", return_value=_make_prices_df()):
        from layers.backtester import run_backtest
        result = run_backtest("MA Crossover", "AAPL", "2021-01-01", "2022-01-01")
    assert "benchmark_curve" in result
    assert "benchmark_ticker" in result


def test_run_backtest_benchmark_curve_is_series_or_none():
    from unittest.mock import patch
    with patch("layers.backtester.fetch_prices", return_value=_make_prices_df()):
        from layers.backtester import run_backtest
        result = run_backtest("MA Crossover", "AAPL", "2021-01-01", "2022-01-01")
    bc = result["benchmark_curve"]
    assert bc is None or isinstance(bc, pd.Series)


def test_run_backtest_benchmark_ticker_is_spy_for_us_equity():
    from unittest.mock import patch
    with patch("layers.backtester.fetch_prices", return_value=_make_prices_df()):
        from layers.backtester import run_backtest
        result = run_backtest("MA Crossover", "AAPL", "2021-01-01", "2022-01-01")
    assert result["benchmark_ticker"] == "SPY"
