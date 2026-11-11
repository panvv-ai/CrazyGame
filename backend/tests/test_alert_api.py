from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.domain.models import AlertRule, Instrument
from src.crazygame.services.alert_service import AlertScanner
from src.crazygame.services.market import QuoteSnapshot


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'alerts.db'}",
            encryption_key="alert-api-test-secret-key-that-is-long-enough",
            enable_scheduler=False,
        )
    )
    client = TestClient(app)
    client.__enter__()
    return client


def seed_alert(client: TestClient) -> tuple[int, int]:
    with client.app.state.session_factory() as db:
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
        rule = AlertRule(
            instrument_id=instrument.id,
            name="突破提醒",
            metric="price",
            direction="above",
            threshold=420,
            channel_ids=json.dumps([1]),
            enabled=True,
            once_per_day=True,
            market_hours_only=True,
            cooldown_minutes=30,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return instrument.id, rule.id


class FakeQuoteService:
    def fetch_quotes(self, instruments):
        return {
            (instrument.symbol, instrument.market): QuoteSnapshot(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                current_price=412.6,
                change_pct=4.06,
                previous_close=396.5,
                as_of="2026-11-11T15:06:00+08:00",
                source="test",
                freshness="live",
            )
            for instrument in instruments
        }


def test_list_alerts_includes_instrument_name_and_quote(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        _instrument_id, _rule_id = seed_alert(client)
        client.app.state.quote_service = FakeQuoteService()

        response = client.get("/api/alerts")

        assert response.status_code == 200
        rule = response.json()["items"][0]
        assert rule["instrument_name"] == "宁德时代"
        assert rule["quote"]["current_price"] == 412.6
        assert rule["quote"]["freshness"] == "live"
    finally:
        client.__exit__(None, None, None)


def test_patch_alert_updates_rule_fields(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        instrument_id, rule_id = seed_alert(client)

        response = client.patch(
            f"/api/alerts/{rule_id}",
            json={
                "name": "回踩观察",
                "metric": "change_pct",
                "direction": "below",
                "threshold": -2,
                "channel_ids": [2, 3],
                "once_per_day": False,
                "market_hours_only": False,
                "cooldown_minutes": 15,
            },
        )

        assert response.status_code == 200
        updated = response.json()
        assert updated["instrument_id"] == instrument_id
        assert updated["name"] == "回踩观察"
        assert updated["metric"] == "change_pct"
        assert updated["direction"] == "below"
        assert updated["threshold"] == -2
        assert updated["channel_ids"] == [2, 3]
        assert updated["once_per_day"] is False
        assert updated["market_hours_only"] is False
        assert updated["cooldown_minutes"] == 15
    finally:
        client.__exit__(None, None, None)


def test_alert_id_is_not_overwritten_by_instrument_id(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        _instrument_id, _rule_id = seed_alert(client)
        with client.app.state.session_factory() as db:
            first_extra = Instrument(
                symbol="AAPL",
                name="苹果",
                market="US",
                asset_type="stock",
                currency="USD",
                quote_mode="realtime",
            )
            second_extra = Instrument(
                symbol="MSFT",
                name="微软",
                market="US",
                asset_type="stock",
                currency="USD",
                quote_mode="realtime",
            )
            db.add_all([first_extra, second_extra])
            db.flush()
            rule = AlertRule(
                instrument_id=second_extra.id,
                name="微软提醒",
                metric="price",
                direction="above",
                threshold=500,
                channel_ids=json.dumps([]),
                enabled=True,
                once_per_day=True,
                market_hours_only=True,
                cooldown_minutes=30,
            )
            db.add(rule)
            db.commit()
            expected_rule_id = rule.id
            expected_instrument_id = second_extra.id

        client.app.state.quote_service = FakeQuoteService()
        payload = client.get("/api/alerts").json()["items"]
        target = next(item for item in payload if item["name"] == "微软提醒")

        assert target["id"] == expected_rule_id
        assert target["instrument_id"] == expected_instrument_id
        assert target["id"] != target["instrument_id"]
    finally:
        client.__exit__(None, None, None)


def test_create_alert_can_check_and_execute_immediately(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        instrument_id, _rule_id = seed_alert(client)
        client.app.state.quote_service = FakeQuoteService()

        response = client.post(
            "/api/alerts",
            json={
                "instrument_id": instrument_id,
                "name": "立即检查",
                "metric": "price",
                "direction": "above",
                "threshold": 400,
                "channel_ids": [],
                "market_hours_only": False,
                "once_per_day": False,
                "cooldown_minutes": 0,
                "run_now": True,
            },
        )

        assert response.status_code == 201
        assert response.json()["run_result"]["scan"]["triggered"] == 1
        hits = client.get("/api/alerts/hits").json()["items"]
        assert any(hit["rule_name"] == "立即检查" for hit in hits)
    finally:
        client.__exit__(None, None, None)


def test_concurrent_scans_trigger_rule_only_once(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        _instrument_id, rule_id = seed_alert(client)
        with client.app.state.session_factory() as db:
            rule = db.get(AlertRule, rule_id)
            rule.threshold = 400
            rule.once_per_day = True
            rule.market_hours_only = False
            db.commit()

        gate = threading.Lock()
        in_flight = 0
        max_in_flight = 0

        class SlowQuoteService:
            def fetch_quotes(self, instruments):
                nonlocal in_flight, max_in_flight
                with gate:
                    in_flight += 1
                    max_in_flight = max(max_in_flight, in_flight)
                time.sleep(0.12)
                with gate:
                    in_flight -= 1
                return FakeQuoteService().fetch_quotes(instruments)

        client.app.state.quote_service = SlowQuoteService()
        scanners = [
            AlertScanner(
                client.app.state.session_factory,
                client.app.state.quote_service,
                client.app.state.secret_box,
            )
            for _ in range(2)
        ]
        now = datetime(2026, 11, 11, 16, 35, tzinfo=timezone.utc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda scanner: scanner.scan_rule(rule_id, now=now), scanners))

        assert max_in_flight == 1
        assert sum(result["triggered"] for result in results) == 1
        hits = client.get("/api/alerts/hits").json()["items"]
        assert len([hit for hit in hits if hit["rule_id"] == rule_id]) == 1
    finally:
        client.__exit__(None, None, None)
