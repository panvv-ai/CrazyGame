from pathlib import Path

from sqlalchemy import select

from src.crazygame.core.config import AppConfig
from src.crazygame.core.database import Base, build_engine, build_session_factory
from src.crazygame.domain.models import (
    AIChatMessage,
    AIChatSession,
    AIReport,
    Instrument,
    MarketIntel,
)


def make_factory(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'ai-models.db'}",
        encryption_key="ai-model-test-secret-key-that-is-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    return engine, build_session_factory(engine)


def test_ai_report_and_intel_are_persisted_for_an_instrument(tmp_path: Path):
    engine, factory = make_factory(tmp_path)
    with factory() as db:
        instrument = Instrument(
            symbol="300750",
            name="宁德时代",
            market="CN",
            asset_type="stock",
            currency="CNY",
            quote_mode="realtime",
        )
        db.add(instrument)
        db.flush()
        report = AIReport(
            instrument_id=instrument.id,
            status="success",
            language="zh-CN",
            verdict="bullish",
            confidence="medium",
            score=72,
            title="宁德时代 AI 诊断",
            content_markdown="# 诊断",
            report_json="{}",
            context_json="{}",
            model_label="fixture-model",
        )
        intel = MarketIntel(
            instrument_id=instrument.id,
            dedupe_key="fixture:one",
            source="fixture",
            title="宁德时代发布公告",
            summary="摘要",
            url="https://example.test/news",
            relevance_kind="direct",
            relevance_score=80,
        )
        db.add_all([report, intel])
        db.commit()

        assert db.scalar(select(AIReport)).score == 72
        assert db.scalar(select(MarketIntel)).relevance_score == 80
    engine.dispose()


def test_deleting_ai_chat_session_cascades_messages(tmp_path: Path):
    engine, factory = make_factory(tmp_path)
    with factory() as db:
        session = AIChatSession(id="session-1", title="测试问股")
        db.add(session)
        db.flush()
        db.add(
            AIChatMessage(
                session_id=session.id,
                role="user",
                content="分析宁德时代",
            )
        )
        db.commit()
        db.delete(session)
        db.commit()

        assert db.scalar(select(AIChatMessage)) is None
    engine.dispose()


def test_same_news_url_can_be_cached_for_multiple_instruments(tmp_path: Path):
    engine, factory = make_factory(tmp_path)
    with factory() as db:
        first = Instrument(
            symbol="300750",
            name="宁德时代",
            market="CN",
            asset_type="stock",
            currency="CNY",
            quote_mode="realtime",
        )
        second = Instrument(
            symbol="600519",
            name="贵州茅台",
            market="CN",
            asset_type="stock",
            currency="CNY",
            quote_mode="realtime",
        )
        db.add_all([first, second])
        db.flush()
        for instrument in (first, second):
            db.add(
                MarketIntel(
                    instrument_id=instrument.id,
                    dedupe_key="shared-article",
                    source="fixture",
                    title="共同新闻",
                )
            )
        db.commit()

        assert db.query(MarketIntel).count() == 2
    engine.dispose()
