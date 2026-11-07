from __future__ import annotations

import os

import uvicorn

from src.panwatch.app import create_app


app = create_app()


if __name__ == "__main__":
    reload_enabled = os.getenv("PANWATCH_RELOAD", "").lower() in {"1", "true", "yes"}
    uvicorn.run(
        "server:app" if reload_enabled else app,
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
        reload_dirs=["src"] if reload_enabled else None,
        proxy_headers=True,
    )
