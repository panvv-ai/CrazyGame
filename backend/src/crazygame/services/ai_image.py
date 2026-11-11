from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.crazygame.services.catalog import search_instruments

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class ImageValidationError(ValueError):
    pass


class VisionResponseError(ValueError):
    """Raised when the vision model does not return the required JSON array."""


@dataclass(frozen=True)
class VisionItem:
    code: str
    name: str | None
    confidence: str


def validate_image(data: bytes, mime_type: str) -> None:
    if not data:
        raise ImageValidationError("图片为空")
    if len(data) < 12:
        raise ImageValidationError("图片文件过小或损坏")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageValidationError("图片超过 5MB 限制")
    if mime_type not in ALLOWED_MIME:
        raise ImageValidationError("仅支持 JPEG、PNG、WebP 和 GIF")
    valid = {
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/gif": data.startswith((b"GIF87a", b"GIF89a")),
        "image/webp": data.startswith(b"RIFF")
        and len(data) >= 12
        and data[8:12] == b"WEBP",
    }[mime_type]
    if not valid:
        raise ImageValidationError("图片内容与文件类型不匹配")


def _normalize_code(value: object) -> str | None:
    text = str(value or "").strip().upper()
    for suffix in (".SH", ".SZ", ".BJ", ".SS"):
        if text.endswith(suffix) and text[: -len(suffix)].isdigit():
            return text[: -len(suffix)]
    if text.endswith(".HK") and text[:-3].isdigit():
        return text[:-3].zfill(5)
    if text.startswith("US.") and re.fullmatch(r"[A-Z.]{1,8}", text[3:]):
        return text[3:]
    for prefix in ("SH", "SZ", "BJ", "HK"):
        if text.startswith(prefix) and text[len(prefix) :].isdigit():
            return text[len(prefix) :].zfill(6 if prefix != "HK" else 5)
    if re.fullmatch(r"\d{6}", text):
        return text
    if re.fullmatch(r"\d{5}", text):
        return text
    if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", text):
        return text
    return None


def parse_vision_items(text: str) -> list[VisionItem]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        rows = json.loads(cleaned)
    except (TypeError, ValueError, json.JSONDecodeError):
        raise VisionResponseError("invalid vision response")
    if not isinstance(rows, list):
        raise VisionResponseError("vision response must be an array")
    output: list[VisionItem] = []
    seen: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        code = _normalize_code(row.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        confidence = str(row.get("confidence") or "medium").lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        name = row.get("name")
        output.append(
            VisionItem(
                code=code,
                name=str(name).strip() if isinstance(name, str) and name.strip() else None,
                confidence=confidence,
            )
        )
    return output


_VISION_PROMPT = """分析这张股票截图，提取所有可见的股票或 ETF 代码及名称。
只返回 JSON 数组，不要 Markdown：
[{"code":"300750","name":"宁德时代","confidence":"high"}]
code 支持 A 股六位、港股五位、美股 1-5 位字母和场内 ETF 代码。
confidence 只能是 high、medium、low。没有识别结果时返回 []。"""


class ImageRecognitionService:
    def __init__(self, *, ai_client, search=search_instruments):
        self.ai_client = ai_client
        self.search = search

    def recognize(self, image_bytes: bytes, mime_type: str) -> list[dict]:
        validate_image(image_bytes, mime_type)
        raw = self.ai_client.vision_json(
            image_bytes,
            mime_type,
            _VISION_PROMPT,
            timeout=60.0,
        )
        results = []
        for item in parse_vision_items(raw):
            query = f"{item.code} {item.name or ''}".strip()
            try:
                candidates = self.search(query, limit=5)
            except Exception:
                candidates = []
            supported = [
                candidate
                for candidate in candidates
                if candidate.asset_type in {"stock", "listed_etf"}
            ]
            match = next(
                (
                    candidate
                    for candidate in supported
                    if candidate.symbol == item.code
                ),
                None,
            )
            results.append(
                {
                    "code": item.code,
                    "name": item.name
                    or (match.name if match is not None else None),
                    "confidence": item.confidence,
                    "instrument": (
                        {
                            "symbol": match.symbol,
                            "name": match.name,
                            "market": match.market,
                            "asset_type": match.asset_type,
                            "currency": match.currency,
                            "quote_mode": match.quote_mode,
                        }
                        if match is not None
                        else None
                    ),
                }
            )
        return results
