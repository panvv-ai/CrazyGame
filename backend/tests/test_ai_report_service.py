import json
from pathlib import Path

import pytest

from src.crazygame.core.config import AppConfig
from src.crazygame.core.database import Base, build_engine, build_session_factory
from src.crazygame.domain.models import AIReport, Instrument
from src.crazygame.services.ai_report import (
    AIReportCancelled,
    AIReportGenerationError,
    AIReportService,
    parse_report_json,
)


VALID_REPORT = {
    "score": 72,
    "verdict": "bullish",
    "confidence": "high",
    "core_conclusion": "趋势偏强，等待量能确认。",
    "trend": "均线多头排列",
    "hotspots": [
        {
            "title": "宁德时代发布公告",
            "summary": "公司披露经营信息",
            "url": "https://example.test/news",
            "source": "公司公告",
            "published_at": "2026-11-11T10:00:00+08:00",
            "relevance_kind": "direct",
            "relevance_score": 90,
        }
    ],
    "risks": ["高位波动"],
    "catalysts": ["储能需求"],
    "position_advice": {
        "no_position": "等待回踩",
        "has_position": "持有观察",
    },
    "price_plan": {
        "support": 240,
        "resistance": 270,
        "invalidation_reference": 230,
    },
    "action_checklist": ["检查量能"],
    "data_quality": {
        "level": "limited",
        "limitations": ["news cache"],
        "quote_as_of": "2026-11-11T14:30:00+08:00",
        "quote_source": "fixture",
        "quote_freshness": "delayed",
    },
}


class FakeContextService:
    def build(self, instrument, *, language, include_news=True):
        return {
            "instrument": {
                "id": instrument.id,
                "symbol": instrument.symbol,
                "name": instrument.name,
                "market": instrument.market,
                "asset_type": instrument.asset_type,
            },
            "quote": {
                "current_price": 250,
                "as_of": "2026-11-11T14:30:00+08:00",
                "source": "fixture",
                "freshness": "delayed",
            },
            "technical": {"bar_count": 80},
            "holding": None,
            "alerts": [],
            "industry": "电池",
            "concepts": ["新能源"],
            "hotspots": VALID_REPORT["hotspots"],
            "data_quality": VALID_REPORT["data_quality"],
        }


class FakeAI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = None

    def complete(self, messages, **kwargs):
        self.messages = messages
        return self.responses.pop(0)


def make_factory(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'report.db'}",
        encryption_key="ai-report-test-secret-key-that-is-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as db:
        instrument = Instrument(
            symbol="300750",
            name="宁德时代",
            market="CN",
            asset_type="stock",
            currency="CNY",
            quote_mode="realtime",
        )
        db.add(instrument)
        db.commit()
        db.refresh(instrument)
        instrument_id = instrument.id
    return engine, factory, instrument_id


def test_report_service_persists_validated_structured_report(tmp_path: Path):
    engine, factory, instrument_id = make_factory(tmp_path)
    ai = FakeAI(
        [
            "```json\n" + json.dumps(VALID_REPORT, ensure_ascii=False) + "\n```"
        ]
    )
    stages = []
    service = AIReportService(
        session_factory=factory,
        context_service=FakeContextService(),
        ai_client=ai,
    )
    with factory() as db:
        instrument = db.get(Instrument, instrument_id)
        result = service.generate(
            instrument,
            language="zh-CN",
            progress_callback=stages.append,
        )
        row = db.query(AIReport).one()

    assert result["status"] == "success"
    assert row.status == "success"
    assert row.confidence == "medium"
    assert "趋势偏强" in row.content_markdown
    assert "宁德时代发布公告" in row.content_markdown
    saved_report = json.loads(row.report_json)
    assert saved_report["quote"]["current_price"] == 250
    assert saved_report["data_quality"]["quote_source"] == "fixture"
    assert stages[0] == "context"
    assert stages[-1] == "save"
    engine.dispose()


def test_report_service_retries_once_then_marks_failure(tmp_path: Path):
    engine, factory, instrument_id = make_factory(tmp_path)
    ai = FakeAI(["not json", "still not json"])
    service = AIReportService(
        session_factory=factory,
        context_service=FakeContextService(),
        ai_client=ai,
    )
    with factory() as db:
        instrument = db.get(Instrument, instrument_id)
        with pytest.raises(AIReportGenerationError):
            service.generate(instrument, language="zh-CN")
        row = db.query(AIReport).one()

    assert row.status == "failed"
    assert row.error
    engine.dispose()


def test_parse_report_json_rejects_text_without_json_object():
    with pytest.raises(AIReportGenerationError):
        parse_report_json("没有 JSON")


def test_cancelled_report_is_not_persisted(tmp_path: Path):
    engine, factory, instrument_id = make_factory(tmp_path)
    ai = FakeAI([json.dumps(VALID_REPORT, ensure_ascii=False)])
    service = AIReportService(
        session_factory=factory,
        context_service=FakeContextService(),
        ai_client=ai,
    )
    with factory() as db:
        instrument = db.get(Instrument, instrument_id)
        with pytest.raises(AIReportCancelled):
            service.generate(
                instrument,
                language="zh-CN",
                is_cancelled=lambda: True,
            )
        assert db.query(AIReport).count() == 0
    engine.dispose()


def test_report_fixed_text_uses_requested_english_language(tmp_path: Path):
    engine, factory, instrument_id = make_factory(tmp_path)
    ai = FakeAI([json.dumps(VALID_REPORT, ensure_ascii=False)])
    service = AIReportService(
        session_factory=factory,
        context_service=FakeContextService(),
        ai_client=ai,
    )
    with factory() as db:
        instrument = db.get(Instrument, instrument_id)
        service.generate(instrument, language="en-US")
        row = db.query(AIReport).one()

    assert row.title.endswith("AI decision report")
    assert "# Cathay" not in row.content_markdown
    assert "# 宁德时代" in row.content_markdown
    assert "## Key risks" in row.content_markdown
    assert "## Risk" not in row.content_markdown
    engine.dispose()
