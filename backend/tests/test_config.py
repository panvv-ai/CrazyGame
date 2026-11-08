from pathlib import Path

from src.crazygame.core.config import AppConfig


def test_database_migrates_from_legacy_filename(tmp_path: Path):
    legacy = tmp_path / "panwatch.sqlite3"
    legacy.write_bytes(b"legacy database")
    config = AppConfig(
        data_dir=tmp_path,
        database_url=None,
        encryption_key="config-test-secret-key-long-enough",
    )

    database_url = config.resolved_database_url()

    target = tmp_path / "crazygame.sqlite3"
    assert target.read_bytes() == b"legacy database"
    assert not legacy.exists()
    assert database_url.endswith("/crazygame.sqlite3")
