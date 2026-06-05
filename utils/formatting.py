# utils/formatting.py
import math
import decimal

_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹"}


def fmt_number(value: float | None, decimals: int = 2) -> str:
    """Format a number with commas. Returns 'N/A' for None or NaN."""
    if value is None:
        return "N/A"
    try:
        if math.isnan(value):
            return "N/A"
    except TypeError:
        return "N/A"
    # Use ROUND_HALF_UP (standard rounding) instead of Python's default banker's rounding.
    quantizer = decimal.Decimal(10) ** -decimals
    rounded = float(
        decimal.Decimal(str(value)).quantize(quantizer, rounding=decimal.ROUND_HALF_UP)
    )
    return f"{rounded:,.{decimals}f}"


def fmt_currency(value: float | None, currency: str = "USD", decimals: int = 2) -> str:
    """Format a value as currency. Unknown currencies use the ISO code as prefix.

    Returns 'N/A' for None or NaN (fundamentals data routinely has missing fields).
    """
    if value is None:
        return "N/A"
    try:
        if math.isnan(value):
            return "N/A"
    except TypeError:
        return "N/A"
    symbol = _CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    return f"{symbol}{value:,.{decimals}f}"


def fmt_percent(value: float | None, decimals: int = 1) -> str:
    """Format a decimal fraction as a percentage string (0.05 → '5.0%').

    Returns 'N/A' for None.
    """
    if value is None:
        return "N/A"
    return f"{value * 100:.{decimals}f}%"


def fmt_large_number(value: float | None, currency: str = "") -> str:
    """Format large numbers with T/B/M/K suffixes.

    Negative values are prefixed with '-'. Currency symbol is prepended when provided.
    Returns 'N/A' for None or NaN (e.g. missing market cap).
    """
    if value is None:
        return "N/A"
    try:
        if math.isnan(value):
            return "N/A"
    except TypeError:
        return "N/A"
    prefix = _CURRENCY_SYMBOLS.get(currency, f"{currency} ") if currency else ""
    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"{sign}{prefix}{abs_val / 1e12:.2f}T"
    if abs_val >= 1e9:
        return f"{sign}{prefix}{abs_val / 1e9:.2f}B"
    if abs_val >= 1e6:
        return f"{sign}{prefix}{abs_val / 1e6:.2f}M"
    if abs_val >= 1e3:
        return f"{sign}{prefix}{abs_val / 1e3:.2f}K"
    return f"{sign}{prefix}{abs_val:.2f}"
