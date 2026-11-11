from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.crazygame.api.dependencies import get_session
from src.crazygame.core.secrets import mask_config
from src.crazygame.domain.models import AppSetting
from src.crazygame.services.ai import AIClient, resolve_runtime_ai_client

router = APIRouter()


class AISettings(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    vision_model: str = ""


class NewsSettings(BaseModel):
    enabled: bool = True
    provider: Literal["eastmoney", "tavily", "bocha"] = "eastmoney"
    api_key: str = ""


class SettingsPayload(BaseModel):
    language: str = "zh-CN"
    ai: AISettings | None = None
    news: NewsSettings | None = None
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
        "vision_model": ai.get("vision_model")
        or request.app.state.config.ai_vision_model,
    }
    news = _get_json(db, "news")
    news = {
        "enabled": news.get("enabled", request.app.state.config.news_enabled),
        "provider": news.get("provider") or request.app.state.config.news_provider,
        "api_key": news.get("api_key") or request.app.state.config.news_api_key,
    }
    if ai.get("api_key"):
        ai = mask_config(ai)
    if news.get("api_key"):
        news = mask_config(news)
    review = _get_json(db, "daily_review")
    return {
        "language": language.value if language else "zh-CN",
        "ai": ai,
        "news": news,
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
        else:
            ai_payload["api_key"] = ai_payload["api_key"].strip()
        if ai_payload["api_key"] and ai_payload["api_key"] != current.get("api_key"):
            ai_payload["api_key"] = request.app.state.secret_box.encrypt(
                ai_payload["api_key"]
            )
        _put_json(db, "ai", ai_payload)

    if payload.news is not None:
        news_payload = payload.news.model_dump()
        current = _get_json(db, "news")
        if news_payload["api_key"] == "••••••••":
            news_payload["api_key"] = current.get("api_key", "")
        else:
            news_payload["api_key"] = news_payload["api_key"].strip()
        if news_payload["api_key"] and news_payload["api_key"] != current.get("api_key"):
            news_payload["api_key"] = request.app.state.secret_box.encrypt(
                news_payload["api_key"]
            )
        _put_json(db, "news", news_payload)

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


@router.post("/ai/test")
def test_ai_capabilities(request: Request, payload: AISettings | None = None):
    saved_ai = resolve_runtime_ai_client(
        session_factory=request.app.state.session_factory,
        secret_box=request.app.state.secret_box,
        fallback_base_url=request.app.state.config.ai_base_url,
        fallback_api_key=request.app.state.config.ai_api_key,
        fallback_model=request.app.state.config.ai_model,
        fallback_vision_model=request.app.state.config.ai_vision_model,
        runtime_client=request.app.state.ai,
    )
    ai = saved_ai
    if payload is not None and payload.api_key.strip() not in {"", "••••••••"}:
        ai = AIClient(
            payload.base_url,
            payload.api_key,
            payload.model,
            payload.vision_model,
        )
    elif payload is not None and saved_ai is not None:
        ai = AIClient(
            payload.base_url or saved_ai.base_url,
            saved_ai.api_key,
            payload.model or saved_ai.model,
            payload.vision_model or saved_ai.vision_model,
        )
    if ai is None:
        raise HTTPException(
            503,
            detail={"code": "ai_not_configured"},
        )
    capabilities = ai.capabilities()
    if not capabilities.get("ok"):
        raise HTTPException(
            502,
            detail={
                "code": capabilities.get("code") or "ai_config_failed",
            },
        )
    return capabilities

