"""AlphaWhale agent graph — LangGraph StateGraph implementation.

Graph architecture:
START → agent_node → [has tool calls?]
                      ├─ No → END
                      └─ Yes → tools_node → [trade signal generated?]
                                             ├─ No → agent_node (loop)
                                             └─ Yes → risk_assessment_node → [high risk?]
                                                                              ├─ No → agent_node
                                                                              └─ Yes → human_approval_node (INTERRUPT)
                                                                                        → agent_node → END
"""

from contextlib import nullcontext
from time import perf_counter
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent.models import RiskLevel, TradeSignal, UserIntent
from agent.state import AgentState
from agent.tools import (
    compare_assets,
    generate_trade_signal,
    get_stock_price,
    get_technical_indicators,
    query_knowledge_base,
)
from core import ExtractionError, extract, get_logfire_instance, get_logger

logger = get_logger("agent.graph")

TOOLS = [
    get_stock_price,
    get_technical_indicators,
    compare_assets,
    generate_trade_signal,
    query_knowledge_base,
]
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}

SYSTEM_PROMPT = (
    "You are AlphaWhale, an AI financial analyst embedded in a live trading terminal. "
    "A TradingView chart is displayed alongside this chat and responds to your confirmations.\n\n"
    "TICKER MAPPING — always resolve company names to their canonical symbol:\n"
    "Apple → AAPL | Microsoft → MSFT | Google / Alphabet → GOOGL | Amazon → AMZN\n"
    "Nvidia → NVDA | Meta / Facebook → META | Tesla → TSLA\n"
    "Bitcoin → BTC | Ethereum → ETH | Solana → SOL\n\n"
    "CHART COMMANDS — the chart updates automatically; your job is only to confirm briefly.\n"
    "DO NOT call any tools for these requests:\n"
    "• 'show / display / chart / pull up [asset]' → reply e.g. 'Here is the Bitcoin (BTC) chart.'\n"
    "• 'add / show / enable [indicator]' → reply e.g. 'RSI added to the chart.'\n"
    "• 'remove / hide / disable [indicator]' → reply e.g. 'Stochastic removed.'\n"
    "Oscillators in the lower pane are mutually exclusive: RSI, MACD, and Stochastic replace one another.\n"
    "Overlays on the price chart can stack: EMA and SMA may be active together (e.g. EMA 8 + SMA 200).\n"
    "If an oscillator is replaced, acknowledge the swap briefly (e.g. 'Stochastic replaced with RSI.').\n\n"
    "DATA QUERIES — use tools only when the user explicitly asks for analysis, prices, or performance.\n"
    "• get_stock_price: recent OHLCV data\n"
    "• get_technical_indicators: EMA 8/80, SMA 200, MACD, RSI 14, Stochastic K/D\n"
    "• compare_assets: side-by-side metric comparison\n"
    "• query_knowledge_base: search SEC filings (10-K/10-Q) and financial news for fundamentals, "
    "earnings, company strategy, or recent news context. Use ticker_filter to scope results.\n\n"
    "RESPONSE FORMAT — when presenting tool data, return a short summary sentence followed by\n"
    "a fenced JSON block using the language tag `financial-data`. The frontend renders this as\n"
    "rich UI components. Never include volume in stock performance summaries.\n\n"
    "For get_stock_price, return:\n"
    "```financial-data\n"
    '{"type":"stock","ticker":"SYMBOL","data":[{"date":"YYYY-MM-DD","open":0.00,"close":0.00,'
    '"high":0.00,"low":0.00}],"summary":"Brief analytical insight"}\n'
    "```\n\n"
    "For get_technical_indicators, return:\n"
    "```financial-data\n"
    '{"type":"indicators","ticker":"SYMBOL","data":[{"date":"YYYY-MM-DD","ema_8":0.00,'
    '"ema_80":0.00,"sma_200":0.00,"rsi_14":0.00,"macd_value":0.00,"macd_signal":0.00,'
    '"stoch_k":0.00,"stoch_d":0.00}],"summary":"Brief analytical insight"}\n'
    "```\n\n"
    "For compare_assets, return:\n"
    "```financial-data\n"
    '{"type":"comparison","metric":"close","tickers":["A","B"],"data":{"A":[{"date":"YYYY-MM-DD",'
    '"value":0.00}],"B":[{"date":"YYYY-MM-DD","value":0.00}]},"summary":"Brief comparison insight"}\n'
    "```\n\n"
    "Always include a brief natural-language sentence before the JSON block for context.\n\n"
    "DISCLAIMER — always include at the end of any response that contains trade signals or "
    "market analysis:\n"
    "'⚠️ This is not financial advice. AlphaWhale is an educational tool demonstrating "
    "AI engineering concepts. Always consult a qualified financial advisor before making "
    "investment decisions.'"
)


_model: Runnable | None = None
_tool_latency_histogram: Any | None = None
_tool_error_counter: Any | None = None


