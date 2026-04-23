"""Tests for AlphaWhale LangGraph agent.

All tests use mocked LLM responses to avoid API calls.
Tests verify graph structure, routing logic, and end-to-end execution.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from testing_utils import FakeLogfire

from agent.graph import (
    TOOLS,
    TOOLS_BY_NAME,
    agent_node,
    build_graph,
    risk_assessment_node,
    route_after_tools,
    run,
    should_continue,
    tools_node,
)
from agent.models import RiskLevel, TradeSignal


@pytest.fixture(autouse=True)
def reset_observability_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset graph-level observability caches between tests."""
    monkeypatch.setattr("agent.graph._tool_latency_histogram", None)
    monkeypatch.setattr("agent.graph._tool_error_counter", None)


# --- Graph structure ---


class TestGraphStructure:
    def test_graph_compiles(self):
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_expected_nodes(self):
        graph = build_graph()
        node_names = set(graph.nodes.keys())
        assert "agent_node" in node_names
        assert "tools_node" in node_names
        assert "risk_assessment_node" in node_names
        assert "human_approval_node" in node_names


# --- Routing logic ---


class TestShouldContinue:
    def test_routes_to_tools_when_tool_calls_present(self):
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_stock_price",
                    "args": {"ticker": "BTC"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        )
        state = {"messages": [HumanMessage(content="hi"), ai_msg]}
        assert should_continue(state) == "tools_node"

    def test_routes_to_end_when_no_tool_calls(self):
        ai_msg = AIMessage(content="Bitcoin is at $50,000.")
        state = {"messages": [HumanMessage(content="hi"), ai_msg]}
        assert should_continue(state) == "__end__"

    def test_routes_to_end_for_empty_tool_calls(self):
        ai_msg = AIMessage(content="Here's the answer.", tool_calls=[])
        state = {"messages": [HumanMessage(content="hi"), ai_msg]}
        assert should_continue(state) == "__end__"


# --- Agent node ---


class TestAgentNode:
    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    def test_agent_node_returns_messages(self, mock_get_model: MagicMock, _mock_extract: MagicMock):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Hello!")
        mock_get_model.return_value = mock_llm

        state = {"messages": [HumanMessage(content="What is BTC price?")]}
        result = agent_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Hello!"

    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    def test_agent_node_passes_history(self, mock_get_model: MagicMock, _mock_extract: MagicMock):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Done")
        mock_get_model.return_value = mock_llm

        history = [
            HumanMessage(content="q1"),
            AIMessage(content="a1"),
            HumanMessage(content="q2"),
        ]
        agent_node({"messages": history})

        # LLM should receive system prompt + full history
        call_args = mock_llm.invoke.call_args[0][0]
        assert len(call_args) == 4  # system + 3 history messages


# --- Tools node ---


