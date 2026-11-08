from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.services.catalog import InstrumentCandidate
from src.crazygame.services.market import QuoteSnapshot


class FakeMarket:
    def fetch_quotes(self, instruments):
        return {
            (instrument.symbol, instrument.market): QuoteSnapshot(
                symbol=instrument.symbol,
                name=instrument.name,
                market=instrument.market,
                current_price=110.0,
                change_pct=10.0,
                previous_close=100.0,
                as_of="2026-11-06T15:00:00+08:00",
                source="fixture",
                freshness="live",
            )
            for instrument in instruments
        }

    def fetch_daily_points(self, instrument, *, days=365):
        return [
            (date(2026, 11, 5), 100.0),
            (date(2026, 11, 6), 110.0),
        ]


class FakeAI:
    def complete(self, messages):
        return "# 健康\n\n继续持有。"


def make_client(tmp_path: Path, monkeypatch) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'read.db'}",
            encryption_key="read-api-test-secret-key-long-enough",
        )
    )
    app.state.quote_service = FakeMarket()
    app.state.ai = FakeAI()

    def fake_search(query, **kwargs):
        return [
            InstrumentCandidate(
                symbol="600519",
                name="贵州茅台",
                market="CN",
                asset_type="stock",
                currency="CNY",
                quote_mode="realtime",
            )
        ]

    monkeypatch.setattr(
        "src.crazygame.api.routes.market.search_instruments",
        fake_search,
    )
    return TestClient(app)


def test_instrument_search_returns_normalized_identity(tmp_path: Path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/instruments/search?q=茅台")

        assert response.status_code == 200
        assert response.json()["items"][0]["symbol"] == "600519"


def test_version_endpoint_returns_release_version(tmp_path: Path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/version")

        assert response.status_code == 200
        assert response.json()["version"] == "1.0.0"


def test_watchlist_quotes_preserve_freshness_metadata(tmp_path: Path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        client.post(
            "/api/watchlist",
            json={
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        )

        response = client.get("/api/quotes?kind=stock")

        assert response.status_code == 200
        quote = response.json()["items"][0]["quote"]
        assert quote["freshness"] == "live"
        assert quote["as_of"] == "2026-11-06T15:00:00+08:00"


def test_group_series_returns_line_points(tmp_path: Path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        item = client.post(
            "/api/watchlist",
            json={
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        group = client.post(
            "/api/groups",
            json={
                "name": "核心",
                "members": [{"instrument_id": item["instrument_id"], "weight": 1}],
            },
        ).json()

        response = client.get(f"/api/groups/{group['id']}/series")

        assert response.status_code == 200
        assert [point["value"] for point in response.json()["points"]] == [100.0, 110.0]
        assert response.json()["members"][0]["name"] == "贵州茅台"


def test_instrument_series_returns_normalized_line_points(tmp_path: Path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        item = client.post(
            "/api/watchlist",
            json={
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()

        response = client.get(
            f"/api/instruments/{item['instrument_id']}/series?days=365"
        )

        assert response.status_code == 200
        assert [point["value"] for point in response.json()["points"]] == [100.0, 110.0]


def test_daily_review_endpoint_generates_and_lists_report(tmp_path: Path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        item = client.post(
            "/api/watchlist",
            json={
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        client.put(
            "/api/holdings",
            json={
                "instrument_id": item["instrument_id"],
                "quantity": 10,
                "average_cost": 90,
            },
        )

        generated = client.post("/api/reviews/daily/run")
        listed = client.get("/api/reviews/daily")

        assert generated.status_code == 200
        assert generated.json()["status"] == "success"
        assert "继续持有" in listed.json()["items"][0]["content"]

