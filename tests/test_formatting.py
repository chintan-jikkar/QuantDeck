# tests/test_formatting.py
import math
import pytest
from utils.formatting import fmt_number, fmt_currency, fmt_percent, fmt_large_number


def test_fmt_number_basic():
    assert fmt_number(1234.5678) == "1,234.57"


def test_fmt_number_zero_decimals():
    assert fmt_number(1234.5, decimals=0) == "1,235"


def test_fmt_number_nan_returns_na():
    assert fmt_number(math.nan) == "N/A"


def test_fmt_number_none_returns_na():
    assert fmt_number(None) == "N/A"


def test_fmt_currency_usd():
    assert fmt_currency(1234.56) == "$1,234.56"


def test_fmt_currency_gbp():
    assert fmt_currency(100.0, currency="GBP") == "£100.00"


def test_fmt_currency_jpy():
    assert fmt_currency(10000.0, currency="JPY") == "¥10,000.00"


def test_fmt_currency_unknown_uses_code_prefix():
    assert fmt_currency(100.0, currency="AUD") == "AUD 100.00"


def test_fmt_percent_positive():
    assert fmt_percent(0.05) == "5.0%"


def test_fmt_percent_negative():
    assert fmt_percent(-0.123) == "-12.3%"


def test_fmt_percent_zero():
    assert fmt_percent(0.0) == "0.0%"


def test_fmt_percent_none_returns_na():
    assert fmt_percent(None) == "N/A"


def test_fmt_large_number_trillions():
    assert fmt_large_number(3_000_000_000_000) == "3.00T"


def test_fmt_large_number_billions():
    assert fmt_large_number(2_500_000_000) == "2.50B"


def test_fmt_large_number_millions():
    assert fmt_large_number(750_000_000) == "750.00M"


def test_fmt_large_number_thousands():
    assert fmt_large_number(5_500) == "5.50K"


def test_fmt_large_number_small():
    assert fmt_large_number(500) == "500.00"


def test_fmt_large_number_with_currency():
    assert fmt_large_number(1_500_000_000, currency="USD") == "$1.50B"


def test_fmt_large_number_negative():
    assert fmt_large_number(-500_000_000) == "-500.00M"


def test_fmt_currency_none_returns_na():
    assert fmt_currency(None) == "N/A"


def test_fmt_currency_nan_returns_na():
    assert fmt_currency(math.nan) == "N/A"


def test_fmt_large_number_none_returns_na():
    assert fmt_large_number(None) == "N/A"


def test_fmt_large_number_nan_returns_na():
    assert fmt_large_number(math.nan) == "N/A"
