# data/fundamentals.py
"""Fundamentals via yfinance (no API key, no rate limit, global coverage).

yfinance returns each statement as a DataFrame of line-items (rows) x periods
(columns, newest-first). We transpose into QuantDeck's legacy per-period schema
(rows = periods newest-first, columns = the FMP-style field names the rest of the
app already expects) so Valuation / Screener / Deep Dive need no changes.
"""
import time
import pandas as pd
import yfinance as yf

# In-process cache: each (ticker, statement) is fetched once per hour. yfinance is
# free and lenient, but caching keeps repeated module loads instant.
_CACHE: dict = {}
_CACHE_TTL = 3600

# legacy field -> candidate yfinance row labels (first present wins)
_INCOME_MAP = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "costOfRevenue": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "grossProfit": ["Gross Profit"],
    "operatingIncome": ["Operating Income", "Total Operating Income As Reported"],
    "netIncome": ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"],
    "sellingGeneralAndAdministrativeExpenses": ["Selling General And Administration", "Selling General And Administrative Expense"],
    "depreciationAndAmortization": ["Reconciled Depreciation", "Depreciation And Amortization In Income Statement"],
    "interestExpense": ["Interest Expense", "Interest Expense Non Operating"],
    "incomeTaxExpense": ["Tax Provision", "Income Tax Expense"],
    "incomeBeforeTax": ["Pretax Income", "Income Before Tax"],
    "eps": ["Diluted EPS", "Basic EPS"],
    "weightedAverageShsOut": ["Diluted Average Shares", "Basic Average Shares"],
}
_BALANCE_MAP = {
    "totalAssets": ["Total Assets"],
    "totalCurrentAssets": ["Current Assets", "Total Current Assets"],
    "propertyPlantEquipmentNet": ["Net PPE", "Net Property Plant And Equipment"],
    "netReceivables": ["Receivables", "Accounts Receivable", "Net Receivables"],
    "totalCurrentLiabilities": ["Current Liabilities", "Total Current Liabilities"],
    "longTermDebt": ["Long Term Debt"],
    "totalDebt": ["Total Debt"],
    "totalEquity": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "cashAndCashEquivalents": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
}
_CASHFLOW_MAP = {
    "operatingCashFlow": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capitalExpenditure": ["Capital Expenditure", "Purchase Of PPE"],
    "dividendsPaid": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
    "commonStockRepurchased": ["Repurchase Of Capital Stock", "Common Stock Payments"],
    "freeCashFlow": ["Free Cash Flow"],
    "depreciationAndAmortization": ["Depreciation And Amortization", "Depreciation Amortization Depletion"],
}


def _cached(ticker: str, attr: str):
    key = (ticker, attr)
    now = time.time()
    hit = _CACHE.get(key)
    if hit is not None and now - hit[0] < _CACHE_TTL:
        return hit[1]
    try:
        val = getattr(yf.Ticker(ticker), attr)
    except Exception:
        val = None
    _CACHE[key] = (now, val)
    return val


def _pick(df: pd.DataFrame, candidates: list, col) -> float:
    for label in candidates:
        if label in df.index:
            try:
                return float(df.loc[label, col])
            except Exception:
                return float("nan")
    return float("nan")


def _statement(ticker: str, attr: str, mapping: dict, limit: int) -> pd.DataFrame:
    raw = _cached(ticker, attr)
    if raw is None or getattr(raw, "empty", True):
        return pd.DataFrame()
    raw = raw.iloc[:, :limit]  # most-recent `limit` periods (yfinance is newest-first)
    rows = []
    for col in raw.columns:
        rec = {"date": str(col)[:10]}
        for field, cands in mapping.items():
            rec[field] = _pick(raw, cands, col)
        rows.append(rec)
    return pd.DataFrame(rows)


def fetch_income_statement(ticker: str, limit: int = 5) -> pd.DataFrame:
    ticker = ticker.upper()
    df = _statement(ticker, "income_stmt", _INCOME_MAP, limit)
    # yfinance often omits D&A from the income statement; backfill from cash flow.
    if not df.empty and df["depreciationAndAmortization"].isna().all():
        cf = _statement(ticker, "cashflow",
                        {"depreciationAndAmortization": _CASHFLOW_MAP["depreciationAndAmortization"]}, limit)
        if not cf.empty and len(cf) == len(df):
            df["depreciationAndAmortization"] = cf["depreciationAndAmortization"].values
    return df


def fetch_balance_sheet(ticker: str, limit: int = 5) -> pd.DataFrame:
    return _statement(ticker.upper(), "balance_sheet", _BALANCE_MAP, limit)


def fetch_cash_flow(ticker: str, limit: int = 5) -> pd.DataFrame:
    # capex / dividends come back negative (outflows); consumers use .abs() already.
    return _statement(ticker.upper(), "cashflow", _CASHFLOW_MAP, limit)


def fetch_key_metrics(ticker: str, limit: int = 5) -> pd.DataFrame:
    """Current-snapshot metrics from yfinance .info, in the legacy schema."""
    info = _cached(ticker.upper(), "info") or {}
    if not info:
        return pd.DataFrame()
    de = info.get("debtToEquity")
    if de is not None and de > 10:  # yfinance reports D/E as a percentage
        de = de / 100.0
    row = {
        "peRatio": info.get("trailingPE"),
        "pbRatio": info.get("priceToBook"),
        "evToEbitda": info.get("enterpriseToEbitda"),
        "roe": info.get("returnOnEquity"),
        "debtToEquity": de,
        "netProfitMargin": info.get("profitMargins"),
        "revenueGrowth": info.get("revenueGrowth"),
        "currentRatio": info.get("currentRatio"),
        "marketCap": info.get("marketCap"),
        "sharesOutstanding": info.get("sharesOutstanding"),
    }
    return pd.DataFrame([row])


def fetch_peers(ticker: str) -> list[str]:
    """yfinance has no reliable peer endpoint; comps are unavailable for now."""
    return []
