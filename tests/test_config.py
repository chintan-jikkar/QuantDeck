# tests/test_config.py


def test_equity_universes_structure():
    from config import EQUITY_UNIVERSES
    required = {"suffix", "benchmark", "market_index", "country"}
    for name, info in EQUITY_UNIVERSES.items():
        assert required <= info.keys(), f"{name!r} missing keys: {required - info.keys()}"


def test_all_twelve_equity_universes_present():
    from config import EQUITY_UNIVERSES
    expected = {
        "S&P 500", "NASDAQ 100", "Russell 2000", "FTSE 100",
        "DAX 40", "CAC 40", "Nikkei 225", "Hang Seng",
        "Nifty 50", "BSE Sensex", "ASX 200", "TSX 60",
    }
    assert expected == set(EQUITY_UNIVERSES.keys())


def test_country_risk_structure():
    from config import COUNTRY_RISK
    required = {"rf_ticker", "erp", "crp"}
    for country, info in COUNTRY_RISK.items():
        assert required <= info.keys(), f"{country!r} missing keys"
        assert 0 <= info["erp"] <= 0.15, f"{country} ERP {info['erp']} out of expected range"
        assert 0 <= info["crp"] <= 0.20, f"{country} CRP {info['crp']} out of expected range"


def test_all_equity_universe_countries_have_risk_params():
    from config import EQUITY_UNIVERSES, COUNTRY_RISK
    for name, info in EQUITY_UNIVERSES.items():
        country = info["country"]
        assert country in COUNTRY_RISK, (
            f"No COUNTRY_RISK entry for {country!r} (used by {name!r})"
        )


def test_fx_pairs_yfinance_format():
    from config import FX_PAIRS
    for group, pairs in FX_PAIRS.items():
        for label, ticker in pairs.items():
            assert ticker.endswith("=X"), (
                f"{label} ticker {ticker!r} is not in yfinance FX format (must end with =X)"
            )


def test_commodities_futures_format():
    from config import COMMODITIES
    for group, items in COMMODITIES.items():
        for name, ticker in items.items():
            assert ticker.endswith("=F"), (
                f"{name} ticker {ticker!r} is not in yfinance futures format (must end with =F)"
            )


def test_simulation_defaults():
    from config import SIMULATION_DEFAULTS
    assert SIMULATION_DEFAULTS["n_paths"] == 5000
    assert SIMULATION_DEFAULTS["batch_size"] == 200
    assert SIMULATION_DEFAULTS["horizon_days"] == 252


def test_backtest_defaults():
    from config import BACKTEST_DEFAULTS
    assert BACKTEST_DEFAULTS["initial_capital"] == 100_000
    assert "commission_bps" in BACKTEST_DEFAULTS
    assert "slippage_pct" in BACKTEST_DEFAULTS
