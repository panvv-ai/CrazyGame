from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _configured_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))


def _local_encryption_key() -> str:
    data_dir = _configured_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / ".app-secret"
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    key = os.urandom(48).hex()
    key_path.write_text(key, encoding="utf-8")
    key_path.chmod(0o600)
    return key


class AppConfig(BaseModel):
    data_dir: Path = Field(default_factory=_configured_data_dir)
    database_url: str | None = None
    encryption_key: str = Field(
        default_factory=lambda: os.getenv("APP_SECRET_KEY") or _local_encryption_key()
    )
    app_timezone: str = Field(
        default_factory=lambda: os.getenv("TZ", "Asia/Shanghai")
    )
    ai_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "AI_BASE_URL", "https://api.openai.com/v1"
        )
    )
    ai_api_key: str = Field(default_factory=lambda: os.getenv("AI_API_KEY", ""))
    ai_model: str = Field(default_factory=lambda: os.getenv("AI_MODEL", "gpt-4.1-mini"))
    daily_review_hour: int = 15
    daily_review_minute: int = 20
    enable_scheduler: bool = True

    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        target = self.data_dir / "crazygame.sqlite3"
        legacy = self.data_dir / "panwatch.sqlite3"
        if legacy.exists() and not target.exists():
            try:
                for suffix in ("", "-wal", "-shm"):
                    source = self.data_dir / f"{legacy.name}{suffix}"
                    if source.exists():
                        source.replace(self.data_dir / f"{target.name}{suffix}")
            except OSError:
                return f"sqlite+pysqlite:///{legacy}"
        return f"sqlite+pysqlite:///{target}"

