# layers/backtester.py — no Streamlit imports
import numpy as np
import pandas as pd


def run_engine(prices: pd.Series, signals: pd.Series, initial_capital: float = 100_000,
               commission_bps: float = 10, slippage_pct: float = 0.001) -> dict:
    """Vectorized long/short backtest on a single price series.

    signals: 1 (long), -1 (short), 0 (flat), aligned to prices.index.
    No look-ahead: the return earned on day t uses the position held from t-1.
    Transaction costs are charged on turnover (|Δsignal|) each day.

    Returns dict: equity_curve, returns, positions, trades.
    """
    prices = prices.dropna()
    signals = signals.reindex(prices.index).fillna(0)

    asset_returns = prices.pct_change().fillna(0)
    positions = signals.shift(1).fillna(0)  # act on yesterday's signal

    gross = positions * asset_returns

    turnover = signals.diff().abs().fillna(signals.abs())
    cost_rate = commission_bps / 10_000.0 + slippage_pct
    costs = turnover * cost_rate

    net = gross - costs
    equity_curve = (1 + net).cumprod() * initial_capital

    changed = signals.diff().fillna(signals).abs() > 0
    trade_days = signals[changed]
    trades = pd.DataFrame({
        "date": trade_days.index,
        "signal": trade_days.values,
        "price": prices.reindex(trade_days.index).values,
    })

    return {
        "equity_curve": equity_curve,
        "returns": net,
        "positions": positions,
        "trades": trades,
    }