def _get_tool_latency_histogram() -> Any | None:
    """Return a cached histogram for tool execution time."""
    global _tool_latency_histogram
    if _tool_latency_histogram is None:
        logfire = get_logfire_instance()
        if logfire is None:
            return None
        _tool_latency_histogram = logfire.metric_histogram(
            "alpha_whale.agent.tool.duration",
            unit="ms",
            description="Duration of LangGraph tool executions in milliseconds.",
        )
    return _tool_latency_histogram


def _get_tool_error_counter() -> Any | None:
    """Return a cached counter for tool failures."""
    global _tool_error_counter
    if _tool_error_counter is None:
        logfire = get_logfire_instance()
        if logfire is None:
            return None
        _tool_error_counter = logfire.metric_counter(
            "alpha_whale.agent.tool.errors",
            unit="1",
            description="Number of LangGraph tool execution failures.",
        )
    return _tool_error_counter


def _record_tool_metrics(*, tool_name: str, duration_ms: float, success: bool) -> None:
    """Record latency metrics for a tool invocation."""
    histogram = _get_tool_latency_histogram()
    if histogram is None:
        return
    histogram.record(duration_ms, attributes={"tool_name": tool_name, "success": success})


def _record_tool_error(*, tool_name: str, error_type: str) -> None:
    """Increment the tool failure counter."""
    counter = _get_tool_error_counter()
    if counter is None:
        return
    counter.add(1, attributes={"tool_name": tool_name, "error_type": error_type})


def get_model() -> Runnable:
    """Return a cached ChatOpenAI model with tools bound.

    Lazily creates the model on first call to avoid requiring an API key at
    import time. Subsequent calls return the cached instance.

    When LLM caching is enabled, configures LangChain's global RedisCache
    so identical prompts return cached responses (effective with temperature=0.0).
    """
    global _model  # noqa: PLW0603
    if _model is None:
        from agent.config import AgentSettings

        settings = AgentSettings()
        if settings.llm_cache_enabled:
            try:
                import redis as sync_redis_lib
                from langchain_community.cache import RedisCache
                from langchain_core.globals import set_llm_cache

                sync_client = sync_redis_lib.Redis.from_url(settings.llm_cache_redis_url)
                sync_client.ping()
                set_llm_cache(RedisCache(redis_=sync_client))
            except Exception:
                from core import get_logger

                get_logger("agent").warning("llm_cache_init_failed", reason="Redis unavailable")

        llm = ChatOpenAI(model="gpt-5-mini", temperature=0.0)
        _model = llm.bind_tools(TOOLS)
    return _model


def extract_user_intent(text: str) -> UserIntent | None:
    """Extract structured intent from user input.

    Returns None on failure — the agent continues with normal LLM routing.
    """
    try:
        intent = extract(text, UserIntent)
        logger.info(
            "user_intent_extracted",
            query_type=intent.query_type,
            assets=[a.ticker for a in intent.assets],
            indicators=[i.indicator for i in intent.indicators],
        )
        return intent
    except ExtractionError:
        logger.debug("user_intent_extraction_skipped", reason="extraction_failed", exc_info=True)
        return None


def agent_node(state: AgentState) -> dict:
    """Call the LLM with the current messages and return its response."""
    last_msg = state["messages"][-1]
    if isinstance(last_msg, HumanMessage) and isinstance(last_msg.content, str):
        extract_user_intent(last_msg.content)

    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = get_model().invoke(messages)
    return {"messages": [response]}


def tools_node(state: AgentState) -> dict:
    """Execute tool calls from the last AI message and return results.

    When a generate_trade_signal tool is called, the result is parsed
    into a TradeSignal and accumulated in state.
    """
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        return {"messages": []}

    results = []
    new_signals: list[TradeSignal] = []
    logfire = get_logfire_instance()

    for call in last_message.tool_calls:
        start_time = perf_counter()
        success = False
        error_type: str | None = None
        tool = TOOLS_BY_NAME.get(call["name"])
        span_context = (
            logfire.span("agent.tool_call", tool_name=call["name"])
            if logfire is not None
            else nullcontext()
        )

        with span_context as span:
            if tool is None:
                error_type = "unknown_tool"
                output = f"Error: unknown tool '{call['name']}'"
            else:
                try:
                    output = tool.invoke(call["args"])
                    success = True
                except Exception as exc:
                    error_type = type(exc).__name__
                    logger.warning(
                        "tool_invocation_failed",
                        tool=call["name"],
                        error_type=error_type,
                    )
                    output = f"Error: tool '{call['name']}' failed"

            duration_ms = (perf_counter() - start_time) * 1000
            if span is not None:
                span.set_attribute("tool.success", success)
                span.set_attribute("tool.duration_ms", duration_ms)
                if error_type is not None:
                    span.set_attribute("error.type", error_type)
            _record_tool_metrics(
                tool_name=call["name"],
                duration_ms=duration_ms,
                success=success,
            )
            if error_type is not None:
                _record_tool_error(tool_name=call["name"], error_type=error_type)

        # Capture trade signals for risk assessment routing
        if call["name"] == "generate_trade_signal" and isinstance(output, dict):
            try:
                new_signals.append(TradeSignal(**output))
            except Exception:
                logger.debug("trade_signal_parse_skipped", tool_output=str(output)[:200])

        results.append(ToolMessage(content=str(output), tool_call_id=call["id"]))

    update: dict = {"messages": results}
    if new_signals:
        update["trade_signals"] = new_signals
    return update


