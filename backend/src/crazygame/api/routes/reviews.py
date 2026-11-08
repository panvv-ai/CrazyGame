from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from src.crazygame.api.dependencies import get_session
from src.crazygame.core.timeutils import iso_utc
from src.crazygame.domain.models import DailyReview
from src.crazygame.services.ai import resolve_ai_client
from src.crazygame.services.daily_review import DailyReviewService

router = APIRouter()


def review_dict(row: DailyReview) -> dict:
    return {
        "id": row.id,
        "trade_date": row.trade_date,
        "language": row.language,
        "status": row.status,
        "title": row.title,
        "content": row.content,
        "model_label": row.model_label,
        "notified_at": iso_utc(row.notified_at),
        "error": row.error,
        "created_at": iso_utc(row.created_at),
    }


@router.get("")
def list_reviews(db=Depends(get_session)):
    rows = db.scalars(
        select(DailyReview).order_by(DailyReview.trade_date.desc())
    ).all()
    return {"items": [review_dict(row) for row in rows]}


@router.post("/run")
def run_review(request: Request, trade_date: str | None = None):
    timezone = ZoneInfo(request.app.state.config.app_timezone)
    target = (
        date.fromisoformat(trade_date)
        if trade_date
        else datetime.now(timezone).date()
    )
    service = DailyReviewService(
        session_factory=request.app.state.session_factory,
        quote_service=request.app.state.quote_service,
        ai=request.app.state.ai
        or resolve_ai_client(
            session_factory=request.app.state.session_factory,
            secret_box=request.app.state.secret_box,
            fallback_base_url=request.app.state.config.ai_base_url,
            fallback_api_key=request.app.state.config.ai_api_key,
            fallback_model=request.app.state.config.ai_model,
        ),
    )
    if service.ai is None:
        return {"status": "skipped", "reason": "ai_not_configured"}
    return service.generate(trade_date=target)

