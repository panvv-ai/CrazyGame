from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.domain.models import Instrument
from src.crazygame.services.ai import AIClient


def unauthorized_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/chat/completions")
    response = httpx.Response(401, request=request)
    return httpx.HTTPStatusError(
        "401 Authorization Required",
        request=request,
        response=response,
    )


def make_client(tmp_path: Path) -> tuple[TestClient, int]:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'ai-config.db'}",
            encryption_key="ai-config-test-secret-key-that-is-long-enough",
            enable_scheduler=False,
        )
    )
    client = TestClient(app)
    client.__enter__()
    with app.state.session_factory() as db:
        instrument = Instrument(
            symbol="NVDA",
            name="英伟达",
            market="US",
            asset_type="stock",
            currency="USD",
            quote_mode="realtime",
        )
        db.add(instrument)
        db.commit()
        db.refresh(instrument)
        instrument_id = instrument.id
    return client, instrument_id


def parse_events(text: str) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_capability_probe_identifies_authentication_failure(monkeypatch):
    client = AIClient(
        "https://example.test",
        "invalid-key",
        "deepseek-flash",
        "deepseek-flash",
    )

    def fail(*_args, **_kwargs):
        raise unauthorized_error()

    monkeypatch.setattr(client, "complete", fail)
    monkeypatch.setattr(client, "tool_chat", fail)
    monkeypatch.setattr(client, "stream_text", fail)
    monkeypatch.setattr(client, "vision_json", fail)

    result = client.capabilities()

    assert result["ok"] is False
    assert result["code"] == "ai_auth_failed"
    assert result["json"] is False


def test_ai_capability_endpoint_rejects_fully_failed_probe(tmp_path: Path):
    client, _instrument_id = make_client(tmp_path)
    try:
        class FailedAI:
            def capabilities(self):
                return {
                    "json": False,
                    "tools": False,
                    "stream": False,
                    "vision": False,
                    "ok": False,
                    "code": "ai_auth_failed",
                }

        client.app.state.ai = FailedAI()

        response = client.post("/api/settings/ai/test")

        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "ai_auth_failed"
    finally:
        client.__exit__(None, None, None)


def test_chat_stream_reports_authentication_failure_code(tmp_path: Path, monkeypatch):
    client, instrument_id = make_client(tmp_path)
    try:
        class FakeContextService:
            def build(self, instrument, *, language, include_news=True):
                return {
                    "instrument": {
                        "id": instrument.id,
                        "symbol": instrument.symbol,
                        "name": instrument.name,
                        "market": instrument.market,
                        "asset_type": instrument.asset_type,
                    },
                    "quote": {},
                    "price_history": [],
                    "technical": {},
                    "holding": None,
                    "alerts": [],
                    "hotspots": [],
                    "latest_report": None,
                    "data_quality": {},
                }

        class UnauthorizedAI:
            def tool_chat(self, messages, tools, *, timeout):
                raise unauthorized_error()

            def stream_text(self, messages, *, timeout):
                raise unauthorized_error()

        client.app.state.ai_context_service = FakeContextService()
        client.app.state.ai = UnauthorizedAI()
        monkeypatch.setattr(
            "src.crazygame.api.routes.ai._news_enabled",
            lambda _request: False,
        )

        response = client.post(
            "/api/ai/chat/stream",
            json={"message": "英伟达现在合适入手建仓吗？", "instrument_id": instrument_id},
        )
        events = parse_events(response.text)

        assert response.status_code == 200
        assert events[-1]["type"] == "error"
        assert events[-1]["code"] == "ai_auth_failed"
    finally:
        client.__exit__(None, None, None)
