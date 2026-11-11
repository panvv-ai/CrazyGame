from src.crazygame.services.ai_news import (
    parse_bocha_results,
    parse_tavily_results,
)


def test_parse_tavily_results_maps_news_fields():
    items = parse_tavily_results(
        {
            "results": [
                {
                    "title": "宁德时代最新公告",
                    "content": "公司披露经营情况",
                    "url": "https://example.test/tavily",
                    "published_date": "2026-11-10T08:00:00Z",
                    "score": 0.8,
                }
            ]
        }
    )

    assert items[0].title == "宁德时代最新公告"
    assert items[0].source == "Tavily"
    assert items[0].url == "https://example.test/tavily"


def test_parse_bocha_results_maps_web_pages():
    items = parse_bocha_results(
        {
            "data": {
                "webPages": {
                    "value": [
                        {
                            "name": "宁德时代储能业务进展",
                            "summary": "储能订单增长",
                            "url": "https://example.test/bocha",
                            "siteName": "财经网",
                            "datePublished": "2026-11-10T08:00:00+08:00",
                        }
                    ]
                }
            }
        }
    )

    assert items[0].title == "宁德时代储能业务进展"
    assert items[0].source == "财经网"
