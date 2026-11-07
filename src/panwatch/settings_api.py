from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.panwatch.api import get_session
from src.panwatch.models import AppSetting
from src.panwatch.secrets import mask_config

router = APIRouter()


class AISettings(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class SettingsPayload(BaseModel):
    language: str = "zh-CN"
    ai: AISettings | None = None
    daily_review_channel_ids: list[int] = []
    daily_review_enabled: bool = True


def _get_json(db, key: str) -> dict:
    row = db.get(AppSetting, key)
    if row is None or not row.value:
        return {}
    try:
        value = json.loads(row.value)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def _put_json(db, key: str, value: dict) -> None:
    row = db.get(AppSetting, key)
    serialized = json.dumps(value, ensure_ascii=False)
    if row is None:
        db.add(AppSetting(key=key, value=serialized))
    else:
        row.value = serialized


@router.get("")
def get_settings(request: Request, db=Depends(get_session)):
    language = db.get(AppSetting, "language")
    ai = _get_json(db, "ai")
    ai = {
        "base_url": ai.get("base_url") or request.app.state.config.ai_base_url,
        "api_key": ai.get("api_key") or request.app.state.config.ai_api_key,
        "model": ai.get("model") or request.app.state.config.ai_model,
    }
    if ai.get("api_key"):
        ai = mask_config(ai)
    review = _get_json(db, "daily_review")
    return {
        "language": language.value if language else "zh-CN",
        "ai": ai,
        "daily_review_channel_ids": review.get("channel_ids", []),
        "daily_review_enabled": review.get("enabled", True),
    }


@router.put("")
def update_settings(payload: SettingsPayload, request: Request, db=Depends(get_session)):
    language = db.get(AppSetting, "language")
    if language is None:
        db.add(AppSetting(key="language", value=payload.language))
    else:
        language.value = payload.language

    if payload.ai is not None:
        ai_payload = payload.ai.model_dump()
        current = _get_json(db, "ai")
        if ai_payload["api_key"] == "••••••••":
            ai_payload["api_key"] = current.get("api_key", "")
        if ai_payload["api_key"]:
            ai_payload["api_key"] = request.app.state.secret_box.encrypt(
                ai_payload["api_key"]
            )
        _put_json(db, "ai", ai_payload)

    _put_json(
        db,
        "daily_review",
        {
            "channel_ids": payload.daily_review_channel_ids,
            "enabled": payload.daily_review_enabled,
        },
    )
    db.commit()
    return get_settings(request, db)

