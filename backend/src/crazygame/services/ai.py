from __future__ import annotations

import json

import httpx


class AIClient:
    """最小化的 OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def complete(self, messages: list[dict[str, str]]) -> str:
        """发送对话消息并返回模型生成的纯文本内容。"""
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]


def resolve_ai_client(
    *,
    session_factory,
    secret_box,
    fallback_base_url: str,
    fallback_api_key: str,
    fallback_model: str,
):
    """优先读取设置页保存的 AI 配置，缺失时回退到环境变量提供的默认值。"""
    from src.crazygame.domain.models import AppSetting

    base_url = fallback_base_url
    api_key = fallback_api_key
    model = fallback_model
    with session_factory() as db:
        row = db.get(AppSetting, "ai")
        if row is not None:
            try:
                config = json.loads(row.value)
            except json.JSONDecodeError:
                config = {}
            base_url = config.get("base_url") or base_url
            model = config.get("model") or model
            stored_key = config.get("api_key") or ""
            if stored_key and secret_box is not None:
                try:
                    api_key = secret_box.decrypt(stored_key)
                except Exception:
                    api_key = stored_key
            elif stored_key:
                api_key = stored_key
    if not api_key or not base_url or not model:
        return None
    return AIClient(base_url, api_key, model)

