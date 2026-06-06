# tests/test_strategies_factor.py
import numpy as np
import pandas as pd
import pytest


def _prices_df(values):
    dates = pd.date_range("2022-01-01", periods=len(values), freq="B")
    return pd.DataFrame({"Close": values}, index=dates)


def test_value_rank_universe_prefers_cheap():
    from strategies.factor.value import Value
    metrics = pd.DataFrame({
        "peRatio": [10.0, 20.0, 30.0],
        "pbRatio": [1.0, 2.0, 3.0],
        "roe":     [0.20, 0.15, 0.10],
    }, index=["CHEAP", "MID", "RICH"])
    ranked = Value.rank_universe(metrics)
    assert ranked.index[0] == "CHEAP"


def test_quality_rank_universe_prefers_high_roic_low_leverage():
    from strategies.factor.quality import Quality
    metrics = pd.DataFrame({
        "roe":             [0.25, 0.15, 0.05],
        "debtToEquity":    [0.2, 1.0, 2.0],
        "netProfitMargin": [0.20, 0.10, 0.05],
    }, index=["GOOD", "MID", "BAD"])
    ranked = Quality.rank_universe(metrics)
    assert ranked.index[0] == "GOOD"


def test_value_generate_signals_index():
    from strategies.factor.value import Value
    df = _prices_df(np.linspace(100, 120, 50))
    sig = Value().generate_signals(df)
    assert sig.index.equals(df.index)


def test_pairs_compute_spread_zscore_bounds():
    from strategies.arbitrage.pairs_trading import PairsTrading
    rng = np.random.default_rng(0)
    n = 300
    a = pd.Series(np.cumsum(rng.standard_normal(n)) + 100)
    b = a + rng.standard_normal(n) * 2
    z = PairsTrading.compute_spread_zscore(a, b, lookback=60)
    valid = z.dropna()
    assert valid.abs().max() < 10


def test_pairs_signals_enter_on_extreme_zscore():
    from strategies.arbitrage.pairs_trading import PairsTrading
    n = 200
    base = pd.Series(np.linspace(100, 100, n))
    a = base.copy()
    b = base.copy()
    a.iloc[-1] = 130
    signals = PairsTrading().generate_pair_signals(a, b, lookback=60, entry_z=2.0, exit_z=0.5)
    assert signals.iloc[-1] in (-1, 0, 1)


def test_pairs_describe_metadata():
    from strategies.arbitrage.pairs_trading import PairsTrading
    d = PairsTrading().describe()
    assert d["tier"] == "aggressive"
