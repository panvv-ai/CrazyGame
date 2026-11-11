from __future__ import annotations

from src.crazygame.services.notifications import render_alert_message


def test_alert_message_formats_iso_timestamp_for_people():
    message = render_alert_message(
        "特斯拉股价",
        {
            "name": "特斯拉",
            "symbol": "TSLA",
            "current_price": 379.78,
            "change_pct": 0.46,
            "as_of": "2026-11-11T16:35:04-05:00",
            "freshness": "live",
        },
        "zh-CN",
    )

    assert "数据：live · 2026-11-11 16:35:04" in message["body"]
    assert "T16:35:04-05:00" not in message["body"]
