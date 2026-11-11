from pathlib import Path

from src.crazygame.core.config import AppConfig
from src.crazygame.core.database import Base, build_engine, build_session_factory
from src.crazygame.services.ai_chat import AIChatService


def make_factory(tmp_path: Path):
    config = AppConfig(
        data_dir=tmp_path,
        database_url=f"sqlite+pysqlite:///{tmp_path / 'chat.db'}",
        encryption_key="ai-chat-test-secret-key-that-is-long-enough",
    )
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    return engine, build_session_factory(engine)


class Candidate:
    symbol = "600519"
    name = "贵州茅台"
    market = "CN"
    asset_type = "stock"
    currency = "CNY"
    quote_mode = "realtime"


def test_first_turn_resolves_named_stock_and_follow_up_reuses_active_instrument(
    tmp_path: Path,
    monkeypatch,
):
    engine, factory = make_factory(tmp_path)
    service = AIChatService(factory)
    monkeypatch.setattr(
        "src.crazygame.services.ai_chat.search_instruments",
        lambda query, limit=10: [Candidate()],
    )

    first = service.prepare_turn(message="分析贵州茅台")
    second = service.prepare_turn(
        message="那风险呢",
        session_id=first.session_id,
    )

    assert first.instrument.symbol == "600519"
    assert second.instrument.symbol == "600519"
    assert first.request_id != second.request_id
    engine.dispose()


def test_ambiguous_name_returns_candidates_without_binding_a_stock(
    tmp_path: Path,
    monkeypatch,
):
    engine, factory = make_factory(tmp_path)
    service = AIChatService(factory)
    monkeypatch.setattr(
        "src.crazygame.services.ai_chat.search_instruments",
        lambda query, limit=10: [
            Candidate(),
            type(
                "Other",
                (),
                {
                    "symbol": "600520",
                    "name": "贵州茅台酒",
                    "market": "CN",
                    "asset_type": "stock",
                    "currency": "CNY",
                    "quote_mode": "realtime",
                },
            )(),
        ],
    )

    turn = service.prepare_turn(message="分析贵州茅台")

    assert turn.instrument is None
    assert len(turn.candidates) == 2
    engine.dispose()


def test_question_with_bare_stock_name_still_resolves_when_unambiguous(
    tmp_path: Path,
    monkeypatch,
):
    engine, factory = make_factory(tmp_path)
    service = AIChatService(factory)
    monkeypatch.setattr(
        "src.crazygame.services.ai_chat.search_instruments",
        lambda query, limit=10: [Candidate()] if "茅台" in query else [],
    )

    turn = service.prepare_turn(message="茅台现在能买吗")

    assert turn.instrument.symbol == "600519"
    engine.dispose()


def test_common_english_words_are_not_treated_as_us_tickers():
    assert AIChatService._search_query("What is the trend?") is None
    assert AIChatService._search_query("the trend") is None
    assert AIChatService._search_query("AI分析") is None
    assert AIChatService._search_query("分析 AI") is None
    assert AIChatService._search_query("分析 AAPL") == "AAPL"
    assert AIChatService._search_query("AAPL现在能买吗") == "AAPL"


def test_explicit_new_stock_in_follow_up_switches_active_instrument(
    tmp_path: Path,
    monkeypatch,
):
    engine, factory = make_factory(tmp_path)
    service = AIChatService(factory)

    def fake_search(query, limit=10):
        if "茅台" in query:
            return [Candidate()]
        return [
            type(
                "Catl",
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

    monkeypatch.setattr(
        "src.crazygame.services.ai_chat.search_instruments",
        fake_search,
    )
    first = service.prepare_turn(message="分析贵州茅台")
    second = service.prepare_turn(
        message="分析宁德时代",
        session_id=first.session_id,
    )

    assert second.instrument.symbol == "300750"
    assert second.history == []
    engine.dispose()
