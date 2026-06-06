# strategies/signal/rsi_mean_reversion.py — no Streamlit imports
import pandas as pd
from strategies.base import Strategy
from data.prices import compute_rsi


class RSIMeanReversion(Strategy):
    name = "RSI Mean Reversion"
    description = ("Buys when RSI falls below the oversold threshold and sells when "
                   "it rises above overbought, betting on reversion. Works in "
                   "range-bound markets; dangerous in strong trends.")
    asset_classes = ["equity", "fx", "commodity"]
    tier = "moderate"

    def generate_signals(self, prices: pd.DataFrame, period: int = 14,
                         oversold: float = 30, overbought: float = 70, **params) -> pd.Series:
        rsi = compute_rsi(prices["Close"], period=period)
        signal = pd.Series(0, index=prices.index)
        signal[rsi < oversold] = 1
        signal[rsi > overbought] = -1
        return signal.fillna(0).astype(int)

    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        return signals.astype(float)
