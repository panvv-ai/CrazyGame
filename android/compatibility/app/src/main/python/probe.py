from __future__ import annotations

import json
import platform
import sqlite3


def run_self_check() -> str:
    checks: dict[str, str] = {}

    def check(name: str, callback) -> None:
        try:
            checks[name] = str(callback())
        except Exception as error:
            checks[name] = f"ERROR: {type(error).__name__}: {error}"

    modules: dict[str, object] = {}

    def imports() -> str:
        import apscheduler
        import cryptography
        import fastapi
        import httpx
        import pydantic
        import sqlalchemy
        import uvicorn

        modules.update(
            {
                "apscheduler": apscheduler,
                "cryptography": cryptography,
                "fastapi": fastapi,
                "httpx": httpx,
                "pydantic": pydantic,
                "sqlalchemy": sqlalchemy,
                "uvicorn": uvicorn,
            }
        )
        return "ok"

    def sqlite_check() -> str:
        with sqlite3.connect(":memory:") as connection:
            value = connection.execute("select sqlite_version(), 40 + 2").fetchone()
        return f"sqlite={value[0]}, answer={value[1]}"

    def cryptography_check() -> str:
        from cryptography.fernet import Fernet

        box = Fernet(Fernet.generate_key())
        return box.decrypt(box.encrypt(b"crazygame")).decode("utf-8")

    def sqlalchemy_check() -> str:
        from sqlalchemy import create_engine, text

        engine = create_engine("sqlite+pysqlite:///:memory:")
        with engine.connect() as connection:
            return str(connection.execute(text("select 42")).scalar_one())

    def timezone_check() -> str:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return datetime(2026, 1, 1, tzinfo=ZoneInfo("Asia/Shanghai")).isoformat()

    def https_check() -> str:
        import httpx

        response = httpx.get("https://example.com", timeout=8)
        response.raise_for_status()
        return str(response.status_code)

    check("python", lambda: f"{platform.python_version()} / {platform.machine()}")
    check("imports", imports)
    check("sqlite", sqlite_check)
    check("cryptography", cryptography_check)
    check("sqlalchemy", sqlalchemy_check)
    check("timezone", timezone_check)
    check("https", https_check)

    ok = all(not value.startswith("ERROR:") for value in checks.values())
    return json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2)


def build_app():
    from fastapi import FastAPI

    app = FastAPI(title="CrazyGame Android compatibility probe")

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "runtime": "chaquopy",
            "python": platform.python_version(),
        }

    return app


def start_server() -> None:
    import uvicorn

    uvicorn.run(
        build_app(),
        host="127.0.0.1",
        port=8765,
        log_level="info",
        access_log=False,
    )
