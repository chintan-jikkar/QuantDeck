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


def compute_cagr(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    """Compound annual growth rate from an equity curve."""
    eq = equity_curve.dropna()
    if len(eq) < 2 or eq.iloc[0] <= 0:
        return 0.0
    total_return = eq.iloc[-1] / eq.iloc[0]
    years = len(eq) / periods_per_year
    if years <= 0:
        return 0.0
    return float(total_return ** (1 / years) - 1)


def compute_sharpe(returns: pd.Series, rf: float = 0.0, periods_per_year: int = 252) -> float:
    """Annualized Sharpe ratio. Returns 0.0 when volatility is zero."""
    r = returns.dropna()
    excess = r - rf / periods_per_year
    std = excess.std(ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def compute_sortino(returns: pd.Series, rf: float = 0.0, periods_per_year: int = 252) -> float:
    """Annualized Sortino ratio (downside deviation only)."""
    r = returns.dropna()
    excess = r - rf / periods_per_year
    downside = excess[excess < 0]
    dd = downside.std(ddof=1)
    if dd == 0 or np.isnan(dd):
        return 0.0
    return float(excess.mean() / dd * np.sqrt(periods_per_year))


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a negative fraction (e.g. -0.25)."""
    eq = equity_curve.dropna()
    if eq.empty:
        return 0.0
    running_max = eq.cummax()
    drawdown = eq / running_max - 1.0
    return float(drawdown.min())


def compute_tearsheet(equity_curve: pd.Series, returns: pd.Series,
                      periods_per_year: int = 252) -> dict:
    """Full performance summary used by the Backtester tearsheet panel."""
    eq = equity_curve.dropna()
    r = returns.dropna()
    cagr = compute_cagr(eq, periods_per_year)
    max_dd = compute_max_drawdown(eq)
    wins = r[r > 0]
    losses = r[r < 0]
    win_rate = float(len(wins) / len(r)) if len(r) else 0.0
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf")
    calmar = float(cagr / abs(max_dd)) if max_dd != 0 else float("inf")
    return {
        "cagr": cagr,
        "sharpe": compute_sharpe(r, periods_per_year=periods_per_year),
        "sortino": compute_sortino(r, periods_per_year=periods_per_year),
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "calmar": calmar,
        "total_return": float(eq.iloc[-1] / eq.iloc[0] - 1) if len(eq) >= 2 else 0.0,
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "n_periods": int(len(r)),
    }
