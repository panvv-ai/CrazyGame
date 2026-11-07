from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.panwatch.alerts import AlertCondition, condition_matches, next_market_midnight


@pytest.mark.parametrize(
    ("metric", "direction", "threshold", "actual", "expected"),
    [
        ("price", "above", 100.0, 100.1, True),
        ("price", "above", 100.0, 100.0, False),
        ("price", "below", 100.0, 99.9, True),
        ("change_pct", "above", 3.0, 3.01, True),
        ("change_pct", "below", -2.0, -2.01, True),
    ],
)
def test_condition_matches_threshold_boundaries(
    metric: str,
    direction: str,
    threshold: float,
    actual: float,
    expected: bool,
):
    condition = AlertCondition(metric=metric, direction=direction, threshold=threshold)

    assert condition_matches(
        condition,
        {"price": actual, "change_pct": actual},
    ) is expected


def test_condition_does_not_match_missing_value():
    condition = AlertCondition(metric="price", direction="above", threshold=100.0)

    assert condition_matches(condition, {"price": None, "change_pct": 1.0}) is False


def test_next_market_midnight_uses_market_timezone():
    current = datetime(2026, 11, 6, 23, 30, tzinfo=ZoneInfo("Asia/Shanghai"))

    boundary = next_market_midnight(current, ZoneInfo("Asia/Shanghai"))

    assert boundary == datetime(2026, 11, 7, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

