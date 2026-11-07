from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.panwatch.alerts_api import router as alerts_router
from src.panwatch.api import public_router, router
from src.panwatch.auth import get_current_user
from src.panwatch.auth import router as auth_router
from src.panwatch.channels_api import router as channels_router
from src.panwatch.config import AppConfig
from src.panwatch.database import build_engine, build_session_factory, ensure_schema
from src.panwatch.market import MarketService
from src.panwatch.portfolio_api import router as portfolio_router
from src.panwatch.reviews_api import router as reviews_router
from src.panwatch.secrets import SecretBox
from src.panwatch.senders import NotificationSender
from src.panwatch.settings_api import router as settings_router


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or AppConfig()
    engine = build_engine(app_config)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        ensure_schema(engine)
        if app_config.auth_username and app_config.auth_password:
            from sqlalchemy import select

            from src.panwatch.auth import hash_password
            from src.panwatch.models import User

            with session_factory() as db:
                exists = db.scalar(select(User).limit(1))
                if exists is None:
                    db.add(
                        User(
                            username=app_config.auth_username,
                            password_hash=hash_password(app_config.auth_password),
                        )
                    )
                    db.commit()
        scheduler = None
        if app_config.enable_scheduler:
            from src.panwatch.scheduler import build_scheduler

            scheduler = build_scheduler(_app)
            scheduler.start()
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        engine.dispose()

    app = FastAPI(
        title="PanWatchDIY",
        version="2.0.0",
        lifespan=lifespan,
        redirect_slashes=False,
    )
    app.state.config = app_config
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.secret_box = SecretBox(app_config.secret_key)
    app.state.quote_service = MarketService()
    app.state.notification_sender = NotificationSender()
    from src.panwatch.ai import AIClient

    app.state.ai = (
        AIClient(
            app_config.ai_base_url,
            app_config.ai_api_key,
            app_config.ai_model,
        )
        if app_config.ai_api_key
        else None
    )
    app.include_router(auth_router, prefix="/api/auth")
    protected = [Depends(get_current_user)]
    app.include_router(public_router, prefix="/api")
    app.include_router(router, prefix="/api", dependencies=protected)
    app.include_router(settings_router, prefix="/api/settings", dependencies=protected)
    app.include_router(channels_router, prefix="/api/channels", dependencies=protected)
    app.include_router(portfolio_router, prefix="/api/holdings", dependencies=protected)
    app.include_router(alerts_router, prefix="/api/alerts", dependencies=protected)
    app.include_router(reviews_router, prefix="/api/reviews/daily", dependencies=protected)

    static_dir = Path(__file__).resolve().parents[2] / "static"
    if static_dir.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            candidate = static_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app

