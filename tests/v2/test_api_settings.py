from pathlib import Path

from fastapi.testclient import TestClient

from src.panwatch.app import create_app
from src.panwatch.config import AppConfig
from src.panwatch.models import NotifyChannel


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'settings.db'}",
            enable_auth=False,
            secret_key="settings-test-secret-key-that-is-long-enough",
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

