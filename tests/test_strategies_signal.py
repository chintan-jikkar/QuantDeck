# tests/test_strategies_signal.py
import numpy as np
import pandas as pd
import pytest


def _prices_df(values):
    dates = pd.date_range("2022-01-01", periods=len(values), freq="B")
    return pd.DataFrame({"Close": values}, index=dates)


def test_ma_crossover_golden_cross_goes_long():
    from strategies.signal.ma_crossover import MACrossover
    df = _prices_df(np.linspace(100, 200, 300))
    signals = MACrossover().generate_signals(df, fast=10, slow=50)
    assert signals.iloc[-1] == 1


def test_ma_crossover_death_cross_goes_short():
    from strategies.signal.ma_crossover import MACrossover
    df = _prices_df(np.linspace(200, 100, 300))
    signals = MACrossover().generate_signals(df, fast=10, slow=50)
    assert signals.iloc[-1] == -1


def test_ma_crossover_signals_index_matches():
    from strategies.signal.ma_crossover import MACrossover
    df = _prices_df(np.linspace(100, 200, 300))
    signals = MACrossover().generate_signals(df)
    assert signals.index.equals(df.index)


def test_rsi_mean_reversion_buys_oversold():
    from strategies.signal.rsi_mean_reversion import RSIMeanReversion
    df = _prices_df(np.concatenate([np.full(40, 100.0), np.linspace(100, 70, 40)]))
    signals = RSIMeanReversion().generate_signals(df, period=14, oversold=30, overbought=70)
    assert signals.iloc[-1] == 1


def test_rsi_mean_reversion_sells_overbought():
    from strategies.signal.rsi_mean_reversion import RSIMeanReversion
    df = _prices_df(np.concatenate([np.full(40, 100.0), np.linspace(100, 140, 40)]))
    signals = RSIMeanReversion().generate_signals(df, period=14, oversold=30, overbought=70)
    assert signals.iloc[-1] == -1


def test_momentum_positive_trend_goes_long():
    from strategies.signal.momentum import Momentum
    df = _prices_df(np.linspace(100, 200, 300))
    signals = Momentum().generate_signals(df, lookback=252, skip=21)
    assert signals.iloc[-1] == 1


def test_momentum_negative_trend_goes_short():
    from strategies.signal.momentum import Momentum
    df = _prices_df(np.linspace(200, 100, 300))
    signals = Momentum().generate_signals(df, lookback=252, skip=21)
    assert signals.iloc[-1] == -1


def test_strategy_get_positions_matches_signals_index():
    from strategies.signal.ma_crossover import MACrossover
    df = _prices_df(np.linspace(100, 200, 300))
    s = MACrossover()
    sig = s.generate_signals(df)
    pos = s.get_positions(sig, df)
    assert pos.index.equals(sig.index)
    assert (pos.abs() <= 1.0).all()


def test_strategy_describe_has_metadata():
    from strategies.signal.ma_crossover import MACrossover
    d = MACrossover().describe()
    assert d["name"] and d["asset_classes"] and d["tier"]
