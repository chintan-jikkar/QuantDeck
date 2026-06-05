# layers/backtester.py — no Streamlit imports
import pandas as pd


def run_backtest(
    strategy_name: str,
    universe: str,
    start: str,
    end: str,
    params: dict | None = None,
) -> dict:
    """Run a named strategy over history and return a tearsheet dict.

    Implemented in Phase 3.
    """
    raise NotImplementedError("Backtester layer is implemented in Phase 3")
