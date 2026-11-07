from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from src.panwatch.api.app import create_app
from src.panwatch.core.config import AppConfig
from src.panwatch.services.alert_service import AlertScanner
from src.panwatch.services.market import QuoteSnapshot


class FakeQuotes:
    def fetch_quotes(self, instruments):
        return {
            (instrument.symbol, instrument.market): QuoteSnapshot(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                current_price=210.0,
                change_pct=5.0,
                previous_close=200.0,
                as_of="2026-11-06T15:00:00+00:00",
                source="fixture",
                freshness="live",
            )
            for instrument in instruments
        }


class FakeSender:
    def send(self, channel_type, config, title, content, context=None):
        return True


def test_alert_rule_can_be_created_and_listed(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'alerts.db'}",
            encryption_key="alerts-test-secret-key-long-enough",
        )
    )
    with TestClient(app) as client:
        item = client.post(
            "/api/watchlist",
            json={
                "symbol": "AAPL",
                "name": "Apple",
                "market": "US",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        channel = client.post(
            "/api/channels",
            json={
                "name": "Feishu",
                "type": "feishu",
                "config": {"webhook_url": "https://example.test/hook"},
            },
        ).json()

        created = client.post(
            "/api/alerts",
            json={
                "instrument_id": item["instrument_id"],
                "name": "AAPL above 200",
                "metric": "price",
                "direction": "above",
                "threshold": 200,
                "channel_ids": [channel["id"]],
            },
        )
        listed = client.get("/api/alerts")

        assert created.status_code == 201
        assert created.json()["metric"] == "price"
        assert listed.json()["items"][0]["name"] == "AAPL above 200"


def test_alert_hits_and_channel_test_are_exposed(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'alert-hits.db'}",
            encryption_key="alerts-hit-secret-key-long-enough",
        )
    )
    app.state.quote_service = FakeQuotes()
    app.state.notification_sender = FakeSender()
    with TestClient(app) as client:
        item = client.post(
            "/api/watchlist",
            json={
                "symbol": "AAPL",
                "name": "Apple",
                "market": "US",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        channel = client.post(
            "/api/channels",
            json={
                "name": "Feishu",
                "type": "feishu",
                "config": {"webhook_url": "https://example.test/hook"},
            },
        ).json()
        client.post(
            "/api/alerts",
            json={
                "instrument_id": item["instrument_id"],
                "name": "Breakout",
                "metric": "price",
                "direction": "above",
                "threshold": 200,
                "channel_ids": [channel["id"]],
            },
        )
        AlertScanner(
            session_factory=app.state.session_factory,
            quote_service=app.state.quote_service,
            secret_box=app.state.secret_box,
        ).scan_once(now=datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc))

        hits = client.get("/api/alerts/hits")
        tested = client.post(f"/api/channels/{channel['id']}/test")

        assert hits.status_code == 200
        assert hits.json()["items"][0]["rule_name"] == "Breakout"
        assert tested.status_code == 200
        assert tested.json()["ok"] is True


def test_alert_can_be_disabled(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'alert-toggle.db'}",
            encryption_key="alert-toggle-secret-key-long-enough",
        )
    )
    with TestClient(app) as client:
        item = client.post(
            "/api/watchlist",
            json={
                "symbol": "AAPL",
                "name": "Apple",
                "market": "US",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        rule = client.post(
            "/api/alerts",
            json={
                "instrument_id": item["instrument_id"],
                "name": "Breakout",
                "metric": "price",
                "direction": "above",
                "threshold": 200,
            },
        ).json()

        response = client.patch(
            f"/api/alerts/{rule['id']}",
            json={"enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False

