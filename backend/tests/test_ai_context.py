from datetime import date
from pathlib import Path

from marketdata.types import Bar

from src.crazygame.core.config import AppConfig
from src.crazygame.core.database import Base, build_engine, build_session_factory
from src.crazygame.domain.models import AlertRule, Holding, Instrument
from src.crazygame.services.ai_context import AIContextService
from src.crazygame.services.ai_news import IntelItem
from src.crazygame.services.market import QuoteSnapshot


class FakeQuotes:
    def __init__(self, bars: list[Bar]):
        self.bars = bars

    def fetch_quotes(self, instruments):
        return {
            (instrument.symbol, instrument.market): QuoteSnapshot(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                current_price=250.0,
                change_pct=1.8,
                previous_close=245.6,
                as_of="2026-11-11T14:30:00+08:00",
                source="fixture",
                freshness="delayed",
            )
            for instrument in instruments
        }

    def fetch_bars(self, instrument, *, days=250):
        return self.bars[-days:]


class FakeNews:
    def fetch_for_instrument(self, instrument, *, concepts=None):
        return {
            "items": [
                IntelItem(
                    title=f"{instrument.name}发布公告",
                    summary="摘要",
                    url="https://example.test/news",
                    source="公司公告",
                    published_at=None,
                    relevance_kind="direct",
                    relevance_score=90,
                    relevance_reasons=("标题命中公司名",),
                )
            ],
            "industry": "电池",
            "concepts": concepts,
            "limitations": [],
        }


class FailingQuoteFetcher(FakeQuotes):
    def fetch_quotes(self, instruments):
        raise RuntimeError("quote provider unavailable")


class NullPriceQuoteFetcher(FakeQuotes):
    def fetch_quotes(self, instruments):
        return {
            key: QuoteSnapshot(
                symbol=quote.symbol,
                name=quote.name,
                market=quote.market,
                current_price=None,
                change_pct=quote.change_pct,
                previous_close=quote.previous_close,
                as_of=quote.as_of,
                source=quote.source,
                freshness=quote.freshness,
            )
            for key, quote in super().fetch_quotes(instruments).items()
        }


def make_factory(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'context.db'}",
        encryption_key="ai-context-test-secret-key-that-is-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    return engine, build_session_factory(engine)


def make_bars(count: int) -> list[Bar]:
    return [
        Bar(
            date=f"2026-{index // 28 + 1:02d}-{index % 28 + 1:02d}",
            open=float(index + 200),
            close=float(index + 200),
            high=float(index + 201),
            low=float(index + 199),
            volume=1_000.0 + index,
        )
        for index in range(count)
    ]


def test_context_includes_holding_alerts_technical_and_intel(tmp_path: Path):
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
        db.add(
            Holding(
                instrument_id=instrument.id,
                quantity=10,
                average_cost=220,
                note="核心持仓",
            )
        )
        db.add(
            AlertRule(
                instrument_id=instrument.id,
                name="突破提醒",
                metric="price",
                direction="above",
                threshold=260,
            )
        )
        db.commit()

        service = AIContextService(
            session_factory=factory,
            quote_service=FakeQuotes(make_bars(80)),
            news_service=FakeNews(),
        )
        context = service.build(instrument, language="zh-CN", include_news=True)

    assert context["quote"]["current_price"] == 250.0
    assert len(context["price_history"]) == 80
    assert context["price_history"][-1]["close"] == 279.0
    assert context["technical"]["bar_count"] == 80
    assert context["holding"]["quantity"] == 10
    assert context["holding"]["market_value"] == 2500.0
    assert context["alerts"][0]["threshold"] == 260
    assert context["hotspots"][0]["relevance_kind"] == "direct"
    assert context["data_quality"]["level"] == "good"
    engine.dispose()


def test_context_marks_short_history_limited(tmp_path: Path):
    engine, factory = make_factory(tmp_path)
    with factory() as db:
        instrument = Instrument(
            symbol="600519",
            name="贵州茅台",
            market="CN",
            asset_type="stock",
            currency="CNY",
            quote_mode="realtime",
        )
        db.add(instrument)
        db.commit()
        service = AIContextService(
            session_factory=factory,
            quote_service=FakeQuotes(make_bars(20)),
            news_service=FakeNews(),
        )
        context = service.build(instrument, language="zh-CN", include_news=True)

    assert context["data_quality"]["level"] == "limited"
    assert "history_under_60_days" in context["data_quality"]["limitations"]
    engine.dispose()


def test_context_degrades_when_quote_provider_fails(tmp_path: Path):
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
        db.commit()
        service = AIContextService(
            session_factory=factory,
            quote_service=FailingQuoteFetcher(make_bars(80)),
            news_service=FakeNews(),
        )
        context = service.build(instrument, language="zh-CN", include_news=True)

    assert context["quote"] == {}
    assert context["data_quality"]["level"] == "poor"
    assert "quote_unavailable" in context["data_quality"]["limitations"]
    engine.dispose()


def test_context_treats_missing_quote_price_as_poor_quality(tmp_path: Path):
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
        db.commit()
        service = AIContextService(
            session_factory=factory,
            quote_service=NullPriceQuoteFetcher(make_bars(80)),
            news_service=FakeNews(),
        )
        context = service.build(instrument, language="zh-CN", include_news=True)

    assert context["data_quality"]["level"] == "poor"
    assert "quote_price_missing" in context["data_quality"]["limitations"]
    engine.dispose()
