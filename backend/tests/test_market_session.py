from datetime import datetime
from zoneinfo import ZoneInfo

from src.crazygame.services.market import is_market_open


def test_cn_market_is_open_during_morning_session():
    moment = datetime(2026, 11, 6, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert is_market_open("CN", moment) is True


def test_cn_market_is_closed_during_lunch_break():
    moment = datetime(2026, 11, 6, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert is_market_open("CN", moment) is False


def test_market_is_closed_on_exchange_holiday():
    moment = datetime(2026, 10, 1, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    assert is_market_open("CN", moment) is False


def test_us_market_uses_new_york_timezone():
    moment = datetime(2026, 11, 6, 15, 0, tzinfo=ZoneInfo("UTC"))

    assert is_market_open("US", moment) is True

