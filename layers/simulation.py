# layers/simulation.py — no Streamlit imports
import numpy as np
import pandas as pd


def _log_returns(prices: pd.Series) -> np.ndarray:
    p = prices.dropna().to_numpy(dtype=float)
    return np.diff(np.log(p))


def simulate_gbm(prices: pd.Series, n_paths: int = 5000, horizon: int = 252,
                 seed: int | None = None) -> np.ndarray:
    """Bootstrap GBM: resample historical log-returns with replacement.

    Captures real skew/fat-tails without assuming normality. Returns a
    (horizon+1, n_paths) array; row 0 is the current price for every path.
    """
    rng = np.random.default_rng(seed)
    rets = _log_returns(prices)
    if len(rets) == 0:
        raise ValueError("Not enough price history to simulate")
    start = float(prices.dropna().iloc[-1])
    sampled = rng.choice(rets, size=(horizon, n_paths), replace=True)
    log_paths = np.vstack([np.zeros((1, n_paths)), np.cumsum(sampled, axis=0)])
    return start * np.exp(log_paths)


def calibrate_ou(prices: pd.Series) -> dict:
    """Calibrate Ornstein-Uhlenbeck via AR(1) regression on the level series.

    Discrete model: x_t = x_{t-1} + theta*(mu - x_{t-1}) + sigma*eps.
    AR(1) form: x_t = a + b*x_{t-1} + eps, with b = 1 - theta, mu = a/theta,
    sigma = std(residuals).
    """
    x = prices.dropna().to_numpy(dtype=float)
    x_prev, x_next = x[:-1], x[1:]
    b, a = np.polyfit(x_prev, x_next, 1)
    theta = 1.0 - b
    if theta <= 1e-6:
        theta = 1e-6
    mu = a / theta
    resid = x_next - (a + b * x_prev)
    sigma = float(np.std(resid, ddof=1))
    return {"theta": float(theta), "mu": float(mu), "sigma": sigma}


def simulate_ou(prices: pd.Series, n_paths: int = 5000, horizon: int = 252,
                seed: int | None = None) -> np.ndarray:
    """Simulate Ornstein-Uhlenbeck mean-reverting paths on the price level.

    Returns (horizon+1, n_paths); row 0 = current price. Suited to commodities.
    """
    rng = np.random.default_rng(seed)
    params = calibrate_ou(prices)
    theta, mu, sigma = params["theta"], params["mu"], params["sigma"]
    start = float(prices.dropna().iloc[-1])

    paths = np.empty((horizon + 1, n_paths))
    paths[0, :] = start
    for t in range(1, horizon + 1):
        prev = paths[t - 1, :]
        shock = sigma * rng.standard_normal(n_paths)
        paths[t, :] = prev + theta * (mu - prev) + shock
    return paths


def run_simulation(
    ticker: str,
    model: str = "gbm",
    n_paths: int = 5000,
    horizon_days: int = 252,
) -> dict:
    """Run Monte Carlo simulation and return path matrix + risk metrics.

    Implemented in Phase 3.
    """
    raise NotImplementedError("Simulation layer is implemented in Phase 3")
