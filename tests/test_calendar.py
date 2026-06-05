# tests/test_calendar.py
from datetime import date
import pandas as pd
import pytest


def test_get_exchange_calendar_us_returns_nyse():
    from utils.calendar import get_exchange_calendar
    cal = get_exchange_calendar("US")
    assert cal.name == "NYSE"


def test_get_exchange_calendar_uk_returns_lse():
    from utils.calendar import get_exchange_calendar
    cal = get_exchange_calendar("UK")
    assert cal.name == "LSE"


def test_get_exchange_calendar_unknown_defaults_to_nyse():
    from utils.calendar import get_exchange_calendar
    cal = get_exchange_calendar("UnknownCountry")
    assert cal.name == "NYSE"


def test_get_valid_dates_excludes_weekends():
    from utils.calendar import get_valid_dates
    dates = get_valid_dates("US", "2024-01-01", "2024-01-07")
    for d in dates:
        assert d.weekday() < 5, f"{d} is a weekend"


def test_get_valid_dates_returns_datetime_index():
    from utils.calendar import get_valid_dates
    dates = get_valid_dates("US", "2024-01-02", "2024-01-05")
    assert isinstance(dates, pd.DatetimeIndex)


def test_is_trading_day_normal_weekday():
    from utils.calendar import is_trading_day
    assert is_trading_day("US", date(2024, 1, 2)) is True


def test_is_trading_day_saturday():
    from utils.calendar import is_trading_day
    assert is_trading_day("US", date(2024, 1, 6)) is False


def test_is_trading_day_new_years_day():
    from utils.calendar import is_trading_day
    assert is_trading_day("US", date(2024, 1, 1)) is False
