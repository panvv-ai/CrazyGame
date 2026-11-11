from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class AIInstrument(BaseModel):
    id: int
    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    market: str = ""
    asset_type: str = ""


class AIHotspot(BaseModel):
    title: str = Field(min_length=1)
    summary: str = ""
    url: str = ""
    source: str = ""
    published_at: datetime | str | None = None
    relevance_kind: Literal["direct", "sector", "macro"] = "macro"
    relevance_score: int = Field(default=0, ge=0, le=100)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        if not value:
            return ""
        parsed = urlparse(value)
        return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""


class AIPositionAdvice(BaseModel):
    no_position: str = ""
    has_position: str = ""


class AIPricePlan(BaseModel):
    support: float | None = Field(default=None, ge=0)
    resistance: float | None = Field(default=None, ge=0)
    invalidation_reference: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_range(self):
        if (
            self.support is not None
            and self.resistance is not None
            and self.support > self.resistance
        ):
            raise ValueError("support must not exceed resistance")
        return self


class AIDataQuality(BaseModel):
    level: Literal["good", "limited", "poor", "unknown"] = "unknown"
    limitations: list[str] = Field(default_factory=list)
    quote_as_of: str = ""
    quote_source: str = ""
    quote_freshness: str = ""


class AIDecisionReportData(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: Literal["bullish", "neutral", "bearish"]
    confidence: Literal["high", "medium", "low"]
    core_conclusion: str = Field(min_length=1)
    trend: str = ""
    quote: dict = Field(default_factory=dict)
    hotspots: list[AIHotspot] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    position_advice: AIPositionAdvice = Field(default_factory=AIPositionAdvice)
    price_plan: AIPricePlan = Field(default_factory=AIPricePlan)
    action_checklist: list[str] = Field(default_factory=list)
    data_quality: AIDataQuality = Field(default_factory=AIDataQuality)

    @field_validator("hotspots")
    @classmethod
    def limit_hotspots(cls, value: list[AIHotspot]) -> list[AIHotspot]:
        return value[:3]


class AIDecisionReport(BaseModel):
    instrument: AIInstrument
    score: int = Field(ge=0, le=100)
    verdict: Literal["bullish", "neutral", "bearish"]
    confidence: Literal["high", "medium", "low"]
    core_conclusion: str = Field(min_length=1)
    trend: str = ""
    quote: dict = Field(default_factory=dict)
    hotspots: list[AIHotspot] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    position_advice: AIPositionAdvice = Field(default_factory=AIPositionAdvice)
    price_plan: AIPricePlan = Field(default_factory=AIPricePlan)
    action_checklist: list[str] = Field(default_factory=list)
    data_quality: AIDataQuality = Field(default_factory=AIDataQuality)
    disclaimer: str = ""


def _disclaimer(language: str) -> str:
    if language == "en-US":
        return (
            "AI-generated research for personal reference only. "
            "It is not investment advice."
        )
    return "AI 生成内容仅供个人研究参考，不构成投资建议。"


def _cap_confidence(
    confidence: str,
    quality: AIDataQuality,
) -> str:
    if quality.level == "poor":
        return "low"
    if quality.level in {"limited", "unknown"} or quality.limitations:
        return "medium" if confidence == "high" else confidence
    return confidence


def normalize_ai_report_payload(
    payload: dict,
    *,
    instrument: dict,
    language: str,
) -> AIDecisionReport:
    """Validate model JSON and enforce evidence-aware confidence limits."""
    data = AIDecisionReportData.model_validate(payload)
    data = data.model_copy(
        update={"confidence": _cap_confidence(data.confidence, data.data_quality)}
    )
    return AIDecisionReport(
        instrument=AIInstrument.model_validate(instrument),
        **data.model_dump(),
        disclaimer=_disclaimer(language),
    )
