from pathlib import Path

from fastapi.testclient import TestClient
from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig


def test_business_routes_are_available_without_login(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'local.db'}",
            encryption_key="local-test-encryption-key",
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/watchlist")

        assert response.status_code == 200
        assert response.json() == {"items": []}


def test_auth_routes_are_not_exposed(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'local.db'}",
            encryption_key="local-test-encryption-key",
        )
    )

    with TestClient(app) as client:
        assert client.get("/api/auth/status").status_code == 404
