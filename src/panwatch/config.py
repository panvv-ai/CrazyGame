from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _local_secret_key() -> str:
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / ".app-secret"
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    key = os.urandom(48).hex()
    key_path.write_text(key, encoding="utf-8")
    key_path.chmod(0o600)
    return key


class AppConfig(BaseModel):
    data_dir: Path = Field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")))
    database_url: str | None = None
    enable_auth: bool = True
    secret_key: str = Field(default_factory=lambda: os.getenv("JWT_SECRET") or _local_secret_key())
    auth_username: str = Field(default_factory=lambda: os.getenv("AUTH_USERNAME", ""))
    auth_password: str = Field(default_factory=lambda: os.getenv("AUTH_PASSWORD", ""))
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
        return f"sqlite+pysqlite:///{self.data_dir / 'panwatch-v2.db'}"

