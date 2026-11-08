from src.crazygame.providers.fund_collector import latest_point_change


def test_latest_point_change_uses_adjacent_nav_points():
    points = [
        {"value": 1.80},
        {"value": 1.85},
        {"value": 1.8325},
    ]

    assert round(latest_point_change(points), 6) == -0.945946


def test_latest_point_change_handles_invalid_or_short_series():
    assert latest_point_change([]) is None
    assert latest_point_change([{"value": 1.8}]) is None
    assert latest_point_change([{"value": 0}, {"value": 1.8}]) is None