class TestToolsNode:
    def test_executes_get_stock_price(self):
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        tool_call = {
            "name": "get_stock_price",
            "args": {"ticker": "AAPL"},
            "id": "call_1",
            "type": "tool_call",
        }
        ai_msg = AIMessage(content="", tool_calls=[tool_call])
        state = {"messages": [HumanMessage(content="price?"), ai_msg]}

        with patch("agent.tools._get_supabase", return_value=mock_client):
            result = tools_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], ToolMessage)
        assert result["messages"][0].tool_call_id == "call_1"

    def test_executes_get_technical_indicators(self):
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        tool_call = {
            "name": "get_technical_indicators",
            "args": {"ticker": "NVDA"},
            "id": "call_2",
            "type": "tool_call",
        }
        ai_msg = AIMessage(content="", tool_calls=[tool_call])
        state = {"messages": [HumanMessage(content="indicators?"), ai_msg]}

        with patch("agent.tools._get_supabase", return_value=mock_client):
            result = tools_node(state)

        assert len(result["messages"]) == 1
        assert result["messages"][0].tool_call_id == "call_2"

    def test_executes_compare_assets(self):
        from unittest.mock import MagicMock, patch

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        tool_call = {
            "name": "compare_assets",
            "args": {"tickers": ["AAPL", "MSFT"]},
            "id": "call_3",
            "type": "tool_call",
        }
        ai_msg = AIMessage(content="", tool_calls=[tool_call])
        state = {"messages": [HumanMessage(content="compare?"), ai_msg]}

        with patch("agent.tools._get_supabase", return_value=mock_client):
            result = tools_node(state)

        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], ToolMessage)
        assert result["messages"][0].tool_call_id == "call_3"

    def test_handles_unknown_tool_name(self):
        tool_call = {"name": "nonexistent_tool", "args": {}, "id": "call_x", "type": "tool_call"}
        ai_msg = AIMessage(content="", tool_calls=[tool_call])
        state = {"messages": [HumanMessage(content="test"), ai_msg]}

        result = tools_node(state)

        assert len(result["messages"]) == 1
        assert "Error: unknown tool" in result["messages"][0].content
        assert result["messages"][0].tool_call_id == "call_x"

    def test_tools_by_name_has_all_tools(self):
        assert set(TOOLS_BY_NAME.keys()) == {
            "get_stock_price",
            "get_technical_indicators",
            "compare_assets",
            "generate_trade_signal",
            "query_knowledge_base",
        }
        assert len(TOOLS_BY_NAME) == len(TOOLS)

    @patch("agent.tools.extract")
    def test_executes_generate_trade_signal(self, mock_extract: MagicMock):
        """Trade signal tool calls extract() and returns dict."""
        mock_extract.return_value = TradeSignal(
            ticker="NVDA",
            signal="bullish",
            confidence=0.85,
            reasoning="EMA crossover confirmed",
            indicators_used=["ema_8", "ema_80"],
        )
        tool_call = {
            "name": "generate_trade_signal",
            "args": {"ticker": "NVDA", "analysis_context": "EMA 8 crossed above EMA 80"},
            "id": "call_sig",
            "type": "tool_call",
        }
        ai_msg = AIMessage(content="", tool_calls=[tool_call])
        state = {"messages": [HumanMessage(content="outlook?"), ai_msg]}

        result = tools_node(state)

        assert len(result["messages"]) == 1
        assert result["messages"][0].tool_call_id == "call_sig"
        assert "trade_signals" in result
        assert len(result["trade_signals"]) == 1
        assert result["trade_signals"][0].ticker == "NVDA"

    @patch("agent.graph.logger")
    @patch("agent.tools.extract")
    def test_trade_signal_surfaces_error_on_extraction_failure(
        self, mock_extract: MagicMock, _mock_logger: MagicMock
    ):
        """Trade signal extraction failure surfaces as a tool error, not a neutral signal."""
        from core import ExtractionError

        mock_extract.side_effect = ExtractionError("fail")
        tool_call = {
            "name": "generate_trade_signal",
            "args": {"ticker": "AAPL", "analysis_context": "some analysis"},
            "id": "call_fail",
            "type": "tool_call",
        }
        ai_msg = AIMessage(content="", tool_calls=[tool_call])
        state = {"messages": [HumanMessage(content="test"), ai_msg]}

        result = tools_node(state)

        assert len(result["messages"]) == 1
        # Error is surfaced in the ToolMessage, no signal added to state
        assert "Error" in result["messages"][0].content
        assert "trade_signals" not in result

    def test_records_success_telemetry_for_tool_call(self, monkeypatch: pytest.MonkeyPatch):
        fake_logfire = FakeLogfire()
        fake_tool = MagicMock()
        fake_tool.invoke.return_value = {"ok": True}
        monkeypatch.setattr("agent.graph.get_logfire_instance", lambda: fake_logfire)
        monkeypatch.setitem(TOOLS_BY_NAME, "get_stock_price", fake_tool)

        tool_call = {
            "name": "get_stock_price",
            "args": {"ticker": "AAPL"},
            "id": "call_obs_ok",
            "type": "tool_call",
        }
        state = {
            "messages": [
                HumanMessage(content="price?"),
                AIMessage(content="", tool_calls=[tool_call]),
            ]
        }

        result = tools_node(state)

        assert len(result["messages"]) == 1
        histogram_calls = fake_logfire.histograms["alpha_whale.agent.tool.duration"].calls
        assert histogram_calls[0][1] == {"tool_name": "get_stock_price", "success": True}
        assert "alpha_whale.agent.tool.errors" not in fake_logfire.counters
        assert fake_logfire.spans[0].name == "agent.tool_call"
        assert fake_logfire.spans[0].initial_attributes == {"tool_name": "get_stock_price"}
        assert fake_logfire.spans[0].attributes["tool.success"] is True

    def test_records_failure_telemetry_for_tool_error(self, monkeypatch: pytest.MonkeyPatch):
        fake_logfire = FakeLogfire()
        fake_tool = MagicMock()
        fake_tool.invoke.side_effect = RuntimeError("boom")
        monkeypatch.setattr("agent.graph.get_logfire_instance", lambda: fake_logfire)
        monkeypatch.setitem(TOOLS_BY_NAME, "get_stock_price", fake_tool)

        tool_call = {
            "name": "get_stock_price",
            "args": {"ticker": "AAPL"},
            "id": "call_obs_fail",
            "type": "tool_call",
        }
        state = {
            "messages": [
                HumanMessage(content="price?"),
                AIMessage(content="", tool_calls=[tool_call]),
            ]
        }

        result = tools_node(state)

        assert "Error: tool 'get_stock_price' failed" in result["messages"][0].content
        histogram_calls = fake_logfire.histograms["alpha_whale.agent.tool.duration"].calls
        counter_calls = fake_logfire.counters["alpha_whale.agent.tool.errors"].calls
        assert histogram_calls[0][1] == {"tool_name": "get_stock_price", "success": False}
        assert counter_calls == [
            (1, {"tool_name": "get_stock_price", "error_type": "RuntimeError"})
        ]
        assert fake_logfire.spans[0].attributes["tool.success"] is False
        assert fake_logfire.spans[0].attributes["error.type"] == "RuntimeError"


