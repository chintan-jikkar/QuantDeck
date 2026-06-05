# tests/test_strategies_base.py
import pandas as pd
import pytest
from strategies.base import Strategy


class _ConcreteStrategy(Strategy):
    """Minimal concrete subclass used only in tests."""
    name = "Test Strategy"
    description = "Always long."
    asset_classes = ["equity"]
    tier = "moderate"

    def generate_signals(self, prices: pd.DataFrame, **params) -> pd.Series:
        return pd.Series(1, index=prices.index, dtype=int)

    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        return signals.astype(float)


def test_strategy_abstract_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Strategy()


def test_concrete_strategy_instantiates():
    s = _ConcreteStrategy()
    assert s.name == "Test Strategy"


def test_generate_signals_returns_series_with_matching_index(sample_prices):
    s = _ConcreteStrategy()
    signals = s.generate_signals(sample_prices)
    assert isinstance(signals, pd.Series)
    assert signals.index.equals(sample_prices.index)


def test_generate_signals_values_are_long(sample_prices):
    s = _ConcreteStrategy()
    signals = s.generate_signals(sample_prices)
    assert (signals == 1).all()


def test_get_positions_returns_series(sample_prices):
    s = _ConcreteStrategy()
    signals = s.generate_signals(sample_prices)
    positions = s.get_positions(signals, sample_prices)
    assert isinstance(positions, pd.Series)
    assert positions.index.equals(signals.index)


def test_describe_returns_all_keys():
    s = _ConcreteStrategy()
    d = s.describe()
    assert set(d.keys()) == {"name", "description", "asset_classes", "tier"}


def test_describe_values():
    s = _ConcreteStrategy()
    d = s.describe()
    assert d["name"] == "Test Strategy"
    assert d["asset_classes"] == ["equity"]
    assert d["tier"] == "moderate"
