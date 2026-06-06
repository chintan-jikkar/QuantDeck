# data/prices.py
import pandas as pd
import yfinance as yf


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns that yfinance 0.2.x returns for single-ticker downloads."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_prices(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data for any asset. Ticker must be in yfinance format.

    Works for equities (AAPL), FX (EURUSD=X), and commodities (GC=F).
    Raises ValueError if no data is returned.
    """
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
    df = _normalize_df(df)
    if df.empty:
        raise ValueError(f"No price data for {ticker!r} (period={period!r}, interval={interval!r})")
    return df


def fetch_intraday(ticker: str) -> pd.DataFrame:
    """Fetch 5-minute intraday bars for the current trading day."""
    return fetch_prices(ticker, period="1d", interval="5m")


def compute_returns(prices: pd.DataFrame, col: str = "Close") -> pd.Series:
    """Daily percentage returns from a price column, with the first NaN dropped."""
    return prices[col].pct_change().dropna()


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index using exponential moving averages (Wilder-style smoothing).

    Values outside [0, 100] are not possible by construction.
    The first `period` values are NaN (the leading diff is NaN, then `min_periods`
    requires `period` observations before a value is produced).

    Note: this seeds the average via `ewm` from the first bar rather than the
    textbook Wilder seed (an SMA at index `period`). Early values differ slightly
    from strict Wilder RSI but converge within a few dozen bars.
    """
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_rolling_beta(
    stock_returns: pd.Series,
    market_returns: pd.Series,
    window: int = 60,
) -> pd.Series:
    """Rolling beta of stock returns vs market returns over a sliding window.

    Beta = Cov(stock, market) / Var(market).
    The spec uses 60-month windows; pass monthly returns for spec-correct values.
    """
    cov = stock_returns.rolling(window).cov(market_returns)
    var = market_returns.rolling(window).var()
    return cov / var


def detect_asset_type(ticker: str) -> str:
    """Detect asset class from yfinance ticker format.

    =X suffix → "fx"; =F suffix → "commodity"; else → "equity".
    Case-insensitive.
    """
    t = ticker.upper().strip()
    if t.endswith("=X"):
        return "fx"
    if t.endswith("=F"):
        return "commodity"
    return "equity"


def get_benchmark(ticker: str) -> str:
    """Return the benchmark ETF ticker for a given ticker based on asset type.

    FX → UUP (US Dollar Index ETF).
    Commodity → DJP (broad commodity ETF).
    Equity → looks up the universe benchmark by ticker suffix; defaults to SPY.
    """
    from config import FX_BENCHMARK, COMMODITY_BENCHMARK, EQUITY_UNIVERSES
    asset_type = detect_asset_type(ticker)
    if asset_type == "fx":
        return FX_BENCHMARK
    if asset_type == "commodity":
        return COMMODITY_BENCHMARK
    # Equity: match suffix to a universe entry
    # Empty suffix means US (S&P 500, NASDAQ, Russell) — those fall through to the "SPY" default below.
    suffix_map = {info["suffix"]: info["benchmark"] for info in EQUITY_UNIVERSES.values() if info["suffix"]}
    t = ticker.upper()
    for suffix, benchmark in suffix_map.items():
        if t.endswith(suffix.upper()):
            return benchmark
    return "SPY"


def country_from_ticker(ticker: str) -> str:
    """Derive the issuing country from a yfinance equity ticker suffix.

    Derives suffix→country mapping from config.EQUITY_UNIVERSES so it stays
    in sync automatically when new universes are added. Non-suffixed tickers
    (US stocks) return "US". FX and commodity tickers return "US" as a neutral
    default since country-risk valuation doesn't apply to them.
    """
    from config import EQUITY_UNIVERSES
    suffix_country = {
        info["suffix"]: info["country"]
        for info in EQUITY_UNIVERSES.values()
        if info["suffix"]
    }
    t = ticker.upper()
    for suffix, country in suffix_country.items():
        if t.endswith(suffix.upper()):
            return country
    return "US"


def market_index_for_country(country: str) -> str:
    """Return the local equity market index ticker for beta calculation.

    Reads from config.EQUITY_UNIVERSES (first match wins for countries with
    multiple universes, e.g. India → ^NSEI from Nifty 50). Falls back to
    ^GSPC (S&P 500) for unknown countries.
    """
    from config import EQUITY_UNIVERSES
    for info in EQUITY_UNIVERSES.values():
        if info["country"] == country:
            return info["market_index"]
    return "^GSPC"
