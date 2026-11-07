from __future__ import annotations

from datetime import date


def _dates(start: str, end: str) -> frozenset[date]:
    current = date.fromisoformat(start)
    last = date.fromisoformat(end)
    values: set[date] = set()
    while current <= last:
        values.add(current)
        current = date.fromordinal(current.toordinal() + 1)
    return frozenset(values)


HOLIDAYS: dict[tuple[str, int], frozenset[date]] = {
    ("CN", 2026): _dates("2026-01-01", "2026-01-03")
    | _dates("2026-02-15", "2026-02-23")
    | _dates("2026-04-04", "2026-04-06")
    | _dates("2026-05-01", "2026-05-05")
    | _dates("2026-06-19", "2026-06-21")
    | _dates("2026-09-25", "2026-09-27")
    | _dates("2026-10-01", "2026-10-07"),
    ("HK", 2026): frozenset(
        date.fromisoformat(value)
        for value in (
            "2026-01-01",
            "2026-02-17",
            "2026-02-18",
            "2026-02-19",
            "2026-04-03",
            "2026-04-06",
            "2026-04-07",
            "2026-05-01",
            "2026-05-25",
            "2026-06-19",
            "2026-07-01",
            "2026-10-01",
            "2026-10-19",
            "2026-12-25",
        )
    ),
    ("US", 2026): frozenset(
        date.fromisoformat(value)
        for value in (
            "2026-01-01",
            "2026-01-19",
            "2026-02-16",
            "2026-04-03",
            "2026-05-25",
            "2026-06-19",
            "2026-07-03",
            "2026-09-07",
            "2026-11-26",
            "2026-12-25",
        )
    ),
}

EARLY_CLOSES: dict[tuple[str, date], int] = {
    ("HK", date(2026, 2, 16)): 12,
    ("HK", date(2026, 12, 24)): 12,
    ("HK", date(2026, 12, 31)): 12,
    ("US", date(2026, 11, 27)): 13,
    ("US", date(2026, 12, 24)): 13,
}


def is_trading_day(market: str, day: date) -> bool:
    market_code = market.upper()
    if day.weekday() >= 5:
        return False
    holidays = HOLIDAYS.get((market_code, day.year))
    return holidays is not None and day not in holidays

