from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.domain.models import Holding, Instrument, WatchlistItem


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'transfer.db'}",
            encryption_key="transfer-api-test-secret-key-that-is-long-enough",
            enable_scheduler=False,
        )
    )
    client = TestClient(app)
    client.__enter__()
    return client


def seed_items(client: TestClient) -> None:
    with client.app.state.session_factory() as db:
        instrument = Instrument(
            symbol="600519",
            name="贵州茅台",
            market="CN",
            asset_type="stock",
            currency="CNY",
            quote_mode="realtime",
        )
        db.add(instrument)
        db.flush()
        db.add(WatchlistItem(instrument_id=instrument.id, kind="stock", sort_order=0))
        db.add(
            Holding(
                instrument_id=instrument.id,
                quantity=2,
                average_cost=1400,
                note="",
            )
        )
        db.commit()


def test_export_selected_modules_without_credentials(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        seed_items(client)
        response = client.post(
            "/api/transfer/export",
            json={
                "modules": ["watchlist", "holdings"],
                "include_credentials": False,
                "password": "transfer-password",
            },
        )

        assert response.status_code == 200
        outer = json.loads(response.content)
        assert outer["format"] == "crazygame-transfer"
        assert outer["version"] == 1
        assert outer["data"]
    finally:
        client.__exit__(None, None, None)


def test_import_merges_watchlist_and_holdings(tmp_path: Path):
    (tmp_path / "source").mkdir(exist_ok=True)
    (tmp_path / "target").mkdir(exist_ok=True)
    source = make_client(tmp_path / "source")
    target = make_client(tmp_path / "target")
    try:
        seed_items(source)
        exported = source.post(
            "/api/transfer/export",
            json={
                "modules": ["watchlist", "holdings"],
                "include_credentials": False,
                "password": "transfer-password",
            },
        )
        imported = target.post(
            "/api/transfer/import",
            data={
                "password": "transfer-password",
                "modules": json.dumps(["watchlist", "holdings"]),
            },
            files={
                "file": (
                    "CrazyGame.crazygame",
                    exported.content,
                    "application/octet-stream",
                )
            },
        )

        assert imported.status_code == 200
        assert imported.json()["ok"] is True
        assert len(target.get("/api/watchlist").json()["items"]) == 1
        assert len(target.get("/api/holdings").json()["items"]) == 1
    finally:
        source.__exit__(None, None, None)
        target.__exit__(None, None, None)


def test_wrong_transfer_password_is_rejected(tmp_path: Path):
    client = make_client(tmp_path)
    try:
        seed_items(client)
        exported = client.post(
            "/api/transfer/export",
            json={
                "modules": ["watchlist"],
                "include_credentials": False,
                "password": "correct-password",
            },
        )
        imported = client.post(
            "/api/transfer/import",
            data={"password": "wrong-password", "modules": '["watchlist"]'},
            files={"file": ("CrazyGame.crazygame", exported.content)},
        )

        assert imported.status_code == 400
    finally:
        client.__exit__(None, None, None)
