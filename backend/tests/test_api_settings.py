from pathlib import Path

from fastapi.testclient import TestClient
from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.domain.models import AppSetting, NotifyChannel


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'settings.db'}",
            encryption_key="settings-test-secret-key-that-is-long-enough",
        )
    )
    return TestClient(app)


def test_settings_redact_ai_api_key(tmp_path: Path):
    with make_client(tmp_path) as client:
        saved = client.put(
            "/api/settings",
            json={
                "language": "en-US",
                "ai": {
                    "base_url": "https://example.test/v1",
                    "api_key": "super-secret",
                    "model": "demo-model",
                },
            },
        )
        loaded = client.get("/api/settings")

        assert saved.status_code == 200
        assert saved.json()["language"] == "en-US"
        assert saved.json()["ai"]["api_key"] == "••••••••"
        assert loaded.json()["ai"]["api_key"] == "••••••••"


def test_settings_persist_vision_model_and_redact_news_search_key(tmp_path: Path):
    with make_client(tmp_path) as client:
        saved = client.put(
            "/api/settings",
            json={
                "language": "zh-CN",
                "ai": {
                    "base_url": "https://example.test/v1",
                    "api_key": "main-secret",
                    "model": "text-model",
                    "vision_model": "vision-model",
                },
                "news": {
                    "enabled": True,
                    "provider": "bocha",
                    "api_key": "search-secret",
                },
            },
        )

        assert saved.status_code == 200
        assert saved.json()["ai"]["vision_model"] == "vision-model"
        assert saved.json()["news"] == {
            "enabled": True,
            "provider": "bocha",
            "api_key": "••••••••",
        }
        with client.app.state.session_factory() as db:
            saved_settings = {
                row.key: row.value
                for row in db.query(AppSetting).all()
            }
        assert "search-secret" not in saved_settings["news"]


def test_channel_secret_is_encrypted_at_rest_and_masked(tmp_path: Path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/channels",
            json={
                "name": "我的飞书",
                "type": "feishu",
                "config": {
                    "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/secret",
                    "secret": "signing-secret",
                },
            },
        )

        assert response.status_code == 201
        assert response.json()["config"]["webhook_url"] == "••••••••"
        assert response.json()["config"]["secret"] == "••••••••"

        app = client.app
        factory = app.state.session_factory
        with factory() as db:
            row = db.query(NotifyChannel).one()
            assert "open.feishu.cn" not in row.config_encrypted
            assert "signing-secret" not in row.config_encrypted


def test_ai_capability_endpoint_uses_configured_client(tmp_path: Path):
    with make_client(tmp_path) as client:
        client.app.state.ai = type(
            "CapabilityAI",
            (),
            {
                "capabilities": lambda self: {
                    "json": True,
                    "tools": True,
                    "stream": False,
                    "vision": True,
                }
            },
        )()

        response = client.post("/api/settings/ai/test")

        assert response.status_code == 200
        assert response.json()["tools"] is True
        assert response.json()["stream"] is False