# --- Risk assessment node ---


def _make_signal(signal: str = "bullish", confidence: float = 0.9) -> TradeSignal:
    """Helper to create a TradeSignal for testing."""
    return TradeSignal(
        ticker="NVDA",
        signal=signal,
        confidence=confidence,
        reasoning="test",
        indicators_used=["ema_8"],
    )


class TestRiskAssessmentNode:
    def test_high_risk_for_high_confidence_bullish(self):
        state = {"messages": [], "trade_signals": [_make_signal("bullish", 0.9)]}
        result = risk_assessment_node(state)
        assert result["risk_level"] == RiskLevel.HIGH
        assert result["pending_approval"] is True

    def test_high_risk_for_high_confidence_bearish(self):
        state = {"messages": [], "trade_signals": [_make_signal("bearish", 0.85)]}
        result = risk_assessment_node(state)
        assert result["risk_level"] == RiskLevel.HIGH
        assert result["pending_approval"] is True

    def test_medium_risk_for_moderate_confidence(self):
        state = {"messages": [], "trade_signals": [_make_signal("bullish", 0.6)]}
        result = risk_assessment_node(state)
        assert result["risk_level"] == RiskLevel.MEDIUM
        assert result["pending_approval"] is False

    def test_low_risk_for_low_confidence(self):
        state = {"messages": [], "trade_signals": [_make_signal("neutral", 0.3)]}
        result = risk_assessment_node(state)
        assert result["risk_level"] == RiskLevel.LOW
        assert result["pending_approval"] is False

    def test_medium_risk_for_high_confidence_neutral(self):
        """Neutral signal at 0.9 confidence is medium, not high."""
        state = {"messages": [], "trade_signals": [_make_signal("neutral", 0.9)]}
        result = risk_assessment_node(state)
        assert result["risk_level"] == RiskLevel.MEDIUM

    def test_no_signals_returns_low(self):
        state = {"messages": [], "trade_signals": []}
        result = risk_assessment_node(state)
        assert result["risk_level"] == RiskLevel.LOW
        assert result["pending_approval"] is False


