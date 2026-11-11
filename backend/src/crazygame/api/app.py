from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.crazygame.api.routes.alerts import router as alerts_router
from src.crazygame.api.routes.ai import router as ai_router
from src.crazygame.api.routes.channels import router as channels_router
from src.crazygame.api.routes.market import public_router, router
from src.crazygame.api.routes.portfolio import router as portfolio_router
from src.crazygame.api.routes.reviews import router as reviews_router
from src.crazygame.api.routes.settings import router as settings_router
from src.crazygame.core.config import AppConfig
from src.crazygame.core.database import (
    build_engine,
    build_session_factory,
    ensure_schema,
)
from src.crazygame.core.secrets import SecretBox
from src.crazygame.services.market import MarketService
from src.crazygame.services.ai_context import AIContextService
from src.crazygame.services.ai_news import NewsService
from src.crazygame.services.senders import NotificationSender


def create_app(config: AppConfig | None = None) -> FastAPI:
    """创建 CrazyGame FastAPI 应用并装配数据库、行情、AI、通知和路由。

    config 可注入测试配置；生产环境默认从环境变量和本地数据目录构建。应用启动
    时创建数据库结构并启动调度器，关闭时释放调度器与数据库连接。
    """
    app_config = config or AppConfig()
    engine = build_engine(app_config)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        """管理应用生命周期内的数据库初始化和后台任务。"""
        ensure_schema(engine)
        scheduler = None
        if app_config.enable_scheduler:
            from src.crazygame.services.scheduler import build_scheduler

            scheduler = build_scheduler(_app)
            scheduler.start()
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        engine.dispose()

    app = FastAPI(
        title="CrazyGame",
        version="1.0.0",
        lifespan=lifespan,
        redirect_slashes=False,
    )
    app.state.config = app_config
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.secret_box = SecretBox(app_config.encryption_key)
    app.state.quote_service = MarketService()
    app.state.news_service = NewsService(
        session_factory,
        secret_box=app.state.secret_box,
    )
    app.state.ai_context_service = AIContextService(
        session_factory=session_factory,
        quote_service=app.state.quote_service,
        news_service=app.state.news_service,
    )
    app.state.notification_sender = NotificationSender()
    from src.crazygame.services.ai import AIClient

    app.state.ai = (
        AIClient(
            app_config.ai_base_url,
            app_config.ai_api_key,
            app_config.ai_model,
            app_config.ai_vision_model,
        )
        if app_config.ai_api_key
        else None
    )
    app.include_router(public_router, prefix="/api")
    app.include_router(router, prefix="/api")
    app.include_router(settings_router, prefix="/api/settings")
    app.include_router(channels_router, prefix="/api/channels")
    app.include_router(portfolio_router, prefix="/api/holdings")
    app.include_router(alerts_router, prefix="/api/alerts")
    app.include_router(reviews_router, prefix="/api/reviews/daily")
    app.include_router(ai_router, prefix="/api/ai")

    static_dir = Path(__file__).resolve().parents[3] / "static"
    if static_dir.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = static_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app

