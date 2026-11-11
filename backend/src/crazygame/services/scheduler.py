from __future__ import annotations

import asyncio
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from src.crazygame.core.calendar import is_trading_day
from src.crazygame.domain.models import AppSetting, DailyReview, NotifyChannel, utc_now
from src.crazygame.services.ai import resolve_runtime_ai_client
from src.crazygame.services.alert_service import AlertScanner, DeliveryWorker
from src.crazygame.services.daily_review import DailyReviewService


def build_scheduler(app) -> AsyncIOScheduler:
    """构建后台调度器，负责提醒轮询和每日持仓简报。

    所有同步数据库与行情调用都放到线程中执行，避免阻塞 FastAPI 事件循环。
    """
    config = app.state.config
    timezone = ZoneInfo(config.app_timezone)
    scheduler = AsyncIOScheduler(timezone=timezone)

    async def scan_alerts():
        """定时扫描提醒并立即尝试投递新生成的消息。"""
        scanner = AlertScanner(
            session_factory=app.state.session_factory,
            quote_service=app.state.quote_service,
            secret_box=app.state.secret_box,
        )
        worker = DeliveryWorker(
            session_factory=app.state.session_factory,
            secret_box=app.state.secret_box,
            sender=app.state.notification_sender,
        )
        await asyncio.to_thread(scanner.scan_once)
        await asyncio.to_thread(worker.drain)

    async def generate_daily_review():
        """仅在 A 股交易日生成一次收盘后持仓简报，并发送到配置渠道。"""
        today = datetime.now(timezone).date()
        if not is_trading_day("CN", today):
            return
        with app.state.session_factory() as db:
            enabled_row = db.get(AppSetting, "daily_review")
            if enabled_row is not None:
                try:
                    enabled_config = json.loads(enabled_row.value)
                except Exception:
                    enabled_config = {}
                if enabled_config.get("enabled", True) is False:
                    return
        ai = resolve_runtime_ai_client(
            session_factory=app.state.session_factory,
            secret_box=app.state.secret_box,
            fallback_base_url=config.ai_base_url,
            fallback_api_key=config.ai_api_key,
            fallback_model=config.ai_model,
            fallback_vision_model=config.ai_vision_model,
            runtime_client=app.state.ai,
        )
        if ai is None:
            return
        service = DailyReviewService(
            session_factory=app.state.session_factory,
            quote_service=app.state.quote_service,
            ai=ai,
        )
        result = await asyncio.to_thread(service.generate, trade_date=today)
        if result.get("status") == "success":
            await asyncio.to_thread(_notify_review, app, int(result["id"]))

    scheduler.add_job(
        scan_alerts,
        "interval",
        seconds=30,
        id="scan_alerts",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_review,
        "cron",
        day_of_week="mon-fri",
        hour=config.daily_review_hour,
        minute=config.daily_review_minute,
        id="daily_review",
        replace_existing=True,
        misfire_grace_time=300,
    )
    retry_at = datetime.combine(
        datetime.now(timezone).date(),
        time(config.daily_review_hour, config.daily_review_minute),
        timezone,
    ) + timedelta(minutes=8)
    scheduler.add_job(
        generate_daily_review,
        "cron",
        day_of_week="mon-fri",
        hour=retry_at.hour,
        minute=retry_at.minute,
        id="daily_review_retry",
        replace_existing=True,
        misfire_grace_time=300,
    )
    return scheduler


def _notify_review(app, review_id: int) -> None:
    """把已生成的每日简报投递到设置中选择的通知渠道。"""
    with app.state.session_factory() as db:
        review = db.get(DailyReview, review_id)
        settings = db.get(AppSetting, "daily_review")
        if review is None or settings is None:
            return
        try:
            config = json.loads(settings.value)
            channel_ids = [int(value) for value in config.get("channel_ids", [])]
        except Exception:
            return
        if not channel_ids:
            return
        channels = db.scalars(
            select(NotifyChannel).where(
                NotifyChannel.id.in_(channel_ids),
                NotifyChannel.enabled.is_(True),
            )
        ).all()
        for channel in channels:
            try:
                config = json.loads(app.state.secret_box.decrypt(channel.config_encrypted))
                app.state.notification_sender.send(
                    channel.type,
                    config,
                    review.title,
                    review.content[:500],
                )
            except Exception:
                continue
        review.notified_at = utc_now()
        db.commit()

