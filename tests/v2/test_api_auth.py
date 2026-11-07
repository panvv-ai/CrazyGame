from pathlib import Path

from fastapi.testclient import TestClient

from src.panwatch.app import create_app
from src.panwatch.config import AppConfig


def test_auth_setup_protects_business_routes(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'auth.db'}",
            enable_auth=True,
            secret_key="auth-test-secret-key-that-is-long-enough",
        )
    )

    with TestClient(app) as client:
        assert client.get("/api/auth/status").json() == {"initialized": False}
        assert client.get("/api/watchlist").status_code == 401

        setup = client.post(
            "/api/auth/setup",
            json={"username": "owner", "password": "a-long-password"},
        )
        assert setup.status_code == 201
        token = setup.json()["token"]

        response = client.get(
            "/api/watchlist",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json() == {"items": []}


def test_auth_rejects_wrong_password(tmp_path: Path):
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'auth.db'}",
            enable_auth=True,
            secret_key="auth-test-secret-key-that-is-long-enough",
        )
    )

    with TestClient(app) as client:
        client.post(
            "/api/auth/setup",
            json={"username": "owner", "password": "correct-password"},
        )
        response = client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "wrong-password"},
        )

        assert response.status_code == 401

