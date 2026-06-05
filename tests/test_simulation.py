# tests/test_simulation.py
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def price_series():
    rng = np.random.default_rng(7)
    n = 500
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    rets = rng.standard_normal(n) * 0.01 + 0.0003
    close = 100 * np.exp(np.cumsum(rets))
    return pd.Series(close, index=dates)


def test_gbm_paths_shape(price_series):
    from layers.simulation import simulate_gbm
    paths = simulate_gbm(price_series, n_paths=200, horizon=30, seed=1)
    assert paths.shape == (31, 200)


def test_gbm_paths_start_at_current_price(price_series):
    from layers.simulation import simulate_gbm
    paths = simulate_gbm(price_series, n_paths=100, horizon=20, seed=1)
    start = float(price_series.iloc[-1])
    assert np.allclose(paths[0, :], start)


def test_gbm_paths_positive(price_series):
    from layers.simulation import simulate_gbm
    paths = simulate_gbm(price_series, n_paths=100, horizon=20, seed=1)
    assert (paths > 0).all()


def test_gbm_deterministic_with_seed(price_series):
    from layers.simulation import simulate_gbm
    p1 = simulate_gbm(price_series, n_paths=50, horizon=10, seed=42)
    p2 = simulate_gbm(price_series, n_paths=50, horizon=10, seed=42)
    assert np.allclose(p1, p2)


def test_ou_paths_shape(price_series):
    from layers.simulation import simulate_ou
    paths = simulate_ou(price_series, n_paths=200, horizon=30, seed=1)
    assert paths.shape == (31, 200)


def test_ou_paths_start_at_current_price(price_series):
    from layers.simulation import simulate_ou
    paths = simulate_ou(price_series, n_paths=100, horizon=20, seed=1)
    start = float(price_series.iloc[-1])
    assert np.allclose(paths[0, :], start)


def test_ou_mean_reversion_pulls_toward_long_run_mean():
    rng = np.random.default_rng(0)
    n = 400
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    base = 100 + 10 * np.sin(np.linspace(0, 12 * np.pi, n))
    base[-1] = 80.0
    series = pd.Series(base, index=dates)
    from layers.simulation import simulate_ou
    paths = simulate_ou(series, n_paths=500, horizon=40, seed=3)
    terminal_mean = paths[-1, :].mean()
    assert terminal_mean > 80.0


def test_calibrate_ou_recovers_parameters():
    from layers.simulation import calibrate_ou
    rng = np.random.default_rng(1)
    n = 1000
    mu_true = 50.0
    x = np.zeros(n)
    x[0] = mu_true
    theta, sigma = 0.05, 1.0
    for t in range(1, n):
        x[t] = x[t-1] + theta * (mu_true - x[t-1]) + sigma * rng.standard_normal()
    series = pd.Series(x)
    params = calibrate_ou(series)
    assert params["theta"] > 0
    assert abs(params["mu"] - mu_true) < 5.0
