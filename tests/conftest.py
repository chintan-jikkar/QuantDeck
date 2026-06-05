import pandas as pd
import numpy as np
import pytest


@pytest.fixture
def sample_prices():
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=252, freq="B")
    close = 100 * (1 + rng.standard_normal(252) * 0.01).cumprod()
    return pd.DataFrame(
        {
            "Open": close * 0.99,
            "High": close * 1.01,
            "Low": close * 0.98,
            "Close": close,
            "Volume": rng.integers(1_000_000, 10_000_000, 252).astype(float),
        },
        index=dates,
    )


@pytest.fixture
def sample_income_statement():
    return [
        {
            "date": "2023-12-31",
            "revenue": 100_000_000,
            "grossProfit": 40_000_000,
            "operatingIncome": 20_000_000,
            "netIncome": 15_000_000,
            "eps": 1.50,
        },
        {
            "date": "2022-12-31",
            "revenue": 90_000_000,
            "grossProfit": 35_000_000,
            "operatingIncome": 17_000_000,
            "netIncome": 12_000_000,
            "eps": 1.20,
        },
    ]
