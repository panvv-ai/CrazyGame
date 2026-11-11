from datetime import datetime, timezone

from src.crazygame.services.ai_news import (
    parse_eastmoney_announcements,
    parse_eastmoney_news_jsonp,
    parse_eastmoney_tags,
)


def test_parse_eastmoney_news_jsonp_removes_highlight_markup():
    payload = """cb({"result":{"cmsArticleWebOld":[{
      "date":"2026-11-10 15:04:20",
      "title":"<em>宁德时代</em>发布新产品",
      "content":"公司与客户签署<em>新协议</em>。",
      "mediaName":"财联社",
      "url":"https://finance.eastmoney.com/a/1.html"
    }]}})"""

    items = parse_eastmoney_news_jsonp(
        payload,
        now=datetime(2026, 11, 11, tzinfo=timezone.utc),
    )

    assert len(items) == 1
    assert items[0].title == "宁德时代发布新产品"
    assert items[0].summary == "公司与客户签署新协议。"
    assert items[0].source == "财联社"


def test_parse_eastmoney_announcements_builds_notice_links():
    payload = {
        "data": {
            "list": [
                {
                    "art_code": "AN123",
                    "title": "宁德时代:关于股份回购的公告",
                    "notice_date": "2026-11-09 00:00:00",
                    "columns": [{"column_name": "回购"}],
                }
            ]
        }
    }

    items = parse_eastmoney_announcements(payload, symbol="300750")

    assert items[0].title.startswith("宁德时代")
    assert items[0].url.endswith("/300750/AN123.html")
    assert items[0].source == "公司公告"


def test_parse_eastmoney_tags_extracts_industry_and_concepts():
    payload = {
        "data": {
            "f127": "电池",
            "f129": "新能源,锂电池概念,储能概念",
        }
    }

    tags = parse_eastmoney_tags(payload)

    assert tags == {
        "industry": "电池",
        "concepts": ["新能源", "锂电池概念", "储能概念"],
    }
