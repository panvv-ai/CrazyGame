from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'channels.db'}",
            encryption_key="channel-api-test-secret-key-that-is-long-enough",
            enable_scheduler=False,
        )
    )
    client = TestClient(app)
    client.__enter__()
    return client


class FakeSender:
    def __init__(self):
        self.calls: list[dict] = []

    def send(self, channel_type, config, title, content, **_kwargs):
        self.calls.append(
            {
                "type": channel_type,
                "config": config,
                "title": title,
                "content": content,
            }
        )
        return True


def test_unsaved_channel_config_can_be_tested_without_persisting(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        sender = FakeSender()
        client.app.state.notification_sender = sender

        response = client.post(
            "/api/channels/test",
            json={
                "type": "feishu",
                "config": {
                    "webhook_url": "https://example.test/hook",
                    "secret": "test-secret",
                },
            },
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert sender.calls[0]["type"] == "feishu"
        assert sender.calls[0]["config"]["webhook_url"] == "https://example.test/hook"
        assert client.get("/api/channels").json()["items"] == []
    finally:
        client.__exit__(None, None, None)


def test_create_channel_persists_masked_config(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        response = client.post(
            "/api/channels",
            json={
                "name": "个人飞书",
                "type": "feishu",
                "config": {
                    "webhook_url": "https://example.test/hook",
                    "secret": "test-secret",
                },
                "enabled": True,
            },
        )

        assert response.status_code == 201
        created = response.json()
        assert created["name"] == "个人飞书"
        assert created["config"]["webhook_url"] != "https://example.test/hook"

        channels = client.get("/api/channels").json()["items"]
        assert len(channels) == 1
        assert channels[0]["type"] == "feishu"
        assert channels[0]["enabled"] is True
    finally:
        client.__exit__(None, None, None)