class TestRouteAfterTools:
    def test_routes_to_risk_when_trade_signal_generated(self):
        """Routes to risk_assessment_node when generate_trade_signal was called."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "generate_trade_signal",
                    "args": {"ticker": "NVDA", "analysis_context": "test"},
                    "id": "call_sig",
                    "type": "tool_call",
                }
            ],
        )
        tool_msg = ToolMessage(content="signal result", tool_call_id="call_sig")
        state = {
            "messages": [HumanMessage(content="q"), ai_msg, tool_msg],
            "trade_signals": [_make_signal()],
        }
        assert route_after_tools(state) == "risk_assessment_node"

    def test_routes_to_agent_for_regular_tools(self):
        """Routes back to agent_node for non-signal tools."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_stock_price",
                    "args": {"ticker": "AAPL"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        )
        tool_msg = ToolMessage(content="price data", tool_call_id="call_1")
        state = {
            "messages": [HumanMessage(content="q"), ai_msg, tool_msg],
            "trade_signals": [],
        }
        assert route_after_tools(state) == "agent_node"


# --- End-to-end (mocked LLM) ---


class TestRunFunction:
    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    def test_run_returns_final_answer(self, mock_get_model: MagicMock, _mock_extract: MagicMock):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="BTC is at $50,000.")
        mock_get_model.return_value = mock_llm

        result = run("What is the BTC price?")
        assert result == "BTC is at $50,000."

    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    def test_run_with_tool_call_loop(self, mock_get_model: MagicMock, _mock_extract: MagicMock):
        """Simulate: LLM requests tool -> tool runs -> LLM gives final answer."""
        from unittest.mock import patch as inner_patch

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        tool_call_response = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_stock_price",
                    "args": {"ticker": "BTC"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        )
        final_response = AIMessage(content="Bitcoin is currently at $55,000.")

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [tool_call_response, final_response]
        mock_get_model.return_value = mock_llm

        with inner_patch("agent.tools._get_supabase", return_value=mock_supabase):
            result = run("What is Bitcoin's price?")
        assert result == "Bitcoin is currently at $55,000."
        assert mock_llm.invoke.call_count == 2


# --- Checkpointing + Human-in-the-loop ---


def _compile_fresh_graph():
    """Compile a fresh graph with its own MemorySaver for test isolation."""
    return build_graph().compile(checkpointer=MemorySaver())


class TestCheckpointing:
    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    def test_thread_persists_messages_across_invocations(
        self, mock_get_model: MagicMock, _mock_extract: MagicMock
    ):
        """Messages accumulate when using the same thread_id."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="BTC is at $50k."),
            AIMessage(content="ETH is at $3k."),
        ]
        mock_get_model.return_value = mock_llm

        graph = _compile_fresh_graph()
        config = {"configurable": {"thread_id": "test-thread-1"}}

        # First turn
        result1 = graph.invoke({"messages": [HumanMessage(content="BTC price?")]}, config)
        assert result1["messages"][-1].content == "BTC is at $50k."

        # Second turn — same thread_id, messages should accumulate
        result2 = graph.invoke({"messages": [HumanMessage(content="ETH price?")]}, config)
        assert result2["messages"][-1].content == "ETH is at $3k."
        # Should have 4 messages: human1, ai1, human2, ai2
        assert len(result2["messages"]) == 4

    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    def test_different_threads_are_isolated(
        self, mock_get_model: MagicMock, _mock_extract: MagicMock
    ):
        """Different thread_ids maintain separate conversation state."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            AIMessage(content="Answer A"),
            AIMessage(content="Answer B"),
        ]
        mock_get_model.return_value = mock_llm

        graph = _compile_fresh_graph()

        r1 = graph.invoke(
            {"messages": [HumanMessage(content="Q1")]},
            {"configurable": {"thread_id": "thread-a"}},
        )
        r2 = graph.invoke(
            {"messages": [HumanMessage(content="Q2")]},
            {"configurable": {"thread_id": "thread-b"}},
        )

        # Each thread should have only 2 messages (human + ai), not 4
        assert len(r1["messages"]) == 2
        assert len(r2["messages"]) == 2


