from datetime import datetime, timezone
from pathlib import Path

from src.panwatch.alert_service import AlertScanner, DeliveryWorker
from src.panwatch.config import AppConfig
from src.panwatch.database import Base, build_engine, build_session_factory
from src.panwatch.market import QuoteSnapshot
from src.panwatch.models import (
    AlertRule,
    Instrument,
    NotificationDelivery,
    NotifyChannel,
)
from src.panwatch.secrets import SecretBox


class FakeQuotes:
    def fetch_quotes(self, instruments):
        return {
            (instrument.symbol, instrument.market): QuoteSnapshot(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                current_price=205.0,
                change_pct=2.5,
                previous_close=200.0,
                as_of="2026-11-06T15:00:00+00:00",
                source="fixture",
                freshness="live",
            )
            for instrument in instruments
        }


class FakeSender:
    def __init__(self):
        self.calls = []

    def send(self, channel_type, config, title, content, context=None):
        self.calls.append((channel_type, config, title, content))
        return True


def make_db(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'alerts-scan.db'}",
        secret_key="scanner-test-secret-key-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    box = SecretBox(config.secret_key)
    with factory() as db:
        instrument = Instrument(
            symbol="AAPL",
            name="Apple",
            market="US",
            asset_type="stock",
            currency="USD",
            quote_mode="realtime",
        )
        channel = NotifyChannel(
            name="Feishu",
            type="feishu",
            config_encrypted=box.encrypt(
                '{"webhook_url":"https://example.test/hook"}'
            ),
        )
        db.add_all([instrument, channel])
        db.flush()
        db.add(
            AlertRule(
                instrument_id=instrument.id,
                name="AAPL above 200",
                metric="price",
                direction="above",
                threshold=200.0,
                channel_ids=f"[{channel.id}]",
            )
        )
        db.commit()
    return engine, factory, box


def test_alert_scanner_creates_one_hit_and_delivery_per_day(tmp_path: Path):
    engine, factory, box = make_db(tmp_path)
    scanner = AlertScanner(
        session_factory=factory,
        quote_service=FakeQuotes(),
        secret_box=box,
    )
    moment = datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)

    first = scanner.scan_once(now=moment)
    second = scanner.scan_once(now=moment)

    with factory() as db:
        assert first["triggered"] == 1
        assert second["triggered"] == 0
        assert db.query(NotificationDelivery).count() == 1
    engine.dispose()


def test_delivery_worker_marks_successful_delivery(tmp_path: Path):
    engine, factory, box = make_db(tmp_path)
    AlertScanner(session_factory=factory, quote_service=FakeQuotes(), secret_box=box).scan_once(
        now=datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc)
    )
    sender = FakeSender()
    worker = DeliveryWorker(session_factory=factory, secret_box=box, sender=sender)

    result = worker.drain()

    with factory() as db:
        delivery = db.query(NotificationDelivery).one()
        assert result["processed"] == 1
        assert delivery.status == "delivered"
        assert sender.calls[0][0] == "feishu"
    engine.dispose()

