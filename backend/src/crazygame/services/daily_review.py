from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select

from src.crazygame.domain.models import (
    AppSetting,
    DailyReview,
    Holding,
    utc_now,
)


class DailyReviewService:
    def __init__(self, session_factory, quote_service, ai):
        self.session_factory = session_factory
        self.quote_service = quote_service
        self.ai = ai

    def generate(self, *, trade_date: date) -> dict:
        with self.session_factory() as db:
            existing = db.scalar(
                select(DailyReview).where(
                    DailyReview.trade_date == trade_date.isoformat(),
                    DailyReview.status == "success",
                )
            )
            if existing is not None:
                return {"status": "success", "id": existing.id, "cached": True}
            holdings = db.scalars(select(Holding).order_by(Holding.id)).all()
            if not holdings:
                return {"status": "skipped", "reason": "no_holdings"}
            language_row = db.get(AppSetting, "language")
            language = language_row.value if language_row else "zh-CN"
            instruments = [holding.instrument for holding in holdings]
            quotes = self.quote_service.fetch_quotes(instruments)
            snapshot_items = []
            for holding in holdings:
                instrument = holding.instrument
                quote = quotes.get((instrument.symbol, instrument.market))
                points = self.quote_service.fetch_daily_points(instrument, days=120)
                snapshot_items.append(
                    {
                        "symbol": instrument.symbol,
                        "name": instrument.name,
                        "market": instrument.market,
                        "asset_type": instrument.asset_type,
                        "quantity": holding.quantity,
                        "average_cost": holding.average_cost,
                        "current_price": quote.current_price if quote else None,
                        "change_pct": quote.change_pct if quote else None,
                        "trend_120d": [value for _, value in points[-120:]],
                    }
                )
            language_instruction = (
                "请使用简体中文输出。" if language == "zh-CN" else "Write the report in English."
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a long-term portfolio health reviewer. Do not predict prices "
                        "or execute trades. Produce concise Markdown with health, concentration, "
                        "trend, and hold/watch/reduce/add observations. Include a disclaimer."
                    ),
                },
                {
                    "role": "user",
                    "content": language_instruction
                    + "\n\n"
                    + json.dumps(snapshot_items, ensure_ascii=False),
                },
            ]
            try:
                content = self.ai.complete(messages)
            except Exception as exc:
                review = db.scalar(
                    select(DailyReview).where(DailyReview.trade_date == trade_date.isoformat())
                )
                if review is None:
                    review = DailyReview(
                        trade_date=trade_date.isoformat(),
                        language=language,
                    )
                    db.add(review)
                review.status = "failed"
                review.error = str(exc)
                db.commit()
                return {"status": "failed", "error": str(exc)}

            review = db.scalar(
                select(DailyReview).where(DailyReview.trade_date == trade_date.isoformat())
            )
            if review is None:
                review = DailyReview(
                    trade_date=trade_date.isoformat(),
                    language=language,
                )
                db.add(review)
            review.language = language
            review.status = "success"
            review.title = (
                "每日持仓健康简报" if language == "zh-CN" else "Daily portfolio health"
            )
            review.content = content
            review.snapshot_json = json.dumps(snapshot_items, ensure_ascii=False)
            review.updated_at = utc_now()
            review.error = ""
            db.commit()
            return {"status": "success", "id": review.id}

