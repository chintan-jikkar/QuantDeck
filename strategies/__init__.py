# strategies/__init__.py
from strategies.signal.ma_crossover import MACrossover
from strategies.signal.rsi_mean_reversion import RSIMeanReversion
from strategies.signal.momentum import Momentum
from strategies.factor.value import Value
from strategies.factor.quality import Quality
from strategies.arbitrage.pairs_trading import PairsTrading

STRATEGY_REGISTRY = {
    "MA Crossover":             MACrossover,
    "RSI Mean Reversion":       RSIMeanReversion,
    "12-1 Momentum":            Momentum,
    "Value (Graham/Buffett)":   Value,
    "Quality Factor":           Quality,
    "Pairs Trading (Stat Arb)": PairsTrading,
}


def get_strategy(name: str):
    """Return an instantiated strategy by display name."""
    cls = STRATEGY_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"Unknown strategy {name!r}. Options: {list(STRATEGY_REGISTRY)}")
    return cls()


def list_strategies() -> list[dict]:
    """Return describe() dicts for every registered strategy."""
    return [cls().describe() for cls in STRATEGY_REGISTRY.values()]
