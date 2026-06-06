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


def test_garch_paths_shape(price_series):
    from layers.simulation import simulate_garch
    paths = simulate_garch(price_series, n_paths=100, horizon=20, seed=1)
    assert paths.shape == (21, 100)


def test_garch_paths_start_at_current_price(price_series):
    from layers.simulation import simulate_garch
    paths = simulate_garch(price_series, n_paths=50, horizon=10, seed=1)
    assert np.allclose(paths[0, :], float(price_series.iloc[-1]))


def test_garch_paths_positive(price_series):
    from layers.simulation import simulate_garch
    paths = simulate_garch(price_series, n_paths=50, horizon=10, seed=1)
    assert (paths > 0).all()


def test_compute_risk_metrics_keys():
    from layers.simulation import compute_risk_metrics
    rng = np.random.default_rng(0)
    paths = 100 * np.exp(np.cumsum(rng.standard_normal((30, 1000)) * 0.01, axis=0))
    paths = np.vstack([np.full((1, 1000), 100.0), paths])
    m = compute_risk_metrics(paths, start_price=100.0)
    for k in ["var_95", "cvar_95", "prob_profit", "expected_return", "p50_price"]:
        assert k in m


def test_var_cvar_ordering():
    from layers.simulation import compute_risk_metrics
    rng = np.random.default_rng(2)
    term = 100 * np.exp(rng.standard_normal((1, 5000)) * 0.2)
    paths = np.vstack([np.full((1, 5000), 100.0), term])
    m = compute_risk_metrics(paths, start_price=100.0)
    assert m["cvar_95"] <= m["var_95"]


def test_prob_profit_bounds():
    from layers.simulation import compute_risk_metrics
    rng = np.random.default_rng(5)
    paths = 100 * np.exp(np.cumsum(rng.standard_normal((30, 1000)) * 0.01, axis=0))
    paths = np.vstack([np.full((1, 1000), 100.0), paths])
    m = compute_risk_metrics(paths, start_price=100.0)
    assert 0.0 <= m["prob_profit"] <= 1.0


def test_percentile_bands_shape():
    from layers.simulation import compute_percentile_bands
    rng = np.random.default_rng(0)
    paths = 100 * np.exp(np.cumsum(rng.standard_normal((30, 500)) * 0.01, axis=0))
    paths = np.vstack([np.full((1, 500), 100.0), paths])
    bands = compute_percentile_bands(paths, percentiles=[10, 25, 50, 75, 90])
    assert bands.shape == (31, 5)
    assert bands.iloc[-1]["p10"] <= bands.iloc[-1]["p50"] <= bands.iloc[-1]["p90"]
