from datetime import datetime, timedelta, timezone

from src.crazygame.services.ai_news import IntelItem, rank_intel_items


def test_rank_intel_items_prioritizes_identity_then_concept_then_macro():
    now = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)
    items = [
        IntelItem(
            title="央行宣布降准",
            summary="宏观流动性变化",
            url="https://example.test/macro",
            source="财经媒体",
            published_at=now,
        ),
        IntelItem(
            title="白酒板块今日回暖",
            summary="行业情绪改善",
            url="https://example.test/sector",
            source="财经媒体",
            published_at=now,
        ),
        IntelItem(
            title="贵州茅台发布经营数据",
            summary="公司披露最新经营情况",
            url="https://example.test/company",
            source="公司公告",
            published_at=now - timedelta(hours=1),
        ),
        IntelItem(
            title="600519 获机构关注",
            summary="机构发布最新观点",
            url="https://example.test/direct",
            source="证券媒体",
            published_at=now - timedelta(hours=2),
        ),
    ]

    ranked = rank_intel_items(
        items,
        symbol="600519",
        name="贵州茅台",
        industry="白酒",
        concepts=["消费", "白酒概念"],
        now=now,
        limit=3,
    )

    assert [item.url for item in ranked] == [
        "https://example.test/direct",
        "https://example.test/company",
        "https://example.test/sector",
    ]
    assert ranked[0].relevance_kind == "direct"
    assert ranked[0].relevance_score > ranked[1].relevance_score
    assert ranked[2].relevance_kind == "sector"
    assert "白酒" in " ".join(ranked[2].relevance_reasons)


def test_rank_intel_items_deduplicates_urls_and_drops_old_items():
    now = datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc)
    items = [
        IntelItem(
            title="宁德时代发布公告",
            summary="较新的版本",
            url="https://example.test/same",
            source="公告",
            published_at=now,
        ),
        IntelItem(
            title="宁德时代发布公告",
            summary="较旧的版本",
            url="https://example.test/same",
            source="转载",
            published_at=now - timedelta(days=3),
        ),
        IntelItem(
            title="宁德时代旧闻",
            summary="超出时效",
            url="https://example.test/old",
            source="转载",
            published_at=now - timedelta(days=45),
        ),
    ]

    ranked = rank_intel_items(
        items,
        symbol="300750",
        name="宁德时代",
        industry="电池",
        concepts=["新能源"],
        now=now,
        limit=8,
    )

    assert len(ranked) == 1
    assert ranked[0].summary == "较新的版本"
