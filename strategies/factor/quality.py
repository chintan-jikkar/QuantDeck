# strategies/factor/quality.py — no Streamlit imports
import pandas as pd
from strategies.base import Strategy


class Quality(Strategy):
    name = "Quality Factor"
    description = ("Ranks toward high profitability (ROE/margin) and low leverage. "
                   "Favors durable, well-run businesses. Defensive in downturns; "
                   "can lag in speculative rallies.")
    asset_classes = ["equity"]
    tier = "conservative"

    @classmethod
    def rank_universe(cls, metrics: pd.DataFrame) -> pd.DataFrame:
        score = pd.Series(0.0, index=metrics.index)
        if "roe" in metrics:
            score += metrics["roe"].rank(pct=True)
        if "netProfitMargin" in metrics:
            score += metrics["netProfitMargin"].rank(pct=True)
        if "debtToEquity" in metrics:
            score += (1 - metrics["debtToEquity"].rank(pct=True))
        return metrics.assign(_score=score).sort_values("_score", ascending=False)

    def generate_signals(self, prices: pd.DataFrame, **params) -> pd.Series:
        return pd.Series(1, index=prices.index, dtype=int)

    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        return signals.astype(float)
