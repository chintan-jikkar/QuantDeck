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


def simulate_garch(prices: pd.Series, n_paths: int = 5000, horizon: int = 252,
                   seed: int | None = None) -> np.ndarray:
    """GARCH(1,1) with Student-t innovations — volatility clustering + fat tails.

    Fits a GARCH(1,1)-t to historical % returns via the `arch` package, then
    simulates forward. Returns (horizon+1, n_paths); row 0 = current price.
    Falls back to GBM bootstrap if the GARCH fit fails to converge.
    """
    from arch import arch_model
    rng = np.random.default_rng(seed)
    rets_pct = prices.dropna().pct_change().dropna().to_numpy(dtype=float) * 100.0
    start = float(prices.dropna().iloc[-1])

    try:
        am = arch_model(rets_pct, vol="GARCH", p=1, q=1, dist="t")
        res = am.fit(disp="off")
        params = res.params
        omega = params["omega"]
        alpha = params["alpha[1]"]
        beta  = params["beta[1]"]
        nu    = params["nu"]
        mu    = params["mu"]
        last_resid = res.resid[-1]
        last_var   = res.conditional_volatility[-1] ** 2
    except Exception:
        return simulate_gbm(prices, n_paths=n_paths, horizon=horizon, seed=seed)

    t_scale = np.sqrt(nu / (nu - 2)) if nu > 2 else 1.0
    log_paths = np.zeros((horizon + 1, n_paths))
    var_t = np.full(n_paths, last_var)
    resid_t = np.full(n_paths, last_resid)
    for t in range(1, horizon + 1):
        var_t = omega + alpha * resid_t ** 2 + beta * var_t
        z = rng.standard_t(nu, size=n_paths) / t_scale
        resid_t = np.sqrt(var_t) * z
        ret_pct = mu + resid_t
        log_paths[t, :] = log_paths[t - 1, :] + np.log1p(ret_pct / 100.0)
    return start * np.exp(log_paths)


def compute_risk_metrics(paths: np.ndarray, start_price: float) -> dict:
    """Risk metrics from a simulated path matrix (rows=time, cols=paths)."""
    terminal = paths[-1, :]
    returns = terminal / start_price - 1.0
    var_95 = float(np.percentile(returns, 5))
    cvar_95 = float(returns[returns <= var_95].mean()) if (returns <= var_95).any() else var_95
    return {
        "var_95": var_95,
        "cvar_95": cvar_95,
        "prob_profit": float((terminal > start_price).mean()),
        "expected_return": float(np.median(returns)),
        "p50_price": float(np.median(terminal)),
        "mean_price": float(np.mean(terminal)),
    }


def compute_percentile_bands(paths: np.ndarray,
                             percentiles: list[int] | None = None) -> pd.DataFrame:
    """Per-timestep percentile bands across all paths. Columns: p{n}."""
    percentiles = percentiles or [10, 25, 50, 75, 90]
    data = {f"p{p}": np.percentile(paths, p, axis=1) for p in percentiles}
    return pd.DataFrame(data)


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
