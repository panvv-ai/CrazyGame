from marketdata.types import Bar

from src.crazygame.services.ai_technical import build_technical_snapshot


def make_bars(count: int) -> list[Bar]:
    return [
        Bar(
            date=f"2026-01-{index + 1:02d}",
            open=float(index + 1),
            close=float(index + 1),
            high=float(index + 2),
            low=float(index),
            volume=1_000.0 + index * 10,
        )
        for index in range(count)
    ]


def test_technical_snapshot_calculates_moving_averages_from_complete_history():
    snapshot = build_technical_snapshot(make_bars(80))

    assert snapshot["bar_count"] == 80
    assert snapshot["ma"]["ma5"] == 78.0
    assert snapshot["ma"]["ma10"] == 75.5
    assert snapshot["ma"]["ma20"] == 70.5
    assert snapshot["ma"]["ma60"] == 50.5
    assert snapshot["ma"]["alignment"] == "bullish"
    assert snapshot["macd"]["bar"] > 0
    assert snapshot["support"] < snapshot["resistance"]
    assert snapshot["limitations"] == []


def test_technical_snapshot_marks_short_history_as_limited():
    snapshot = build_technical_snapshot(make_bars(10))

    assert snapshot["bar_count"] == 10
    assert snapshot["ma"]["ma20"] is None
    assert snapshot["ma"]["alignment"] == "unknown"
    assert snapshot["limitations"] == ["history_under_60_days"]
