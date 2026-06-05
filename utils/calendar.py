# utils/calendar.py
from datetime import date
import pandas as pd
import pandas_market_calendars as mcal

_EXCHANGE_MAP: dict[str, str] = {
    "US":        "NYSE",
    "UK":        "LSE",
    "Germany":   "XETR",
    "France":    "XPAR",
    "Japan":     "JPX",
    "HongKong":  "HKEX",
    "India":     "BSE",
    "Australia": "ASX",
    "Canada":    "TSX",
}


def get_exchange_calendar(country: str) -> mcal.MarketCalendar:
    """Return the market calendar for the given country. Defaults to NYSE."""
    exchange = _EXCHANGE_MAP.get(country, "NYSE")
    return mcal.get_calendar(exchange)


def get_valid_dates(country: str, start: str, end: str) -> pd.DatetimeIndex:
    """Return all valid trading days between start and end (inclusive) for the given country."""
    cal = get_exchange_calendar(country)
    schedule = cal.schedule(start_date=start, end_date=end)
    return mcal.date_range(schedule, frequency="1D")


def is_trading_day(country: str, check_date: date) -> bool:
    """Return True if check_date is a valid trading day in the given country."""
    cal = get_exchange_calendar(country)
    ds = check_date.strftime("%Y-%m-%d")
    schedule = cal.schedule(start_date=ds, end_date=ds)
    return not schedule.empty
