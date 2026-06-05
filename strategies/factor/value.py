# strategies/factor/value.py — no Streamlit imports
import pandas as pd
from strategies.base import Strategy


class Value(Strategy):
    name = "Value (Graham/Buffett)"
    description = ("Ranks the universe toward low P/E and P/B with healthy ROE. "
                   "Buys the cheapest quality names. Works over long horizons; "
                   "can underperform in momentum-driven markets.")
    asset_classes = ["equity"]
    tier = "conservative"

    @classmethod
    def rank_universe(cls, metrics: pd.DataFrame) -> pd.DataFrame:
        """Rank tickers (rows) best→worst on cheapness + quality.

        Lower P/E and P/B are better; higher ROE is better.
        """
        score = pd.Series(0.0, index=metrics.index)
        if "peRatio" in metrics:
            score += (1 - metrics["peRatio"].rank(pct=True))
        if "pbRatio" in metrics:
            score += (1 - metrics["pbRatio"].rank(pct=True))
        if "roe" in metrics:
            score += metrics["roe"].rank(pct=True)
        return metrics.assign(_score=score).sort_values("_score", ascending=False)

    def generate_signals(self, prices: pd.DataFrame, **params) -> pd.Series:
        return pd.Series(1, index=prices.index, dtype=int)

    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        return signals.astype(float)
