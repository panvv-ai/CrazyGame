from pathlib import Path

from fastapi.testclient import TestClient

from src.panwatch.app import create_app
from src.panwatch.config import AppConfig


def make_client(tmp_path: Path) -> TestClient:
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        enable_auth=False,
        secret_key="test-secret-key-that-is-long-enough",
    )
    app = create_app(config)
    return TestClient(app)


def test_watchlist_and_group_crud_normalizes_weights(tmp_path: Path):
    with make_client(tmp_path) as client:
        first = client.post(
            "/api/watchlist",
            json={
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        )
        second = client.post(
            "/api/watchlist",
            json={
                "symbol": "510300",
                "name": "沪深300ETF",
                "market": "CN",
                "asset_type": "listed_etf",
                "kind": "fund",
            },
        )

        assert first.status_code == 201
        assert second.status_code == 201

        group = client.post(
            "/api/groups",
            json={
                "name": "核心资产",
                "members": [
                    {"instrument_id": first.json()["instrument_id"], "weight": 2},
                    {"instrument_id": second.json()["instrument_id"], "weight": 1},
                ],
            },
        )

        assert group.status_code == 201
        payload = group.json()
        assert [member["normalized_weight"] for member in payload["members"]] == [
            2 / 3,
            1 / 3,
        ]


def test_duplicate_watchlist_item_returns_existing_record(tmp_path: Path):
    with make_client(tmp_path) as client:
        body = {
            "symbol": "AAPL",
            "name": "Apple",
            "market": "US",
            "asset_type": "stock",
            "kind": "stock",
        }

        first = client.post("/api/watchlist", json=body)
        second = client.post("/api/watchlist", json=body)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        assert client.get("/api/watchlist?kind=stock").json()["items"][0]["symbol"] == "AAPL"