def risk_assessment_node(state: AgentState) -> dict:
    """Evaluate the latest trade signal and classify its risk level.

    Risk rules (deterministic, no LLM call):
    - confidence >= 0.8 AND bullish/bearish → high
    - confidence >= 0.5 → medium
    - otherwise → low
    """
    signals = state.get("trade_signals", [])
    if not signals:
        return {"risk_level": RiskLevel.LOW, "pending_approval": False}

    signal = signals[-1]
    if signal.confidence >= 0.8 and signal.signal in ("bullish", "bearish"):
        level = RiskLevel.HIGH
    elif signal.confidence >= 0.5:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    requires_approval = level == RiskLevel.HIGH
    logger.info(
        "risk_assessed",
        ticker=signal.ticker,
        signal=signal.signal,
        confidence=signal.confidence,
        risk_level=level.value,
        requires_approval=requires_approval,
    )
    return {"risk_level": level, "pending_approval": requires_approval}


def should_continue(state: AgentState) -> str:
    """Route to tools_node if the LLM made tool calls, otherwise end."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools_node"
    return END


def route_after_tools(state: AgentState) -> str:
    """Route after tools_node: to risk assessment if trade signal generated, else back to agent."""
    if state.get("trade_signals", []):
        return "risk_assessment_node"
    return "agent_node"


def route_after_risk(state: AgentState) -> str:
    """Route after risk assessment: to human approval if high risk, else back to agent."""
    if state.get("pending_approval", False):
        return "human_approval_node"
    return "agent_node"


def human_approval_node(state: AgentState) -> dict:
    """Pause for human approval on high-risk trade signals.

    Uses LangGraph's interrupt() to pause execution and surface the
    trade signal to the caller. The graph resumes when the caller
    invokes with Command(resume=<bool>).
    """
    signal = state["trade_signals"][-1]
    decision = interrupt(
        {
            "type": "approval_request",
            "signal": signal.model_dump(),
            "risk_level": state.get("risk_level", RiskLevel.HIGH).value,
            "message": (
                f"High-confidence {signal.signal} signal for {signal.ticker} "
                f"(confidence: {signal.confidence:.0%}). Approve?"
            ),
        }
    )
    approved = decision if isinstance(decision, bool) else bool(decision)
    risk_level = state.get("risk_level")
    logger.info(
        "human_approval_decision",
        ticker=signal.ticker,
        approved=approved,
        risk_level=risk_level.value if risk_level else "unknown",
    )
    if not approved:
        return {
            "pending_approval": False,
            "messages": [
                SystemMessage(content=f"Trade signal for {signal.ticker} was rejected by the user.")
            ],
        }
    return {"pending_approval": False}


def build_graph() -> StateGraph:
    """Construct the AlphaWhale agent graph (uncompiled)."""
    graph = StateGraph(AgentState)

    graph.add_node("agent_node", agent_node)
    graph.add_node("tools_node", tools_node)
    graph.add_node("risk_assessment_node", risk_assessment_node)
    graph.add_node("human_approval_node", human_approval_node)

    graph.add_edge(START, "agent_node")
    graph.add_conditional_edges("agent_node", should_continue, ["tools_node", END])
    graph.add_conditional_edges(
        "tools_node", route_after_tools, ["agent_node", "risk_assessment_node"]
    )
    graph.add_conditional_edges(
        "risk_assessment_node", route_after_risk, ["agent_node", "human_approval_node"]
    )
    graph.add_edge("human_approval_node", "agent_node")

    return graph


# Compiled graph ready for invocation
checkpointer = MemorySaver()
app = build_graph().compile(checkpointer=checkpointer)


def run(user_input: str, *, thread_id: str = "default") -> str:
    """Run the AlphaWhale agent graph on a user question.

    Args:
        user_input: The user's question about crypto markets.
        thread_id: Conversation thread identifier for state persistence.

    Returns:
        The agent's final text response.
    """
    config: RunnableConfig = {
        "run_name": "alpha-whale-agent",
        "tags": ["alpha-whale"],
        "configurable": {"thread_id": thread_id},
    }
    result = app.invoke(
        {"messages": [HumanMessage(content=user_input)]},  # type: ignore[call-overload]
        config=config,
    )
    return str(result["messages"][-1].content)
