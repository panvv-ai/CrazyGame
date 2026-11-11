from dataclasses import dataclass

import pytest

from src.crazygame.services.ai_image import (
    ImageRecognitionService,
    ImageValidationError,
    VisionResponseError,
    parse_vision_items,
    validate_image,
)


def test_validate_image_checks_magic_bytes_instead_of_client_mime():
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    validate_image(png, "image/png")

    with pytest.raises(ImageValidationError):
        validate_image(b"not-an-image", "image/png")
    with pytest.raises(ImageValidationError):
        validate_image(b"GIF89a", "image/gif")


def test_parse_vision_items_accepts_fenced_json_and_drops_invalid_codes():
    text = """```json
[
  {"code":"300750","name":"宁德时代","confidence":"high"},
  {"code":"159915","name":"创业板ETF","confidence":"medium"},
  {"code":"00700.HK","name":"腾讯控股","confidence":"high"},
  {"code":"NOT VALID","name":"错误","confidence":"high"}
]
```"""

    items = parse_vision_items(text)

    assert [(item.code, item.name, item.confidence) for item in items] == [
        ("300750", "宁德时代", "high"),
        ("159915", "创业板ETF", "medium"),
        ("00700", "腾讯控股", "high"),
    ]


def test_parse_vision_items_rejects_malformed_model_response():
    with pytest.raises(VisionResponseError):
        parse_vision_items("not-json")


@dataclass
class VisionAI:
    def vision_json(self, image_bytes, mime_type, prompt, *, timeout):
        return '[{"code":"300750","name":"宁德时代","confidence":"high"}]'


class Search:
    def __call__(self, query, *, limit=10):
        if "300750" not in query:
            return []
        return [
            type(
                "Candidate",
                (),
                {
                    "symbol": "300750",
                    "name": "宁德时代",
                    "market": "CN",
                    "asset_type": "stock",
                    "currency": "CNY",
                    "quote_mode": "realtime",
                },
            )()
        ]


def test_recognition_resolves_candidates_without_persisting_them():
    service = ImageRecognitionService(ai_client=VisionAI(), search=Search())
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32

    items = service.recognize(png, "image/png")

    assert items[0]["code"] == "300750"
    assert items[0]["instrument"]["market"] == "CN"
    assert items[0]["confidence"] == "high"
