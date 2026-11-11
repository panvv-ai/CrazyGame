from __future__ import annotations

import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.domain.models import AppSetting
from src.crazygame.services.ai import AIClient, resolve_runtime_ai_client
from src.crazygame.services.ai_agent import AIAgentRunner
from src.crazygame.services.ai_news import NewsService


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'ai-regressions.db'}",
            encryption_key="ai-regression-test-secret-key-long-enough",
            enable_scheduler=False,
        )
    )
    client = TestClient(app)
    client.__enter__()
    return client


def minimal_context() -> dict:
    return {
        "instrument": {
            "id": 1,
            "symbol": "NVDA",
            "name": "英伟达",
            "market": "US",
            "asset_type": "stock",
        },
        "quote": {"current_price": 200},
        "price_history": [],
        "technical": {},
        "holding": None,
        "alerts": [],
        "hotspots": [],
        "latest_report": None,
        "data_quality": {},
    }


class RecordingToolAI:
    def __init__(self):
        self.calls: list[list[dict]] = []

    def tool_chat(self, messages, tools, *, timeout):
        self.calls.append(copy.deepcopy(messages))
        if len(self.calls) == 1:
            return {
                "role": "assistant",
                "content": "",
                "reasoning_content": "先读取服务端绑定的行情工具。",
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
        return {
            "role": "assistant",
            "content": "证据已足够。",
            "reasoning_content": "可以开始整理最终结论。",
        }


def run_tool_round() -> RecordingToolAI:
    ai = RecordingToolAI()
    runner = AIAgentRunner(
        ai_client=ai,
        context=minimal_context(),
        language="zh-CN",
    )
    runner.prepare("英伟达现在合适入手建仓吗？", history=[])
    return ai


def test_saving_masked_ai_key_does_not_encrypt_existing_ciphertext(tmp_path: Path):
    client = make_client(tmp_path)
    key = "sk-test-deepseek-official-key"
    try:
        first = client.put(
            "/api/settings",
            json={
                "language": "zh-CN",
                "ai": {
                    "base_url": "https://api.deepseek.com",
                    "api_key": key,
                    "model": "deepseek-flash",
                    "vision_model": "deepseek-flash",
                },
            },
        )
        assert first.status_code == 200
        assert first.json()["ai"]["api_key"] == "••••••••"

        second = client.put("/api/settings", json=first.json())

        assert second.status_code == 200
        with client.app.state.session_factory() as db:
            stored = json.loads(db.get(AppSetting, "ai").value)
        assert client.app.state.secret_box.decrypt(stored["api_key"]) == key
    finally:
        client.__exit__(None, None, None)


def test_runtime_ai_unwraps_legacy_nested_key_and_rewrites_one_layer(tmp_path: Path):
    client = make_client(tmp_path)
    key = "sk-test-deepseek-official-key"
    nested = key
    for _ in range(4):
        nested = client.app.state.secret_box.encrypt(nested)
    with client.app.state.session_factory() as db:
        db.add(
            AppSetting(
                key="ai",
                value=json.dumps(
                    {
                        "base_url": "https://api.deepseek.com",
                        "api_key": nested,
                        "model": "deepseek-flash",
                        "vision_model": "deepseek-flash",
                    }
                ),
            )
        )
        db.commit()
    try:
        runtime = resolve_runtime_ai_client(
            session_factory=client.app.state.session_factory,
            secret_box=client.app.state.secret_box,
            fallback_base_url="https://fallback.test",
            fallback_api_key="fallback-key",
            fallback_model="fallback-model",
            runtime_client=None,
        )

        assert runtime.api_key == key
        with client.app.state.session_factory() as db:
            stored = json.loads(db.get(AppSetting, "ai").value)
        assert client.app.state.secret_box.decrypt(stored["api_key"]) == key
    finally:
        client.__exit__(None, None, None)


def test_tool_history_preserves_deepseek_reasoning_content():
    ai = run_tool_round()

    assistant_message = ai.calls[1][-2]

    assert assistant_message["role"] == "assistant"
    assert assistant_message["reasoning_content"] == "先读取服务端绑定的行情工具。"


def test_tool_result_uses_documented_fields_only():
    ai = run_tool_round()

    tool_message = ai.calls[1][-1]

    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert "name" not in tool_message


def test_ai_client_normalizes_configuration_whitespace():
    client = AIClient(
        " https://api.deepseek.com/ ",
        " sk-test-key\n",
        " deepseek-flash ",
        " deepseek-flash ",
    )

    assert client.base_url == "https://api.deepseek.com"
    assert client.api_key == "sk-test-key"
    assert client.model == "deepseek-flash"
    assert client.vision_model == "deepseek-flash"


def test_ai_client_accepts_the_documented_chat_completions_url_as_base_url():
    client = AIClient(
        "https://api.deepseek.com/chat/completions",
        "sk-test-key",
        "deepseek-flash",
    )

    assert client.base_url == "https://api.deepseek.com"


def test_ai_capability_endpoint_tests_submitted_form_values(
    tmp_path: Path,
    monkeypatch,
):
    client = make_client(tmp_path)
    captured: dict[str, str] = {}

    def capabilities(ai_client):
        captured.update(
            {
                "base_url": ai_client.base_url,
                "api_key": ai_client.api_key,
                "model": ai_client.model,
                "vision_model": ai_client.vision_model,
            }
        )
        return {
            "json": True,
            "tools": True,
            "stream": True,
            "vision": True,
            "ok": True,
            "code": "",
            "errors": {},
        }

    monkeypatch.setattr(AIClient, "capabilities", capabilities)
    try:
        response = client.post(
            "/api/settings/ai/test",
            json={
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-current-form-key",
                "model": "deepseek-flash",
                "vision_model": "deepseek-flash",
            },
        )

        assert response.status_code == 200
        assert captured == {
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-current-form-key",
            "model": "deepseek-flash",
            "vision_model": "deepseek-flash",
        }
    finally:
        client.__exit__(None, None, None)


def test_news_provider_unwraps_legacy_nested_key(tmp_path: Path):
    client = make_client(tmp_path)
    key = "news-test-key"
    nested = client.app.state.secret_box.encrypt(
        client.app.state.secret_box.encrypt(key)
    )
    with client.app.state.session_factory() as db:
        db.add(
            AppSetting(
                key="news",
                value=json.dumps(
                    {
                        "enabled": True,
                        "provider": "bocha",
                        "api_key": nested,
                    }
                ),
            )
        )
        db.commit()
    try:
        service = NewsService(
            client.app.state.session_factory,
            secret_box=client.app.state.secret_box,
        )

        config = service._provider_config()

        assert config["api_key"] == key
    finally:
        client.__exit__(None, None, None)
