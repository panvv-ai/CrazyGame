from src.crazygame.services.notifications import (
    build_aliyun_template_params,
    build_feishu_payload,
    render_alert_message,
)


def test_render_alert_message_uses_requested_language():
    quote = {
        "name": "贵州茅台",
        "symbol": "600519",
        "current_price": 1550.0,
        "change_pct": 1.25,
        "as_of": "2026-11-06T15:00:00+08:00",
        "freshness": "live",
    }

    chinese = render_alert_message("突破提醒", quote, "zh-CN")
    english = render_alert_message("Breakout", quote, "en-US")

    assert "价格提醒" in chinese["title"]
    assert "1550.00" in chinese["body"]
    assert "Price alert" in english["title"]
    assert "1.25%" in english["body"]


def test_build_feishu_payload_contains_interactive_card():
    payload = build_feishu_payload(
        title="价格提醒",
        body="贵州茅台 现价 1550.00",
        url="https://example.test/alerts",
    )

    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "价格提醒"


def test_aliyun_template_params_are_standardized():
    params = build_aliyun_template_params(
        {
            "rule": "突破提醒",
            "name": "贵州茅台",
            "current_price": 1550.0,
            "change_pct": 1.25,
        }
    )

    assert params == {
        "rule": "突破提醒",
        "name": "贵州茅台",
        "price": "1550.00",
        "change": "+1.25%",
    }

