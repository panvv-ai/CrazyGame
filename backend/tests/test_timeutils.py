from datetime import datetime

from src.crazygame.core.timeutils import iso_utc


def test_naive_database_time_is_serialized_as_utc():
    assert iso_utc(datetime(2026, 11, 6, 7, 0)) == "2026-11-06T07:00:00+00:00"

