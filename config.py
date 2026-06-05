# config.py

# ---------------------------------------------------------------------------
# Equity universes — maps display name to yfinance suffix, benchmark ETF,
# local market index (for beta calculation), and country (for COUNTRY_RISK).
# ---------------------------------------------------------------------------
EQUITY_UNIVERSES: dict[str, dict] = {
    "S&P 500":     {"suffix": "",    "benchmark": "SPY",  "market_index": "^GSPC",  "country": "US"},
    "NASDAQ 100":  {"suffix": "",    "benchmark": "QQQ",  "market_index": "^NDX",   "country": "US"},
    "Russell 2000":{"suffix": "",    "benchmark": "IWM",  "market_index": "^RUT",   "country": "US"},
    "FTSE 100":    {"suffix": ".L",  "benchmark": "EWU",  "market_index": "^FTSE",  "country": "UK"},
    "DAX 40":      {"suffix": ".DE", "benchmark": "EWG",  "market_index": "^GDAXI", "country": "Germany"},
    "CAC 40":      {"suffix": ".PA", "benchmark": "EWQ",  "market_index": "^FCHI",  "country": "France"},
    "Nikkei 225":  {"suffix": ".T",  "benchmark": "EWJ",  "market_index": "^N225",  "country": "Japan"},
    "Hang Seng":   {"suffix": ".HK", "benchmark": "EWH",  "market_index": "^HSI",   "country": "HongKong"},
    "Nifty 50":    {"suffix": ".NS", "benchmark": "INDY", "market_index": "^NSEI",  "country": "India"},
    "BSE Sensex":  {"suffix": ".BO", "benchmark": "INDY", "market_index": "^BSESN", "country": "India"},
    "ASX 200":     {"suffix": ".AX", "benchmark": "EWA",  "market_index": "^AXJO",  "country": "Australia"},
    "TSX 60":      {"suffix": ".TO", "benchmark": "EWC",  "market_index": "^GSPTSE","country": "Canada"},
}

# ---------------------------------------------------------------------------
# FX pairs — nested by group, value is the yfinance ticker (ends with =X).
# ---------------------------------------------------------------------------
FX_PAIRS: dict[str, dict[str, str]] = {
    "G10 Majors": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "USD/CHF": "USDCHF=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CAD": "USDCAD=X",
        "NZD/USD": "NZDUSD=X",
        "USD/NOK": "USDNOK=X",
        "USD/SEK": "USDSEK=X",
    },
    "Crosses": {
        "EUR/GBP": "EURGBP=X",
        "EUR/JPY": "EURJPY=X",
        "EUR/CHF": "EURCHF=X",
        "EUR/AUD": "EURAUD=X",
        "EUR/CAD": "EURCAD=X",
        "GBP/JPY": "GBPJPY=X",
        "GBP/AUD": "GBPAUD=X",
        "AUD/JPY": "AUDJPY=X",
        "CAD/JPY": "CADJPY=X",
    },
    "Emerging Markets": {
        "USD/INR": "USDINR=X",
        "USD/CNY": "USDCNY=X",
        "USD/BRL": "USDBRL=X",
        "USD/MXN": "USDMXN=X",
        "USD/ZAR": "USDZAR=X",
        "USD/TRY": "USDTRY=X",
        "USD/SGD": "USDSGD=X",
        "USD/KRW": "USDKRW=X",
        "USD/THB": "USDTHB=X",
        "USD/IDR": "USDIDR=X",
        "USD/PHP": "USDPHP=X",
    },
}

# FX universe benchmark (US Dollar Index ETF)
FX_BENCHMARK = "UUP"

