import pytest
from pydantic import ValidationError

from src.crazygame.domain.ai import normalize_ai_report_payload


def base_payload() -> dict:
    return {
        "score": 78,
        "verdict": "bullish",
        "confidence": "high",
        "core_conclusion": "趋势偏强，但等待量能确认。",
        "trend": "均线多头排列",
        "hotspots": [
            {
                "title": f"热点 {index}",
                "summary": "摘要",
                "url": f"https://example.test/{index}",
                "source": "测试",
                "published_at": "2026-11-11T10:00:00+08:00",
                "relevance_kind": "direct",
            }
            for index in range(5)
        ],
        "risks": ["高位波动"],
        "catalysts": ["订单增长"],
        "position_advice": {
            "no_position": "等待回踩确认",
            "has_position": "持有并设置风险条件",
        },
        "price_plan": {
            "support": 240.0,
            "resistance": 270.0,
            "invalidation_reference": 230.0,
        },
        "action_checklist": ["检查量能", "检查风险事件"],
        "data_quality": {
            "level": "limited",
            "limitations": ["news unavailable"],
        },
    }


def test_report_schema_caps_confidence_and_hotspots_when_evidence_is_limited():
    report = normalize_ai_report_payload(
        base_payload(),
        instrument={
            "id": 7,
            "symbol": "300750",
            "name": "宁德时代",
            "market": "CN",
            "asset_type": "stock",
        },
        language="zh-CN",
    )

    assert report.confidence == "medium"
    assert len(report.hotspots) == 3
    assert report.instrument.symbol == "300750"
    assert report.disclaimer


def test_report_schema_rejects_missing_core_conclusion():
    payload = base_payload()
    payload["core_conclusion"] = ""

    with pytest.raises(ValidationError):
        normalize_ai_report_payload(
            payload,
            instrument={"id": 1, "symbol": "600519", "name": "贵州茅台"},
            language="zh-CN",
        )


def test_report_schema_strips_non_http_hotspot_links():
    payload = base_payload()
    payload["hotspots"][0]["url"] = "javascript:alert(1)"

    report = normalize_ai_report_payload(
        payload,
        instrument={"id": 1, "symbol": "600519", "name": "贵州茅台"},
        language="zh-CN",
    )

    assert report.hotspots[0].url == ""
