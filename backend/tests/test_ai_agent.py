import json

from src.crazygame.services.ai_agent import AIAgentRunner, BoundAITools


def fixture_context() -> dict:
    return {
        "instrument": {
            "id": 1,
            "symbol": "300750",
            "name": "宁德时代",
            "market": "CN",
            "asset_type": "stock",
        },
        "quote": {
            "current_price": 250.0,
            "change_pct": 1.8,
            "as_of": "2026-11-11T14:30:00+08:00",
            "source": "fixture",
            "freshness": "delayed",
        },
        "technical": {
            "bar_count": 80,
            "ma": {"ma5": 248.0, "ma10": 245.0, "ma20": 240.0},
            "support": 240.0,
            "resistance": 260.0,
        },
        "holding": None,
        "alerts": [],
        "hotspots": [
            {
                "title": "宁德时代发布公告",
                "url": "https://example.test/news",
                "relevance_kind": "direct",
            }
        ],
        "latest_report": None,
        "data_quality": {"level": "limited", "limitations": []},
    }


def test_bound_tools_are_read_only_and_do_not_accept_stock_code():
    tools = BoundAITools(fixture_context())

    assert [tool["function"]["name"] for tool in tools.definitions] == [
        "get_market_snapshot",
        "get_price_history",
        "get_technical_snapshot",
        "get_portfolio_context",
        "search_recent_intel",
        "get_latest_ai_report",
    ]
    for tool in tools.definitions:
        properties = tool["function"]["parameters"]["properties"]
        assert "stock_code" not in properties

    result = tools.execute("get_market_snapshot", {})

    assert result["ok"] is True
    assert result["result"]["current_price"] == 250.0


class FakeToolAI:
    def __init__(self):
        self.calls = 0
        self.final_messages = None

    def tool_chat(self, messages, tools, *, timeout=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "get_technical_snapshot",
                            "arguments": "{}",
                        },
                    }
                ],
            }
        return {"role": "assistant", "content": "准备生成正文"}

    def stream_text(self, messages, *, timeout=None):
        self.final_messages = messages
        yield "趋势偏强，"
        yield "但等待量能确认。"


def test_agent_runs_tool_phase_then_streams_final_answer():
    ai = FakeToolAI()
    runner = AIAgentRunner(ai_client=ai, context=fixture_context(), language="zh-CN")

    prepared, tool_log = runner.prepare(
        "分析一下",
        history=[{"role": "user", "content": "先看看趋势"}],
    )
    answer = "".join(runner.stream_answer(prepared))

    assert tool_log == [
        {
            "name": "get_technical_snapshot",
            "ok": True,
            "arguments": {},
        }
    ]
    assert answer == "趋势偏强，但等待量能确认。"
    assert ai.final_messages[0]["role"] == "system"
    assert any(message.get("role") == "tool" for message in ai.final_messages)


def test_prepare_fails_open_when_provider_rejects_tools():
    class NoToolAI:
        def tool_chat(self, messages, tools, *, timeout=None):
            raise ValueError("tools unsupported")

        def stream_text(self, messages, *, timeout=None):
            self.messages = messages
            yield "使用预取数据生成回答"

    ai = NoToolAI()
    runner = AIAgentRunner(ai_client=ai, context=fixture_context(), language="zh-CN")

    prepared, tool_log = runner.prepare("分析一下", history=[])
    answer = "".join(runner.stream_answer(prepared))

    assert tool_log == [{"name": "prefetch_context", "ok": False, "arguments": {}}]
    assert answer == "使用预取数据生成回答"
    assert "宁德时代" in json.dumps(ai.messages, ensure_ascii=False)


def test_agent_falls_back_when_wall_clock_budget_is_exhausted():
    class NeverCalledAI:
        def tool_chat(self, messages, tools, *, timeout=None):
            raise AssertionError("model must not run after the budget expires")

        def stream_text(self, messages, *, timeout=None):
            yield "降级回答"

    runner = AIAgentRunner(
        ai_client=NeverCalledAI(),
        context=fixture_context(),
        language="zh-CN",
        max_wall_seconds=0,
    )

    prepared, tool_log = runner.prepare("分析一下", history=[])
    answer = "".join(runner.stream_answer(prepared))

    assert tool_log[0]["name"] == "prefetch_context"
    assert answer == "降级回答"


def test_agent_without_tool_calls_still_receives_authoritative_context():
    class NoToolsAI:
        def tool_chat(self, messages, tools, *, timeout=None):
            return {"role": "assistant", "content": "直接回答"}

        def stream_text(self, messages, *, timeout=None):
            self.messages = messages
            yield "有证据的回答"

    ai = NoToolsAI()
    runner = AIAgentRunner(ai_client=ai, context=fixture_context(), language="zh-CN")

    prepared, _ = runner.prepare("分析一下", history=[])
    "".join(runner.stream_answer(prepared))

    assert any(
        "服务端预取权威证据" in message.get("content", "")
        for message in ai.messages
    )


def test_oversized_tool_result_is_truncated_as_valid_json():
    context = fixture_context()
    context["latest_report"] = {"payload": "x" * 20_000}

    class OversizedToolAI:
        def __init__(self):
            self.calls = 0

        def tool_chat(self, messages, tools, *, timeout=None):
            self.calls += 1
            if self.calls == 1:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-big",
                            "type": "function",
                            "function": {
                                "name": "get_latest_ai_report",
                                "arguments": "{}",
                            },
                        }
                    ],
                }
            return {"role": "assistant", "content": "ok"}

        def stream_text(self, messages, *, timeout=None):
            yield "ok"

    runner = AIAgentRunner(
        ai_client=OversizedToolAI(),
        context=context,
        language="zh-CN",
    )
    prepared, _ = runner.prepare("分析", history=[])
    tool_message = next(
        message for message in prepared.messages if message.get("role") == "tool"
    )
    payload = json.loads(tool_message["content"])

    assert payload["truncated"] is True


def test_oversized_prefetched_context_still_serializes_as_json():
    context = fixture_context()
    context["latest_report"] = {"payload": "x" * 40_000}

    class NoToolsAI:
        def tool_chat(self, messages, tools, *, timeout=None):
            return {"role": "assistant", "content": "ok"}

        def stream_text(self, messages, *, timeout=None):
            self.messages = messages
            yield "ok"

    ai = NoToolsAI()
    runner = AIAgentRunner(ai_client=ai, context=context, language="zh-CN")
    prepared, _ = runner.prepare("分析", history=[])
    "".join(runner.stream_answer(prepared))
    evidence = next(
        message["content"]
        for message in ai.messages
        if "服务端预取权威证据" in message.get("content", "")
    )
    payload = json.loads(evidence.split("\n", 1)[1])

    assert payload["truncated"] is True
