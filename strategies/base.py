# strategies/base.py
from abc import ABC, abstractmethod
import pandas as pd


class Strategy(ABC):
    """Abstract base for all QuantDeck strategies.

    Subclass in strategies/signal/, strategies/factor/, or strategies/arbitrage/.
    Both methods must be pure — no Streamlit imports, no side effects.

    Class attributes to set in every subclass:
        name         — display name shown in the Backtester UI
        description  — plain-English explanation (what it does, when it works)
        asset_classes — list of "equity", "fx", "commodity" it supports
        tier         — "conservative", "moderate", or "aggressive"
    """

    name: str = ""
    description: str = ""
    asset_classes: list[str] = []
    tier: str = ""

    @abstractmethod
    def generate_signals(self, prices: pd.DataFrame, **params) -> pd.Series:
        """Return integer signals aligned to prices.index.

        Values: 1 = long, -1 = short, 0 = flat.
        Must have the same index as prices; no NaN values.
        """
        ...

    @abstractmethod
    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        """Return position sizes in [-1.0, 1.0] aligned to signals.index.

        1.0 = full long, -1.0 = full short.
        The backtester multiplies these by initial_capital to size trades.
        """
        ...

    def describe(self) -> dict:
        """Return a serialisable description dict used by the Backtester UI."""
        return {
            "name": self.name,
            "description": self.description,
            "asset_classes": self.asset_classes,
            "tier": self.tier,
        }
