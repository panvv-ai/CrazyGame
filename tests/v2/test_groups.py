from datetime import date

import pytest

from src.panwatch.groups import (
    GroupSeriesMember,
    calculate_weighted_change,
    normalize_weights,
    rebalanced_group_series,
)


def test_normalize_weights_preserves_relative_size():
    assert normalize_weights([2.0, 1.0, 1.0]) == pytest.approx([0.5, 0.25, 0.25])


def test_normalize_weights_rejects_zero_total():
    with pytest.raises(ValueError, match="positive"):
        normalize_weights([0.0, 0.0])


def test_normalize_weights_rejects_negative_value():
    with pytest.raises(ValueError, match="negative"):
        normalize_weights([1.0, -0.5])


def test_calculate_weighted_change_ignores_missing_quotes_and_reports_coverage():
    value, coverage = calculate_weighted_change(
        [
            (2.0, 4.0),
            (1.0, -2.0),
            (1.0, None),
        ]
    )

    assert value == pytest.approx(2.0)
    assert coverage == pytest.approx(0.75)


def test_calculate_weighted_change_returns_none_without_quotes():
    value, coverage = calculate_weighted_change([(1.0, None), (1.0, None)])

    assert value is None
    assert coverage == 0.0


def test_rebalanced_group_series_uses_daily_target_weights():
    series = rebalanced_group_series(
        [
            GroupSeriesMember(
                instrument_id=1,
                weight=1.0,
                points=[
                    (date(2026, 1, 1), 100.0),
                    (date(2026, 1, 2), 110.0),
                    (date(2026, 1, 3), 121.0),
                ],
            ),
            GroupSeriesMember(
                instrument_id=2,
                weight=1.0,
                points=[
                    (date(2026, 1, 1), 100.0),
                    (date(2026, 1, 2), 90.0),
                    (date(2026, 1, 3), 99.0),
                ],
            ),
        ]
    )

    assert [point.value for point in series] == pytest.approx([100.0, 100.0, 110.0])
    assert [point.coverage for point in series] == pytest.approx([1.0, 1.0, 1.0])


def test_rebalanced_group_series_renormalizes_when_member_is_missing():
    series = rebalanced_group_series(
        [
            GroupSeriesMember(
                instrument_id=1,
                weight=1.0,
                points=[
                    (date(2026, 1, 1), 100.0),
                    (date(2026, 1, 2), 110.0),
                ],
            ),
            GroupSeriesMember(
                instrument_id=2,
                weight=1.0,
                points=[(date(2026, 1, 1), 100.0)],
            ),
        ]
    )

    assert [point.value for point in series] == pytest.approx([100.0, 110.0])
    assert [point.coverage for point in series] == pytest.approx([1.0, 0.5])

