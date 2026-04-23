"""API route handlers for AlphaWhale."""

import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Sequence
from contextlib import nullcontext
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Query
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from sse_starlette import EventSourceResponse

from api.dependencies import GraphDep, RedisClientDep, SupabaseDep
from api.models import (
    ApprovalRequest,
    ChatRequest,
    HealthCheck,
    HealthResponse,
    IndicatorDataResponse,
    MarketDataResponse,
)
from core import get_logfire_instance, get_logger

logger = get_logger("api.routes")

router = APIRouter()

_stream_duration_histogram: Any | None = None
_stream_error_counter: Any | None = None
SSEEvent = dict[str, str]
PostStreamCallback = Callable[[Any | None], Awaitable[tuple[list[SSEEvent], bool]]]


def _get_stream_duration_histogram() -> Any | None:
    """Return a cached histogram for agent stream duration."""
    global _stream_duration_histogram
    if _stream_duration_histogram is None:
        logfire = get_logfire_instance()
        if logfire is None:
            return None
        _stream_duration_histogram = logfire.metric_histogram(
            "alpha_whale.agent.stream.duration",
            unit="ms",
            description="Duration of agent SSE streams in milliseconds.",
        )
    return _stream_duration_histogram


def _get_stream_error_counter() -> Any | None:
    """Return a cached counter for agent stream errors."""
    global _stream_error_counter
    if _stream_error_counter is None:
        logfire = get_logfire_instance()
        if logfire is None:
            return None
        _stream_error_counter = logfire.metric_counter(
            "alpha_whale.agent.stream.errors",
            unit="1",
            description="Number of agent SSE stream failures.",
        )
    return _stream_error_counter


def _record_stream_metrics(*, route: str, duration_ms: float, approval_requested: bool) -> None:
    """Record latency metrics for an agent stream."""
    histogram = _get_stream_duration_histogram()
    if histogram is None:
        return
    histogram.record(
        duration_ms,
        attributes={"route": route, "approval_requested": approval_requested},
    )


def _record_stream_error(*, route: str, error_type: str) -> None:
    """Increment the agent stream error counter."""
    counter = _get_stream_error_counter()
    if counter is None:
        return
    counter.add(1, attributes={"route": route, "error_type": error_type})


async def _stream_token_events(
    stream: AsyncIterator[Any],
) -> AsyncGenerator[SSEEvent, None]:
    """Convert LangGraph stream events into SSE token events."""
    async for event in stream:
        if event["event"] == "on_chat_model_stream" and event["data"]["chunk"].content:
            yield {
                "event": "message",
                "data": json.dumps({"token": event["data"]["chunk"].content}),
            }


async def _run_stream(
    *,
    route: str,
    thread_id: str,
    span_name: str,
    span_attributes: dict[str, object],
    error_log_event: str,
    client_error_message: str,
    stream_factory: Callable[[], AsyncIterator[Any]],
    initial_events: Sequence[SSEEvent] = (),
    post_stream: PostStreamCallback | None = None,
) -> AsyncGenerator[SSEEvent, None]:
    """Wrap a streaming endpoint with shared observability and SSE boilerplate."""
    logfire = get_logfire_instance()
    start_time = perf_counter()
    approval_requested = False
    span_context = (
        logfire.span(span_name, **span_attributes) if logfire is not None else nullcontext()
    )

    with span_context as span:
        for event in initial_events:
            yield event

        try:
            async for event in _stream_token_events(stream_factory()):
                yield event

            if post_stream is not None:
                extra_events, approval_requested = await post_stream(span)
                for event in extra_events:
                    yield event
        except Exception as exc:
            error_type = type(exc).__name__
            logger.error(error_log_event, error_type=error_type, thread_id=thread_id)
            _record_stream_error(route=route, error_type=error_type)
            if span is not None:
                span.set_attribute("error.type", error_type)
            yield {
                "event": "error",
                "data": json.dumps({"error": client_error_message}),
            }
        finally:
            duration_ms = (perf_counter() - start_time) * 1000
            if span is not None:
                span.set_attribute("approval_requested", approval_requested)
                span.set_attribute("stream.duration_ms", duration_ms)
            _record_stream_metrics(
                route=route,
                duration_ms=duration_ms,
                approval_requested=approval_requested,
            )
            yield {"event": "message", "data": "[DONE]"}