class TestHumanInTheLoop:
    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    @patch("agent.tools.extract")
    def test_high_risk_signal_triggers_interrupt(
        self,
        mock_extract: MagicMock,
        mock_get_model: MagicMock,
        _mock_extract_intent: MagicMock,
    ):
        """Graph pauses at human_approval_node for high-confidence bullish signal."""
        high_confidence_signal = TradeSignal(
            ticker="NVDA",
            signal="bullish",
            confidence=0.92,
            reasoning="Strong EMA crossover",
            indicators_used=["ema_8", "ema_80"],
        )
        mock_extract.return_value = high_confidence_signal

        # LLM calls generate_trade_signal, then would give final answer
        tool_call_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "generate_trade_signal",
                    "args": {"ticker": "NVDA", "analysis_context": "EMA 8 crossed above EMA 80"},
                    "id": "call_sig",
                    "type": "tool_call",
                }
            ],
        )
        final_msg = AIMessage(content="NVDA looks bullish!")
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [tool_call_msg, final_msg]
        mock_get_model.return_value = mock_llm

        graph = _compile_fresh_graph()
        config = {"configurable": {"thread_id": "interrupt-test"}}

        result = graph.invoke(
            {"messages": [HumanMessage(content="What's the outlook for NVDA?")]},
            config,
        )

        # Graph should have paused — __interrupt__ present in result
        assert "__interrupt__" in result
        interrupts = result["__interrupt__"]
        assert len(interrupts) == 1
        assert interrupts[0].value["type"] == "approval_request"
        assert interrupts[0].value["signal"]["ticker"] == "NVDA"
        assert "92%" in interrupts[0].value["message"]

    @patch("agent.graph.extract_user_intent")
    @patch("agent.graph.get_model")
    @patch("agent.tools.extract")
    def test_resume_after_approval(
        self,
        mock_extract: MagicMock,
        mock_get_model: MagicMock,
        _mock_extract_intent: MagicMock,
    ):
        """After approval, graph resumes and LLM produces final response."""
        high_confidence_signal = TradeSignal(
            ticker="NVDA",
            signal="bullish",
            confidence=0.92,
            reasoning="Strong EMA crossover",
            indicators_used=["ema_8", "ema_80"],
        )
        mock_extract.return_value = high_confidence_signal

        tool_call_msg = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "generate_trade_signal",
                    "args": {"ticker": "NVDA", "analysis_context": "EMA crossover"},
                    "id": "call_sig",
                    "type": "tool_call",
                }
            ],
        )
        final_msg = AIMessage(content="NVDA looks bullish — EMA crossover confirmed!")

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [tool_call_msg, final_msg]
        mock_get_model.return_value = mock_llm

        graph = _compile_fresh_graph()
        config = {"configurable": {"thread_id": "resume-test"}}

        result = graph.invoke(
            {"messages": [HumanMessage(content="NVDA outlook?")]},
            config,
        )
        assert "__interrupt__" in result

        resumed = graph.invoke(Command(resume=True), config)

        assert resumed["messages"][-1].content == final_msg.content
