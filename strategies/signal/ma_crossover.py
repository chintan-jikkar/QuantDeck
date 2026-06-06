# strategies/signal/ma_crossover.py — no Streamlit imports
import pandas as pd
from strategies.base import Strategy


class MACrossover(Strategy):
    name = "MA Crossover"
    description = ("Goes long when the fast moving average crosses above the slow "
                   "moving average (golden cross) and short on the death cross. "
                   "Works in trending markets; whipsaws in choppy ranges.")
    asset_classes = ["equity", "fx", "commodity"]
    tier = "moderate"

    def generate_signals(self, prices: pd.DataFrame, fast: int = 50, slow: int = 200,
                         **params) -> pd.Series:
        close = prices["Close"]
        fast_ma = close.rolling(fast, min_periods=1).mean()
        slow_ma = close.rolling(slow, min_periods=1).mean()
        signal = pd.Series(0, index=close.index)
        signal[fast_ma > slow_ma] = 1
        signal[fast_ma < slow_ma] = -1
        return signal

    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        return signals.astype(float)
