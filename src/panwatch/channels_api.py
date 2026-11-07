from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.panwatch.api import get_session
from src.panwatch.models import NotifyChannel
from src.panwatch.secrets import mask_config

router = APIRouter()
SUPPORTED_TYPES = {"feishu", "aliyun_sms"}


class ChannelPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str
    config: dict = {}
    enabled: bool = True


def channel_dict(row: NotifyChannel, secret_box) -> dict:
    try:
        config = json.loads(secret_box.decrypt(row.config_encrypted))
    except Exception:
        config = {}
    return {
        "id": row.id,
        "name": row.name,
        "type": row.type,
        "config": mask_config(config),
        "enabled": row.enabled,
    }


@router.get("")
def list_channels(request: Request, db=Depends(get_session)):
    rows = db.scalars(select(NotifyChannel).order_by(NotifyChannel.id)).all()
    return {"items": [channel_dict(row, request.app.state.secret_box) for row in rows]}


@router.post("", status_code=201)
def create_channel(payload: ChannelPayload, request: Request, db=Depends(get_session)):
    if payload.type not in SUPPORTED_TYPES:
        raise HTTPException(400, "unsupported channel type")
    encrypted = request.app.state.secret_box.encrypt(
        json.dumps(payload.config, ensure_ascii=False)
    )
    row = NotifyChannel(
        name=payload.name,
        type=payload.type,
        config_encrypted=encrypted,
        enabled=payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return channel_dict(row, request.app.state.secret_box)


@router.delete("/{channel_id}")
def delete_channel(channel_id: int, db=Depends(get_session)):
    row = db.get(NotifyChannel, channel_id)
    if row is None:
        raise HTTPException(404, "channel not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/{channel_id}/test")
def test_channel(channel_id: int, request: Request, db=Depends(get_session)):
    row = db.get(NotifyChannel, channel_id)
    if row is None:
        raise HTTPException(404, "channel not found")
    try:
        config = json.loads(request.app.state.secret_box.decrypt(row.config_encrypted))
        ok = request.app.state.notification_sender.send(
            row.type,
            config,
            "测试通知 · PanWatchDIY",
            "这是一条测试消息。收到即表示通知渠道配置可用。",
        )
    except Exception as exc:
        raise HTTPException(502, f"channel test failed: {exc}") from exc
    if not ok:
        raise HTTPException(502, "channel test failed")
    return {"ok": True}