async def _stream_agent(
    graph: GraphDep,
    message: str,
    thread_id: str,
) -> AsyncGenerator[dict[str, str], None]:
    """Yield SSE-formatted dicts from the LangGraph agent stream."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    async def _post_stream(span: Any | None) -> tuple[list[SSEEvent], bool]:
        state = await graph.aget_state(config)
        interrupted_task = next(
            (
                task
                for task in (state.tasks or [])
                if hasattr(task, "interrupts") and task.interrupts
            ),
            None,
        )
        if interrupted_task is None:
            return [], False
        if span is not None:
            span.set_attribute("approval_requested", True)
        return [
            {
                "event": "approval_request",
                "data": json.dumps(interrupted_task.interrupts[0].value),
            }
        ], True

    initial_events = [
        {
            "event": "metadata",
            "data": json.dumps({"thread_id": thread_id}),
        }
    ]

    async for event in _run_stream(
        route="/chat/stream",
        thread_id=thread_id,
        span_name="agent.stream_request",
        span_attributes={"thread_id": thread_id, "message_length": len(message)},
        error_log_event="stream_error",
        client_error_message="stream failed",
        stream_factory=lambda: graph.astream_events(
            {"messages": [HumanMessage(content=message)]},
            config=config,
            version="v2",
        ),
        initial_events=initial_events,
        post_stream=_post_stream,
    ):
        yield event


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, graph: GraphDep) -> EventSourceResponse:
    """Stream agent responses as Server-Sent Events."""
    thread_id = body.thread_id or str(uuid.uuid4())
    return EventSourceResponse(_stream_agent(graph, body.message, thread_id))


@router.post("/chat/approve")
async def chat_approve(body: ApprovalRequest, graph: GraphDep) -> EventSourceResponse:
    """Resume a paused conversation after human approval/rejection."""
    thread_id = body.thread_id

    async def _stream_resume() -> AsyncGenerator[dict[str, str], None]:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        async for event in _run_stream(
            route="/chat/approve",
            thread_id=thread_id,
            span_name="agent.resume_request",
            span_attributes={"thread_id": thread_id, "approved": body.approved},
            error_log_event="approval_stream_error",
            client_error_message="resume failed",
            stream_factory=lambda: graph.astream_events(
                Command(resume=body.approved),
                config=config,
                version="v2",
            ),
        ):
            yield event

    return EventSourceResponse(_stream_resume())


@router.get("/market/{asset}", response_model=list[MarketDataResponse])
async def get_market_data(
    asset: str,
    supabase: SupabaseDep,
    redis: RedisClientDep,
    days: int = Query(default=30, ge=1, le=3650),
) -> list[MarketDataResponse]:
    """Return recent daily OHLCV data for a ticker from Supabase."""
    ticker = asset.upper()
    cache_key = f"market:{ticker}:{days}"

    if redis is not None:
        cached = await redis.get(cache_key)
        if cached is not None:
            try:
                logger.info("cache_hit", key=cache_key)
                return [MarketDataResponse(**row) for row in json.loads(cached)]
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                logger.warning("cache_deserialize_failed", key=cache_key, error=str(exc))

    result = (
        await supabase.table("market_data_daily")
        .select("ticker, date, open, high, low, close, volume")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(days)
        .execute()
    )

    if not result.data:
        return []

    if redis is not None:
        await redis.set(cache_key, json.dumps(result.data))

    return [MarketDataResponse(**row) for row in result.data]  # type: ignore[arg-type]


@router.get("/market/{asset}/indicators", response_model=list[IndicatorDataResponse])
async def get_indicator_data(
    asset: str,
    supabase: SupabaseDep,
    redis: RedisClientDep,
    days: int = Query(default=30, ge=1, le=3650),
) -> list[IndicatorDataResponse]:
    """Return recent daily technical indicators for a ticker from Supabase."""
    ticker = asset.upper()
    cache_key = f"indicators:{ticker}:{days}"

    if redis is not None:
        cached = await redis.get(cache_key)
        if cached is not None:
            try:
                logger.info("cache_hit", key=cache_key)
                return [IndicatorDataResponse(**row) for row in json.loads(cached)]
            except (json.JSONDecodeError, TypeError, KeyError) as exc:
                logger.warning("cache_deserialize_failed", key=cache_key, error=str(exc))

    result = (
        await supabase.table("technical_indicators_daily")
        .select(
            "ticker, date, ema_8, ema_80, sma_200, "
            "macd_value, macd_signal, macd_histogram, "
            "rsi_14, stoch_k, stoch_d"
        )
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(days)
        .execute()
    )

    if not result.data:
        return []

    if redis is not None:
        await redis.set(cache_key, json.dumps(result.data))

    return [IndicatorDataResponse(**row) for row in result.data]  # type: ignore[arg-type]


@router.get("/health", response_model=HealthResponse)
async def health_check(redis: RedisClientDep) -> HealthResponse:
    """Service health check with dependency status."""
    if redis is not None:
        redis_ok = await redis.health_check()
        redis_check = HealthCheck(
            status="ok" if redis_ok else "degraded",
            detail="connected" if redis_ok else "unreachable",
        )
    else:
        redis_check = HealthCheck(status="ok", detail="disabled")

    return HealthResponse(
        status="ok",
        checks={
            "redis": redis_check,
            "pinecone": HealthCheck(status="ok", detail="stub"),  # TODO: WP-205
        },
    )
