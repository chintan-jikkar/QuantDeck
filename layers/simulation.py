# layers/simulation.py — no Streamlit imports
import pandas as pd


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
