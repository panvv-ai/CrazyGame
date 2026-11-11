from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from src.crazygame.domain.models import AIReport, AlertRule, Holding
from src.crazygame.services.ai_technical import build_technical_snapshot


class UnsupportedAIInstrument(ValueError):
    """AI diagnostics only support listed stocks and A-share ETFs."""


class AIContextService:
    def __init__(self, *, session_factory, quote_service, news_service):
        self.session_factory = session_factory
        self.quote_service = quote_service
        self.news_service = news_service

    def build(
        self,
        instrument,
        *,
        language: str,
        include_news: bool = True,
    ) -> dict:
        if instrument.asset_type == "open_end_fund":
            raise UnsupportedAIInstrument("open-end funds are not supported by AI diagnostics")

        quote = None
        quote_limitation = None
        try:
            quotes = self.quote_service.fetch_quotes([instrument])
            quote = quotes.get((instrument.symbol, instrument.market))
        except Exception:
            quote_limitation = "quote_unavailable"
        try:
            bars = self.quote_service.fetch_bars(instrument, days=250)
        except Exception:
            bars = []
        technical = build_technical_snapshot(bars)
        price_history = [
            {
                "date": bar.date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars[-250:]
        ]

        with self.session_factory() as db:
            holding = db.scalar(
                select(Holding).where(Holding.instrument_id == instrument.id)
            )
            alerts = db.scalars(
                select(AlertRule)
                .where(AlertRule.instrument_id == instrument.id)
                .order_by(AlertRule.id)
            ).all()
            latest_report = db.scalar(
                select(AIReport)
                .where(
                    AIReport.instrument_id == instrument.id,
                    AIReport.status == "success",
                )
                .order_by(AIReport.created_at.desc(), AIReport.id.desc())
                .limit(1)
            )

        latest_report_payload = None
        if latest_report is not None:
            try:
                latest_report_payload = json.loads(latest_report.report_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                latest_report_payload = None

        holding_payload = None
        if holding is not None:
            current = quote.current_price if quote else None
            market_value = current * holding.quantity if current is not None else None
            cost = holding.average_cost * holding.quantity
            holding_payload = {
                "quantity": holding.quantity,
                "average_cost": holding.average_cost,
                "market_value": market_value,
                "unrealized_pnl": market_value - cost if market_value is not None else None,
                "note": holding.note,
            }

        intel = {
            "items": [],
            "industry": "",
            "concepts": [],
            "limitations": ["news_disabled"],
        }
        if include_news:
            try:
                intel = self.news_service.fetch_for_instrument(instrument)
            except Exception:
                intel["limitations"] = ["news_unavailable"]

        limitations = list(technical.get("limitations", []))
        if quote_limitation:
            limitations.append(quote_limitation)
        limitations.extend(intel.get("limitations", []))
        if quote is None:
            quality_level = "poor"
            limitations.append(quote_limitation or "quote_missing")
        elif quote.current_price is None:
            quality_level = "poor"
            limitations.append("quote_price_missing")
        elif quote.freshness in {"stale", "estimated"}:
            quality_level = "limited"
            limitations.append(f"quote_{quote.freshness}")
        elif "history_under_60_days" in limitations or limitations:
            quality_level = "limited"
        else:
            quality_level = "good"

        quote_payload = quote.as_dict() if quote else {}
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "instrument": {
                "id": instrument.id,
                "symbol": instrument.symbol,
                "name": instrument.name,
                "market": instrument.market,
                "asset_type": instrument.asset_type,
                "currency": instrument.currency,
            },
            "quote": quote_payload,
            "price_history": price_history,
            "technical": technical,
            "holding": holding_payload,
            "alerts": [
                {
                    "name": alert.name,
                    "metric": alert.metric,
                    "direction": alert.direction,
                    "threshold": alert.threshold,
                    "enabled": alert.enabled,
                }
                for alert in alerts
            ],
            "industry": intel.get("industry", ""),
            "concepts": intel.get("concepts", []),
            "hotspots": [item.as_dict() for item in intel.get("items", [])[:8]],
            "latest_report": latest_report_payload,
            "data_quality": {
                "level": quality_level,
                "limitations": list(dict.fromkeys(limitations)),
                "quote_as_of": quote_payload.get("as_of", ""),
                "quote_source": quote_payload.get("source", ""),
                "quote_freshness": quote_payload.get("freshness", ""),
            },
        }
