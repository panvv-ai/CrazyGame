from datetime import date
from pathlib import Path

from src.panwatch.core.config import AppConfig
from src.panwatch.core.database import Base, build_engine, build_session_factory
from src.panwatch.domain.models import AppSetting, DailyReview, Holding, Instrument
from src.panwatch.services.ai import resolve_ai_client
from src.panwatch.services.daily_review import DailyReviewService
from src.panwatch.services.market import QuoteSnapshot


class FakeQuotes:
    def fetch_quotes(self, instruments):
        return {
            (instrument.symbol, instrument.market): QuoteSnapshot(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                current_price=110.0,
                change_pct=10.0,
                previous_close=100.0,
                as_of="2026-11-06T15:00:00+08:00",
                source="fixture",
                freshness="live",
            )
            for instrument in instruments
        }

    def fetch_daily_points(self, instrument, *, days=365):
        return [(date(2026, 11, 5), 100.0), (date(2026, 11, 6), 110.0)]


class FakeAI:
    def __init__(self):
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return "# 持仓健康\n\n组合保持稳定，建议继续观察。"


def make_db(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'review.db'}",
        encryption_key="daily-review-secret-key-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    return engine, factory


def test_daily_review_skips_without_holdings(tmp_path: Path):
    engine, factory = make_db(tmp_path)
    service = DailyReviewService(session_factory=factory, quote_service=FakeQuotes(), ai=FakeAI())

    result = service.generate(trade_date=date(2026, 11, 6))

    assert result["status"] == "skipped"
    engine.dispose()


def test_daily_review_persists_localized_ai_output(tmp_path: Path):
    engine, factory = make_db(tmp_path)
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
        db.flush()
        db.add(Holding(instrument_id=instrument.id, quantity=10, average_cost=90))
        db.add(AppSetting(key="language", value="zh-CN"))
        db.commit()
    ai = FakeAI()
    service = DailyReviewService(session_factory=factory, quote_service=FakeQuotes(), ai=ai)

    result = service.generate(trade_date=date(2026, 11, 6))

    with factory() as db:
        review = db.query(DailyReview).one()
        assert result["status"] == "success"
        assert review.language == "zh-CN"
        assert "持仓健康" in review.content
        assert "中文" in ai.messages[1]["content"]
    engine.dispose()


def test_resolve_ai_client_returns_none_without_configured_key(tmp_path: Path):
    engine, factory = make_db(tmp_path)

    result = resolve_ai_client(
        session_factory=factory,
        secret_box=None,
        fallback_base_url="https://example.test/v1",
        fallback_api_key="",
        fallback_model="demo",
    )

    assert result is None
    engine.dispose()


def test_successful_daily_review_is_not_regenerated_on_retry(tmp_path: Path):
    engine, factory = make_db(tmp_path)
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
        db.flush()
        db.add(Holding(instrument_id=instrument.id, quantity=10, average_cost=90))
        db.commit()
    ai = FakeAI()
    service = DailyReviewService(session_factory=factory, quote_service=FakeQuotes(), ai=ai)

    first = service.generate(trade_date=date(2026, 11, 6))
    first_messages = ai.messages
    second = service.generate(trade_date=date(2026, 11, 6))

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert ai.messages is first_messages
    engine.dispose()

