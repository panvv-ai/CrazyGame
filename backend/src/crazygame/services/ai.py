from __future__ import annotations

import json
from collections.abc import Iterator

import httpx


def classify_ai_error(exc: Exception) -> str:
    """Map provider failures to stable codes without exposing credentials."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {401, 403}:
            return "ai_auth_failed"
        if status == 429:
            return "ai_rate_limited"
        return "ai_provider_error"
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "ai_timeout"
    if isinstance(exc, httpx.RequestError):
        return "ai_unreachable"
    if isinstance(
        exc,
        (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError),
    ):
        return "ai_invalid_response"
    return "ai_chat_failed"


class AIClient:
    """最小化的 OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        vision_model: str = "",
    ):
        normalized_base_url = base_url.strip().rstrip("/")
        if normalized_base_url.endswith("/chat/completions"):
            normalized_base_url = normalized_base_url.removesuffix(
                "/chat/completions"
            )
        self.base_url = normalized_base_url
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.vision_model = (vision_model or model).strip()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.2,
        timeout: float = 120.0,
    ) -> str:
        """发送对话消息并返回模型生成的纯文本内容。"""
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def tool_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        timeout: float = 60.0,
    ) -> dict:
        """Run one non-streaming tool-decision turn."""
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.1,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        if not isinstance(message, dict):
            raise ValueError("AI provider returned an invalid assistant message")
        return message

    def stream_text(
        self,
        messages: list[dict],
        *,
        timeout: float = 120.0,
    ) -> Iterator[str]:
        """Stream final answer text from an OpenAI-compatible endpoint."""
        with httpx.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "stream": True,
            },
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                content = parse_stream_content_delta(line)
                if content:
                    yield content

    def vision_json(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        *,
        timeout: float = 60.0,
    ) -> str:
        """Send an image to the configured vision model and return raw text."""
        import base64

        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                "temperature": 0.0,
                "max_tokens": 1200,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]

    def capabilities(self) -> dict:
        """Best-effort capability probe for the configured model."""
        result = {"json": False, "tools": False, "stream": False, "vision": False}
        errors: dict[str, str] = {}
        try:
            raw = self.complete(
                [
                    {
                        "role": "user",
                        "content": 'Return only JSON: {"ok":true}',
                    }
                ],
                temperature=0,
                timeout=30,
            )
            result["json"] = isinstance(json.loads(raw.strip()), dict)
        except Exception as exc:
            errors["json"] = classify_ai_error(exc)
            if errors["json"] in {
                "ai_auth_failed",
                "ai_rate_limited",
                "ai_unreachable",
                "ai_timeout",
            }:
                result.update(
                    {
                        "ok": False,
                        "code": errors["json"],
                        "errors": errors,
                    }
                )
                return result
        try:
            message = self.tool_chat(
                [{"role": "user", "content": "Call capability_probe."}],
                [
                    {
                        "type": "function",
                        "function": {
                            "name": "capability_probe",
                            "description": "Capability probe",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
                timeout=30,
            )
            result["tools"] = bool(message.get("tool_calls"))
        except Exception as exc:
            errors["tools"] = classify_ai_error(exc)
        try:
            result["stream"] = bool(
                next(iter(self.stream_text(
                    [{"role": "user", "content": "Reply with ok."}],
                    timeout=30,
                )), "")
            )
        except Exception as exc:
            errors["stream"] = classify_ai_error(exc)
        try:
            import base64

            image = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                "AAAAC0lEQVR42mP8/x8AAusB9Y9ZlKcAAAAASUVORK5CYII="
            )
            result["vision"] = bool(
                self.vision_json(
                    image,
                    "image/png",
                    'Return only JSON: {"ok":true}',
                    timeout=30,
                )
            )
        except Exception as exc:
            errors["vision"] = classify_ai_error(exc)
        ok = any(result[key] for key in ("json", "tools", "stream", "vision"))
        result.update(
            {
                "ok": ok,
                "code": "" if ok else next(iter(errors.values()), "ai_config_failed"),
                "errors": errors,
            }
        )
        return result


def parse_stream_content_delta(line: str) -> str | None:
    if not isinstance(line, str):
        return None
    text = line.strip()
    if not text.startswith("data:"):
        return None
    data = text[5:].strip()
    if not data or data == "[DONE]":
        return None
    try:
        payload = json.loads(data)
        content = payload["choices"][0].get("delta", {}).get("content")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return content if isinstance(content, str) and content else None


def resolve_ai_client(
    *,
    session_factory,
    secret_box,
    fallback_base_url: str,
    fallback_api_key: str,
    fallback_model: str,
    fallback_vision_model: str = "",
):
    """优先读取设置页保存的 AI 配置，缺失时回退到环境变量提供的默认值。"""
    from src.crazygame.domain.models import AppSetting

    base_url = fallback_base_url
    api_key = fallback_api_key
    model = fallback_model
    vision_model = fallback_vision_model
    with session_factory() as db:
        row = db.get(AppSetting, "ai")
        if row is not None:
            try:
                config = json.loads(row.value)
            except json.JSONDecodeError:
                config = {}
            base_url = config.get("base_url") or base_url
            model = config.get("model") or model
            vision_model = config.get("vision_model") or vision_model
            stored_key = config.get("api_key") or ""
            if stored_key and secret_box is not None:
                try:
                    api_key, layers = secret_box.decrypt_nested(stored_key)
                except Exception:
                    api_key = ""
                else:
                    if layers != 1 and api_key:
                        config["api_key"] = secret_box.encrypt(api_key)
                        row.value = json.dumps(config, ensure_ascii=False)
                        db.commit()
            elif stored_key:
                api_key = stored_key
    if not api_key or not base_url or not model:
        return None
    return AIClient(base_url, api_key, model, vision_model)


def resolve_runtime_ai_client(
    *,
    session_factory,
    secret_box,
    fallback_base_url: str,
    fallback_api_key: str,
    fallback_model: str,
    fallback_vision_model: str = "",
    runtime_client=None,
):
    """Resolve current saved settings before a client captured at startup."""
    return resolve_ai_client(
        session_factory=session_factory,
        secret_box=secret_box,
        fallback_base_url=fallback_base_url,
        fallback_api_key=fallback_api_key,
        fallback_model=fallback_model,
        fallback_vision_model=fallback_vision_model,
    ) or runtime_client

