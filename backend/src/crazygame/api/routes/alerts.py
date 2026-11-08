from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from src.crazygame.api.dependencies import get_session
from src.crazygame.api.serializers import instrument_dict
from src.crazygame.core.timeutils import iso_utc
from src.crazygame.domain.models import (
    AlertHit,
    AlertRule,
    Instrument,
    NotificationDelivery,
)

router = APIRouter()


class AlertPayload(BaseModel):
    instrument_id: int
    name: str = ""
    metric: str = "price"
    direction: str = "above"
    threshold: float
    channel_ids: list[int] = []
    enabled: bool = True
    once_per_day: bool = True
    market_hours_only: bool = True
    cooldown_minutes: int = Field(default=30, ge=0, le=1440)

    @model_validator(mode="after")
    def validate_rule(self):
        if self.metric not in {"price", "change_pct"}:
            raise ValueError("unsupported metric")
        if self.direction not in {"above", "below"}:
            raise ValueError("unsupported direction")
        return self


class AlertPatch(BaseModel):
    enabled: bool | None = None


def alert_dict(row: AlertRule) -> dict:
    return {
        "id": row.id,
        "instrument_id": row.instrument_id,
        **instrument_dict(row.instrument),
        "name": row.name,
        "metric": row.metric,
        "direction": row.direction,
        "threshold": row.threshold,
        "channel_ids": json.loads(row.channel_ids or "[]"),
        "enabled": row.enabled,
        "once_per_day": row.once_per_day,
        "market_hours_only": row.market_hours_only,
        "cooldown_minutes": row.cooldown_minutes,
        "last_triggered_at": iso_utc(row.last_triggered_at),
    }


@router.get("")
def list_alerts(db=Depends(get_session)):
    rows = db.scalars(select(AlertRule).order_by(AlertRule.id)).all()
    return {"items": [alert_dict(row) for row in rows]}


@router.get("/hits")
def list_alert_hits(db=Depends(get_session)):
    rows = db.scalars(
        select(AlertHit).order_by(AlertHit.triggered_at.desc(), AlertHit.id.desc())
    ).all()
    items = []
    for hit in rows:
        deliveries = db.scalars(
            select(NotificationDelivery)
            .where(NotificationDelivery.hit_id == hit.id)
            .order_by(NotificationDelivery.id)
        ).all()
        items.append(
            {
                "id": hit.id,
                "rule_id": hit.rule_id,
                "rule_name": hit.rule.name,
                "symbol": hit.instrument.symbol,
                "instrument_name": hit.instrument.name,
                "market": hit.instrument.market,
                "triggered_at": iso_utc(hit.triggered_at),
                "observed_value": hit.observed_value,
                "snapshot": json.loads(hit.snapshot_json or "{}"),
                "deliveries": [
                    {
                        "id": delivery.id,
                        "channel_id": delivery.channel_id,
                        "status": delivery.status,
                        "attempts": delivery.attempts,
                        "error_code": delivery.error_code,
                    }
                    for delivery in deliveries
                ],
            }
        )
    return {"items": items}


@router.post("", status_code=201)
def create_alert(payload: AlertPayload, db=Depends(get_session)):
    if db.get(Instrument, payload.instrument_id) is None:
        raise HTTPException(404, "instrument not found")
    row = AlertRule(
        instrument_id=payload.instrument_id,
        name=payload.name,
        metric=payload.metric,
        direction=payload.direction,
        threshold=payload.threshold,
        channel_ids=json.dumps(payload.channel_ids),
        enabled=payload.enabled,
        once_per_day=payload.once_per_day,
        market_hours_only=payload.market_hours_only,
        cooldown_minutes=payload.cooldown_minutes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return alert_dict(row)


@router.patch("/{rule_id}")
def update_alert(rule_id: int, payload: AlertPatch, db=Depends(get_session)):
    row = db.get(AlertRule, rule_id)
    if row is None:
        raise HTTPException(404, "alert not found")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return alert_dict(row)


@router.delete("/{rule_id}")
def delete_alert(rule_id: int, db=Depends(get_session)):
    row = db.get(AlertRule, rule_id)
    if row is None:
        raise HTTPException(404, "alert not found")
    db.delete(row)
    db.commit()
    return {"ok": True}

