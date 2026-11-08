from pathlib import Path

from sqlalchemy import select
from src.crazygame.core.config import AppConfig
from src.crazygame.core.database import (
    Base,
    build_engine,
    build_session_factory,
    ensure_schema,
)
from src.crazygame.domain.models import Holding, Instrument, WatchlistItem


def test_repairs_existing_etf_rows_without_breaking_references(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'migration.db'}",
        encryption_key="migration-test-secret-key-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as db:
        instrument = Instrument(
            symbol="515070",
            name="人工智能ETF华夏",
            market="FUND",
            asset_type="open_end_fund",
            currency="CNY",
            quote_mode="estimated",
        )
        db.add(instrument)
        db.flush()
        db.add(WatchlistItem(instrument_id=instrument.id, kind="stock"))
        db.add(
            Holding(
                instrument_id=instrument.id,
                quantity=1000,
                average_cost=1,
            )
        )
        db.commit()
        instrument_id = instrument.id

    ensure_schema(engine)

    with factory() as db:
        repaired = db.get(Instrument, instrument_id)
        assert repaired is not None
        assert repaired.market == "CN"
        assert repaired.asset_type == "listed_etf"
        assert repaired.currency == "CNY"
        assert repaired.quote_mode == "realtime"
        repaired_watchlist = db.scalar(
            select(WatchlistItem).where(
                WatchlistItem.instrument_id == instrument_id
            )
        )
        assert repaired_watchlist is not None
        assert repaired_watchlist.kind == "fund"
        assert db.scalar(
            select(Holding).where(Holding.instrument_id == instrument_id)
        )
    engine.dispose()
