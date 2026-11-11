import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.domain.models import Instrument


def fixture_context(instrument):
    return {
        "instrument": {
            "id": instrument.id,
            "symbol": instrument.symbol,
            "name": instrument.name,
            "market": instrument.market,
            "asset_type": instrument.asset_type,
        },
        "quote": {
            "current_price": 250,
            "change_pct": 1.8,
            "as_of": "2026-11-11T14:30:00+08:00",
            "source": "fixture",
            "freshness": "delayed",
        },
        "technical": {"bar_count": 80, "ma": {"alignment": "bullish"}},
        "holding": None,
        "alerts": [],
        "industry": "电池",
        "concepts": ["新能源"],
        "hotspots": [],
        "latest_report": None,
        "data_quality": {
            "level": "limited",
            "limitations": [],
            "quote_as_of": "2026-11-11T14:30:00+08:00",
            "quote_source": "fixture",
            "quote_freshness": "delayed",
        },
    }


class FakeContextService:
    def build(self, instrument, *, language, include_news=True):
        return fixture_context(instrument)


VALID_REPORT = {
    "score": 72,
    "verdict": "bullish",
    "confidence": "high",
    "core_conclusion": "趋势偏强，等待量能确认。",
    "trend": "均线多头排列",
    "hotspots": [],
    "risks": ["高位波动"],
    "catalysts": ["储能需求"],
    "position_advice": {
        "no_position": "等待回踩",
        "has_position": "持有观察",
    },
    "price_plan": {"support": 240, "resistance": 270},
    "action_checklist": ["检查量能"],
    "data_quality": {"level": "limited", "limitations": ["news unavailable"]},
}


class FakeAI:
    model = "fixture-model"

    def tool_chat(self, messages, tools, *, timeout=None):
        return {"role": "assistant", "content": "已整理数据"}

    def stream_text(self, messages, *, timeout=None):
        yield "趋势偏强，"
        yield "等待量能确认。"

    def complete(self, messages, **kwargs):
        return json.dumps(VALID_REPORT, ensure_ascii=False)

    def vision_json(self, image_bytes, mime_type, prompt, *, timeout):
        return '[{"code":"300750","name":"宁德时代","confidence":"high"}]'


def make_client(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'ai-api.db'}",
            encryption_key="ai-api-test-secret-key-that-is-long-enough",
            enable_scheduler=False,
        )
    )
    client = TestClient(app)
    client.__enter__()
    app.state.ai_context_service = FakeContextService()
    app.state.ai = FakeAI()
    with app.state.session_factory() as db:
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
        db.refresh(instrument)
        instrument_id = instrument.id
    return client, instrument_id


def parse_events(text: str) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_chat_stream_emits_accepted_delta_done_and_persists_session(tmp_path: Path):
    client, instrument_id = make_client(tmp_path)
    try:
        response = client.post(
            "/api/ai/chat/stream",
            json={
                "message": "分析一下趋势",
                "instrument_id": instrument_id,
            },
        )
        events = parse_events(response.text)

        assert response.status_code == 200
        assert events[0]["type"] == "accepted"
        assert events[0]["active_instrument"]["symbol"] == "300750"
        assert len({event["request_id"] for event in events}) == 1
        assert "".join(
            event.get("content", "") for event in events if event["type"] == "delta"
        ) == "趋势偏强，等待量能确认。"
        assert events[-1]["type"] == "done"
        session_id = events[0]["session_id"]

        sessions = client.get("/api/ai/chat/sessions").json()["items"]
        detail = client.get(f"/api/ai/chat/sessions/{session_id}").json()
        assert sessions[0]["id"] == session_id
        assert [message["role"] for message in detail["messages"]] == [
            "user",
            "assistant",
        ]
        assert detail["active_instrument"]["name"] == "宁德时代"
    finally:
        client.__exit__(None, None, None)


def test_chat_stream_requests_instrument_when_none_can_be_resolved(tmp_path: Path):
    client, _instrument_id = make_client(tmp_path)
    try:
        response = client.post(
            "/api/ai/chat/stream",
            json={"message": "最近市场怎么样"},
        )
        events = parse_events(response.text)

        assert events[0]["type"] == "accepted"
        assert events[-1]["type"] == "clarification"
        assert "股票代码" in events[-1]["message"]
    finally:
        client.__exit__(None, None, None)


def test_report_stream_generates_and_lists_structured_report(tmp_path: Path):
    client, instrument_id = make_client(tmp_path)
    try:
        response = client.post(
            "/api/ai/reports/stream",
            json={"instrument_id": instrument_id},
        )
        events = parse_events(response.text)

        assert response.status_code == 200
        assert events[0]["type"] == "accepted"
        assert len({event["request_id"] for event in events}) == 1
        assert [event["stage"] for event in events if event["type"] == "stage"][
            :2
        ] == ["context", "generate"]
        assert events[-1]["type"] == "done"
        assert events[-1]["report"]["confidence"] == "medium"

        items = client.get(
            f"/api/ai/reports?instrument_id={instrument_id}"
        ).json()["items"]
        assert len(items) == 1
        assert items[0]["status"] == "success"
        assert items[0]["report"]["verdict"] == "bullish"
        report_id = items[0]["id"]
        detail = client.get(f"/api/ai/reports/{report_id}")
        assert detail.status_code == 200
        assert detail.json()["score"] == 72
        deleted = client.delete(f"/api/ai/reports/{report_id}")
        assert deleted.status_code == 200
        assert client.get(f"/api/ai/reports/{report_id}").status_code == 404
    finally:
        client.__exit__(None, None, None)


def test_recognize_image_returns_confirmed_candidates_without_persisting(
    tmp_path: Path,
    monkeypatch,
):
    client, _instrument_id = make_client(tmp_path)
    try:
        from src.crazygame.api.routes import market as market_routes

        monkeypatch.setattr(
            market_routes,
            "search_instruments",
            lambda query, **kwargs: [
                type(
                    "Candidate",
                    (),
                    {
                        "symbol": "300750",
                        "name": "宁德时代",
                        "market": "CN",
                        "asset_type": "stock",
                        "currency": "CNY",
                        "quote_mode": "realtime",
                    },
                )()
            ],
        )
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
        response = client.post(
            "/api/instruments/recognize-image",
            files={"file": ("watchlist.png", png, "image/png")},
        )

        assert response.status_code == 200
        assert response.json()["items"][0]["instrument"]["symbol"] == "300750"
        with client.app.state.session_factory() as db:
            assert db.query(Instrument).count() == 1
    finally:
        client.__exit__(None, None, None)


def test_chat_stream_reports_ai_configuration_error(tmp_path: Path):
    client, instrument_id = make_client(tmp_path)
    try:
        client.app.state.ai = None
        response = client.post(
            "/api/ai/chat/stream",
            json={"message": "分析一下", "instrument_id": instrument_id},
        )
        events = parse_events(response.text)

        assert events[0]["type"] == "accepted"
        assert events[-1]["type"] == "error"
        assert events[-1]["code"] == "ai_not_configured"
    finally:
        client.__exit__(None, None, None)


def test_recognize_image_rejects_forged_mime_type(tmp_path: Path):
    client, _instrument_id = make_client(tmp_path)
    try:
        response = client.post(
            "/api/instruments/recognize-image",
            files={"file": ("fake.png", b"not a png", "image/png")},
        )

        assert response.status_code == 400
    finally:
        client.__exit__(None, None, None)
