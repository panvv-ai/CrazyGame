from pathlib import Path

from fastapi.testclient import TestClient

from src.panwatch.app import create_app
from src.panwatch.config import AppConfig
from src.panwatch.market import QuoteSnapshot


class FakeQuoteService:
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


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'portfolio.db'}",
            enable_auth=False,
            secret_key="portfolio-test-secret-key-long-enough",
        )
    )
    app.state.quote_service = FakeQuoteService()
    return TestClient(app)


def test_holding_valuation_uses_latest_quote(tmp_path: Path):
    with make_client(tmp_path) as client:
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
                "note": "长期",
            },
        )

        response = client.get("/api/holdings")

        assert response.status_code == 200
        holding = response.json()["items"][0]
        assert holding["current_price"] == 110.0
        assert holding["market_value"] == 1100.0
        assert holding["unrealized_pnl"] == 200.0


def test_group_summary_uses_normalized_quote_changes(tmp_path: Path):
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
        ).json()
        second = client.post(
            "/api/watchlist",
            json={
                "symbol": "00700",
                "name": "腾讯控股",
                "market": "HK",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        group = client.post(
            "/api/groups",
            json={
                "name": "长期核心",
                "members": [
                    {"instrument_id": first["instrument_id"], "weight": 2},
                    {"instrument_id": second["instrument_id"], "weight": 1},
                ],
            },
        ).json()

        summary = client.get(f"/api/groups/{group['id']}/summary")

        assert summary.status_code == 200
        assert summary.json()["day_change_pct"] == 10.0
        assert summary.json()["coverage"] == 1.0

