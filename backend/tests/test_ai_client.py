import json

import httpx

from src.crazygame.services.ai import (
    AIClient,
    parse_stream_content_delta,
    resolve_runtime_ai_client,
)
from src.crazygame.core.database import Base, build_engine, build_session_factory
from src.crazygame.core.config import AppConfig
from src.crazygame.core.secrets import SecretBox
from src.crazygame.domain.models import AppSetting


def test_tool_chat_returns_content_and_tool_calls(monkeypatch):
    def fake_post(url, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_market_snapshot",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    client = AIClient("https://example.test/v1", "secret", "fixture")

    message = client.tool_chat(
        [{"role": "user", "content": "分析宁德时代"}],
        [{"type": "function", "function": {"name": "get_market_snapshot"}}],
    )

    assert message["tool_calls"][0]["function"]["name"] == "get_market_snapshot"
    assert json.loads(message["tool_calls"][0]["function"]["arguments"]) == {}


def test_parse_stream_content_delta_reads_openai_sse_chunk():
    line = (
        'data: {"choices":[{"delta":{"content":"趋势偏强"}}]}'
    )

    assert parse_stream_content_delta(line) == "趋势偏强"
    assert parse_stream_content_delta("data: [DONE]") is None


def test_stream_text_emits_only_content_chunks(monkeypatch):
    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            return None

        def iter_lines(self):
            yield 'data: {"choices":[{"delta":{"content":"第一段"}}]}'
            yield 'data: {"choices":[{"delta":{"content":"，第二段"}}]}'
            yield "data: [DONE]"

    def fake_stream(*args, **kwargs):
        return FakeStream()

    monkeypatch.setattr(httpx, "stream", fake_stream)
    client = AIClient("https://example.test/v1", "secret", "fixture")

    assert "".join(client.stream_text([{"role": "user", "content": "分析"}])) == (
        "第一段，第二段"
    )


def test_capability_probe_reports_json_tools_stream_and_vision(monkeypatch):
    client = AIClient("https://example.test/v1", "secret", "fixture")
    monkeypatch.setattr(client, "complete", lambda *args, **kwargs: '{"ok":true}')
    monkeypatch.setattr(
        client,
        "tool_chat",
        lambda *args, **kwargs: {
            "tool_calls": [{"function": {"name": "capability_probe"}}]
        },
    )
    monkeypatch.setattr(client, "stream_text", lambda *args, **kwargs: iter(["ok"]))
    monkeypatch.setattr(client, "vision_json", lambda *args, **kwargs: '{"ok":true}')

    capabilities = client.capabilities()

    assert capabilities == {
        "json": True,
        "tools": True,
        "stream": True,
        "vision": True,
    }


def test_runtime_ai_prefers_saved_settings_over_stale_startup_client(tmp_path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'runtime-ai.db'}",
        encryption_key="runtime-ai-secret-key-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    secret_box = SecretBox(config.encryption_key)
    with factory() as db:
        db.add(
            AppSetting(
                key="ai",
                value=(
                    '{"base_url":"https://saved.test/v1","api_key":"'
                    + secret_box.encrypt("saved-key")
                    + '","model":"saved-model","vision_model":"saved-vision"}'
                ),
            )
        )
        db.commit()

    runtime = resolve_runtime_ai_client(
        session_factory=factory,
        secret_box=secret_box,
        fallback_base_url="https://env.test/v1",
        fallback_api_key="env-key",
        fallback_model="env-model",
        runtime_client=AIClient(
            "https://stale.test/v1",
            "stale-key",
            "stale-model",
        ),
    )

    assert runtime.base_url == "https://saved.test/v1"
    assert runtime.model == "saved-model"
    assert runtime.vision_model == "saved-vision"
    engine.dispose()
