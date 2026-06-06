# strategies/arbitrage/pairs_trading.py — no Streamlit imports
import numpy as np
import pandas as pd
from strategies.base import Strategy


class PairsTrading(Strategy):
    name = "Pairs Trading (Stat Arb)"
    description = ("Trades the spread between two correlated series: short the spread "
                   "when it stretches above +entry_z, long when below -entry_z, exit "
                   "near zero. Market-neutral; depends on the relationship holding.")
    asset_classes = ["equity", "fx", "commodity"]
    tier = "aggressive"

    @staticmethod
    def compute_spread_zscore(a: pd.Series, b: pd.Series, lookback: int = 60) -> pd.Series:
        """Rolling z-score of the (a - b) spread. Look-back only (no future data)."""
        spread = a - b
        mean = spread.rolling(lookback).mean()
        std = spread.rolling(lookback).std()
        return (spread - mean) / std

    def generate_pair_signals(self, a: pd.Series, b: pd.Series, lookback: int = 60,
                              entry_z: float = 2.0, exit_z: float = 0.5) -> pd.Series:
        """Signal on the spread: -1 short spread (a rich), +1 long spread (a cheap), 0 flat."""
        z = self.compute_spread_zscore(a, b, lookback)
        signal = pd.Series(0, index=a.index)
        signal[z > entry_z] = -1
        signal[z < -entry_z] = 1
        return signal.fillna(0).astype(int)

    def generate_signals(self, prices: pd.DataFrame, **params) -> pd.Series:
        return pd.Series(0, index=prices.index, dtype=int)

    def get_positions(self, signals: pd.Series, prices: pd.DataFrame, **params) -> pd.Series:
        return signals.astype(float)
