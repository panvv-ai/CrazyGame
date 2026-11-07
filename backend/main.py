from __future__ import annotations

import os

import uvicorn

from src.panwatch.api.app import create_app


app = create_app()


if __name__ == "__main__":
    reload_enabled = os.getenv("PANWATCH_RELOAD", "").lower() in {"1", "true", "yes"}
    host = os.getenv("PANWATCH_HOST", "127.0.0.1")
    port = int(os.getenv("PANWATCH_PORT", "8000"))
    uvicorn.run(
        "main:app" if reload_enabled else app,
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=["src"] if reload_enabled else None,
        proxy_headers=True,
    )
