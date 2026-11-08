import threading
import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from src.crazygame.api.app import create_app
from src.crazygame.core.config import AppConfig
from src.crazygame.services.market import QuoteSnapshot


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


class ConcurrentSeriesQuoteService(FakeQuoteService):
    def __init__(self):
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def fetch_daily_points(self, instrument, *, days=365):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        with self._lock:
            self.active -= 1
        return [(date(2026, 11, 6), 100.0), (date(2026, 11, 7), 101.0)]


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(
        AppConfig(
            data_dir=tmp_path,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'portfolio.db'}",
            encryption_key="portfolio-test-secret-key-long-enough",
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
                "symbol": "000001",
                "name": "平安银行",
                "market": "CN",
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
        assert group["scope"] == "stock_cn"
        assert summary.json()["day_change_pct"] == 10.0
        assert summary.json()["coverage"] == 1.0


def test_group_rejects_members_from_different_markets(tmp_path: Path):
    with make_client(tmp_path) as client:
        cn_stock = client.post(
            "/api/watchlist",
            json={
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        us_stock = client.post(
            "/api/watchlist",
            json={
                "symbol": "AAPL",
                "name": "Apple",
                "market": "US",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()

        response = client.post(
            "/api/groups",
            json={
                "name": "混合市场",
                "members": [
                    {"instrument_id": cn_stock["instrument_id"], "weight": 1},
                    {"instrument_id": us_stock["instrument_id"], "weight": 1},
                ],
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "group members must share one scope"


def test_group_rejects_mixing_listed_and_open_end_funds(tmp_path: Path):
    with make_client(tmp_path) as client:
        listed_fund = client.post(
            "/api/watchlist",
            json={
                "symbol": "510300",
                "name": "沪深300ETF",
                "market": "CN",
                "asset_type": "listed_etf",
                "kind": "fund",
            },
        ).json()
        open_end_fund = client.post(
            "/api/watchlist",
            json={
                "symbol": "110022",
                "name": "易方达消费行业",
                "market": "FUND",
                "asset_type": "open_end_fund",
                "kind": "fund",
            },
        ).json()

        response = client.post(
            "/api/groups",
            json={
                "name": "混合基金",
                "members": [
                    {"instrument_id": listed_fund["instrument_id"], "weight": 1},
                    {"instrument_id": open_end_fund["instrument_id"], "weight": 1},
                ],
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "group members must share one scope"


def test_group_update_rejects_mixed_members(tmp_path: Path):
    with make_client(tmp_path) as client:
        initial_stock = client.post(
            "/api/watchlist",
            json={
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        cn_stock = client.post(
            "/api/watchlist",
            json={
                "symbol": "000001",
                "name": "平安银行",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        us_stock = client.post(
            "/api/watchlist",
            json={
                "symbol": "AAPL",
                "name": "Apple",
                "market": "US",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        group = client.post(
            "/api/groups",
            json={
                "name": "A股组合",
                "members": [
                    {"instrument_id": initial_stock["instrument_id"], "weight": 1},
                ],
            },
        ).json()

        response = client.put(
            f"/api/groups/{group['id']}",
            json={
                "name": "错误修改",
                "members": [
                    {"instrument_id": cn_stock["instrument_id"], "weight": 1},
                    {"instrument_id": us_stock["instrument_id"], "weight": 1},
                ],
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "group members must share one scope"


def test_group_series_fetches_members_concurrently(tmp_path: Path):
    with make_client(tmp_path) as client:
        quote_service = ConcurrentSeriesQuoteService()
        client.app.state.quote_service = quote_service
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
                "symbol": "000001",
                "name": "平安银行",
                "market": "CN",
                "asset_type": "stock",
                "kind": "stock",
            },
        ).json()
        group = client.post(
            "/api/groups",
            json={
                "name": "并发组合",
                "members": [
                    {"instrument_id": first["instrument_id"], "weight": 1},
                    {"instrument_id": second["instrument_id"], "weight": 1},
                ],
            },
        ).json()

        response = client.get(f"/api/groups/{group['id']}/series?days=365")

        assert response.status_code == 200
        assert quote_service.max_active >= 2

