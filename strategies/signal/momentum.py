# strategies/signal/momentum.py — no Streamlit imports
import pandas as pd
from strategies.base import Strategy


class Momentum(Strategy):
    name = "12-1 Momentum"
    description = ("Fama-French style momentum: long when the trailing return "
                   "(skipping the most recent month) is positive, short when negative. "
                   "Captures trend persistence; vulnerable to sharp reversals.")
    asset_classes = ["equity", "fx"]
    tier = "moderate"

    def generate_signals(self, prices: pd.DataFrame, lookback: int = 252,
                         skip: int = 21, **params) -> pd.Series:
        close = prices["Close"]
        past = close.shift(skip)
        ref = close.shift(lookback)
        mom = past / ref - 1.0
        signal = pd.Series(0, index=close.index)
        signal[mom > 0] = 1
        signal[mom < 0] = -1
        return signal.fillna(0).astype(int)

    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        return signals.astype(float)
