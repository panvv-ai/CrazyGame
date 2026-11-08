from datetime import date

from src.crazygame.core.calendar import is_trading_day


def test_weekend_is_not_a_trading_day():
    assert is_trading_day("CN", date(2026, 11, 7)) is False


def test_published_weekday_holiday_is_not_a_trading_day():
    assert is_trading_day("CN", date(2026, 10, 1)) is False


def test_regular_weekday_is_a_trading_day():
    assert is_trading_day("CN", date(2026, 11, 6)) is True


def test_unpublished_future_year_is_not_tradable():
    assert is_trading_day("CN", date(2035, 1, 3)) is False