# ---------------------------------------------------------------------------
# Commodities — nested by group, value is the yfinance futures ticker (=F).
# ---------------------------------------------------------------------------
COMMODITIES: dict[str, dict[str, str]] = {
    "Precious Metals": {
        "Gold":      "GC=F",
        "Silver":    "SI=F",
        "Platinum":  "PL=F",
        "Palladium": "PA=F",
    },
    "Energy": {
        "WTI Crude":   "CL=F",
        "Brent":       "BZ=F",
        "Natural Gas": "NG=F",
        "Heating Oil": "HO=F",
        "Gasoline":    "RB=F",
    },
    "Base Metals": {
        "Copper":   "HG=F",
        "Aluminum": "ALI=F",
    },
    "Agricultural": {
        "Corn":        "ZC=F",
        "Wheat":       "ZW=F",
        "Soybeans":    "ZS=F",
        "Soybean Oil": "ZL=F",
        "Sugar":       "SB=F",
        "Coffee":      "KC=F",
        "Cotton":      "CT=F",
        "Cocoa":       "CC=F",
        "Lean Hogs":   "HE=F",
        "Live Cattle": "LE=F",
    },
}

# Commodity universe benchmark (broad commodity ETF)
COMMODITY_BENCHMARK = "DJP"

# ---------------------------------------------------------------------------
# Country-specific risk parameters (Damodaran / CFA).
# Ke = Rf_local + β × ERP + CRP
# ERP values updated annually; these are the 2024 Damodaran estimates.
# ---------------------------------------------------------------------------
COUNTRY_RISK: dict[str, dict] = {
    "US":        {"rf_ticker": "^TNX",            "erp": 0.0472, "crp": 0.0000},
    "UK":        {"rf_ticker": "IRLTLT01GBM156N", "erp": 0.0472, "crp": 0.0051},
    "Germany":   {"rf_ticker": "IRLTLT01DEM156N", "erp": 0.0472, "crp": 0.0051},
    "France":    {"rf_ticker": "IRLTLT01FRM156N", "erp": 0.0472, "crp": 0.0051},
    "Japan":     {"rf_ticker": "IRLTLT01JPM156N", "erp": 0.0472, "crp": 0.0056},
    "India":     {"rf_ticker": "INDIRLTLT01STM",  "erp": 0.0472, "crp": 0.0234},
    "Australia": {"rf_ticker": "IRLTLT01AUM156N", "erp": 0.0472, "crp": 0.0040},
    "Canada":    {"rf_ticker": "IRLTLT01CAM156N", "erp": 0.0472, "crp": 0.0023},
    "HongKong":  {"rf_ticker": "IRLTLT01HKM156N", "erp": 0.0472, "crp": 0.0081},
}

# ---------------------------------------------------------------------------
# FRED series IDs for yield curve construction (US only in Phase 1).
# ---------------------------------------------------------------------------
YIELD_CURVE_TICKERS: dict[str, dict[str, str]] = {
    "US": {
        "3M":  "DTB3",
        "2Y":  "DGS2",
        "5Y":  "DGS5",
        "10Y": "DGS10",
        "30Y": "DGS30",
    },
}

# FRED series used for macro regime detection
MACRO_REGIME_SERIES = {
    "us_3m_yield":       "DTB3",          # 3-Month Treasury Bill
    "us_10y_yield":      "DGS10",         # 10-Year Treasury yield
    "us_credit_spread":  "BAMLC0A0CM",    # ICE BofA US Corporate OAS
    "us_policy_rate":    "FEDFUNDS",      # Federal Funds Rate
    "us_cpi":            "CPIAUCSL",      # Consumer Price Index
}

# ---------------------------------------------------------------------------
# Simulation defaults (convergence-tested N values from the design spec).
# ---------------------------------------------------------------------------
SIMULATION_DEFAULTS: dict[str, int] = {
    "n_paths":       5000,
    "horizon_days":  252,
    "batch_size":    200,
}

# ---------------------------------------------------------------------------
# Backtester defaults.
# ---------------------------------------------------------------------------
BACKTEST_DEFAULTS: dict = {
    "initial_capital": 100_000,
    "commission_bps":  10,       # 10 basis points per trade
    "slippage_pct":    0.001,    # 0.1% of price
}
