# data/fx.py
import yfinance as yf
import pandas as pd


def get_fx_rate(from_currency: str, to_currency: str = "USD") -> float:
    """Return the most recent closing exchange rate from from_currency to to_currency.

    Uses the yfinance format: EURUSD=X, USDINR=X, etc.
    Raises ValueError if no data is returned (e.g., invalid currency code).
    """
    if from_currency == to_currency:
        return 1.0
    ticker = f"{from_currency}{to_currency}=X"
    df = yf.download(ticker, period="5d", interval="1d", auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        raise ValueError(f"Could not fetch FX rate for {ticker!r}")
    return float(df["Close"].iloc[-1])


def currency_to_usd(value: float, currency: str) -> float:
    """Convert a monetary value from the given currency to USD.

    Returns value unchanged if currency is already USD.
    """
    if currency == "USD":
        return value
    rate = get_fx_rate(currency, "USD")
    return value * rate
