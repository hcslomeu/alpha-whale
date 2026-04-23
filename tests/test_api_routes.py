"""Tests for AlphaWhale API routes.

Tests use httpx AsyncClient with FastAPI dependency overrides.
"""

import json
from collections.abc import AsyncGenerator, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.types import Command
from testing_utils import FakeLogfire

from api.dependencies import get_graph
from api.main import create_app


@pytest.fixture
def mock_graph():
    """Create a mock compiled graph."""
    graph = AsyncMock()
    graph.astream_events = _make_async_iter([])
    graph.aget_state = AsyncMock(return_value=MagicMock(tasks=[]))
    return graph


@pytest.fixture
def app(mock_graph, monkeypatch):
    """Create a test app with mocked dependencies."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-supabase-key")
    monkeypatch.setenv("LOGFIRE_ENABLED", "false")
    test_app = create_app()
    test_app.state.supabase = AsyncMock()
    test_app.state.redis_client = None
    test_app.dependency_overrides[get_graph] = lambda: mock_graph
    return test_app


@pytest.fixture
async def client(app):
    """Async test client that bypasses lifespan."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_async_iter(items: list) -> Callable[..., AsyncGenerator]:
    """Return a callable that produces a fresh async iterator each time."""

    async def _iter(*_args, **_kwargs):
        for item in items:
            yield item

    return _iter


def _parse_sse_data_lines(text: str, *, exclude_done: bool = True) -> list[str]:
    """Extract data: lines from SSE response text."""
    lines = []
    for line in text.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith("data:"):
            if exclude_done and "[DONE]" in stripped:
                continue
            lines.append(stripped.removeprefix("data:").strip())
    return lines


class TestChatStream:
    async def test_stream_includes_thread_id_in_metadata(
        self, client: AsyncClient, mock_graph: AsyncMock
    ):
        """First SSE event should contain the thread_id."""
        response = await client.post(
            "/chat/stream",
            json={"message": "Hello", "thread_id": "test-thread-123"},
        )
        assert response.status_code == 200

        data_lines = _parse_sse_data_lines(response.text)
        metadata = json.loads(data_lines[0])
        assert metadata["thread_id"] == "test-thread-123"

    async def test_stream_generates_thread_id_when_missing(
        self, client: AsyncClient, mock_graph: AsyncMock
    ):
        """Should auto-generate a UUID thread_id when not provided."""
        response = await client.post(
            "/chat/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 200

        data_lines = _parse_sse_data_lines(response.text)
        metadata = json.loads(data_lines[0])
        assert "thread_id" in metadata
        assert len(metadata["thread_id"]) == 36  # UUID format


class TestAppFactoryObservability:
    def test_create_app_calls_fastapi_instrumentation(self, monkeypatch: pytest.MonkeyPatch):
        """App factory should delegate FastAPI instrumentation to py-core."""
        instrument_mock = MagicMock(return_value=True)
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "test-supabase-key")
        monkeypatch.setattr("api.main.instrument_fastapi_app", instrument_mock)

        app = create_app()

        instrument_mock.assert_called_once_with(app, service_name="alpha-whale-api")

    def test_create_app_remains_usable_when_instrumentation_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """App factory should still return a working app when Logfire is disabled."""
        instrument_mock = MagicMock(return_value=False)
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "test-supabase-key")
        monkeypatch.setattr("api.main.instrument_fastapi_app", instrument_mock)

        app = create_app()

        assert app.title == "AlphaWhale API"
        instrument_mock.assert_called_once_with(app, service_name="alpha-whale-api")


class TestStreamObservability:
    async def test_chat_stream_records_error_telemetry(
        self,
        client: AsyncClient,
        mock_graph: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Streaming errors should emit SSE error events and observability metrics."""

        async def _failing_stream(*_args, **_kwargs):
            raise RuntimeError("stream exploded")
            yield

        fake_logfire = FakeLogfire()
        mock_graph.astream_events = _failing_stream
        monkeypatch.setattr("api.routes.get_logfire_instance", lambda: fake_logfire)
        monkeypatch.setattr("api.routes._stream_duration_histogram", None)
        monkeypatch.setattr("api.routes._stream_error_counter", None)

        response = await client.post(
            "/chat/stream",
            json={"message": "Hello", "thread_id": "stream-obs-1"},
        )

        assert response.status_code == 200
        assert '"error": "stream failed"' in response.text
        assert "[DONE]" in response.text
        counter_calls = fake_logfire.counters["alpha_whale.agent.stream.errors"].calls
        histogram_calls = fake_logfire.histograms["alpha_whale.agent.stream.duration"].calls
        assert counter_calls == [(1, {"route": "/chat/stream", "error_type": "RuntimeError"})]
        assert histogram_calls[0][1] == {
            "route": "/chat/stream",
            "approval_requested": False,
        }
        assert fake_logfire.spans[0].name == "agent.stream_request"
        assert fake_logfire.spans[0].initial_attributes["thread_id"] == "stream-obs-1"
        assert fake_logfire.spans[0].attributes["error.type"] == "RuntimeError"

    async def test_chat_approve_records_error_telemetry(
        self,
        client: AsyncClient,
        mock_graph: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Resume-stream errors should emit SSE error events and observability metrics."""

        async def _failing_stream(*_args, **_kwargs):
            raise RuntimeError("resume exploded")
            yield

        fake_logfire = FakeLogfire()
        mock_graph.astream_events = _failing_stream
        monkeypatch.setattr("api.routes.get_logfire_instance", lambda: fake_logfire)
        monkeypatch.setattr("api.routes._stream_duration_histogram", None)
        monkeypatch.setattr("api.routes._stream_error_counter", None)

        response = await client.post(
            "/chat/approve",
            json={"thread_id": "approve-obs-1", "approved": True},
        )

        assert response.status_code == 200
        assert '"error": "resume failed"' in response.text
        assert "[DONE]" in response.text
        counter_calls = fake_logfire.counters["alpha_whale.agent.stream.errors"].calls
        histogram_calls = fake_logfire.histograms["alpha_whale.agent.stream.duration"].calls
        assert counter_calls == [(1, {"route": "/chat/approve", "error_type": "RuntimeError"})]
        assert histogram_calls[0][1] == {
            "route": "/chat/approve",
            "approval_requested": False,
        }
        assert fake_logfire.spans[0].name == "agent.resume_request"
        assert fake_logfire.spans[0].initial_attributes["thread_id"] == "approve-obs-1"
        assert fake_logfire.spans[0].attributes["error.type"] == "RuntimeError"


class TestChatApprove:
    # TODO: add test asserting 403 when a user attempts to approve a thread they
    # do not own (e.g. thread_id belonging to a different user_id). Requires
    # ownership enforcement on the /chat/approve endpoint (not yet implemented).

    async def test_approve_resumes_graph(self, client: AsyncClient, mock_graph: AsyncMock):
        """POST /chat/approve should resume the graph with Command(resume=True) and stream tokens."""
        token_event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="Signal approved!")},
        }
        astream_mock = MagicMock(side_effect=_make_async_iter([token_event]))
        mock_graph.astream_events = astream_mock

        response = await client.post(
            "/chat/approve",
            json={"thread_id": "test-thread-123", "approved": True},
        )
        assert response.status_code == 200

        data_lines = _parse_sse_data_lines(response.text)
        assert len(data_lines) >= 1
        token_data = json.loads(data_lines[0])
        assert token_data["token"] == "Signal approved!"

        astream_mock.assert_called_once()
        assert astream_mock.call_args[0][0] == Command(resume=True)

    async def test_reject_resumes_graph(self, client: AsyncClient, mock_graph: AsyncMock):
        """POST /chat/approve with approved=false should resume with Command(resume=False)."""
        token_event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": MagicMock(content="Signal rejected.")},
        }
        astream_mock = MagicMock(side_effect=_make_async_iter([token_event]))
        mock_graph.astream_events = astream_mock

        response = await client.post(
            "/chat/approve",
            json={"thread_id": "test-thread-123", "approved": False},
        )
        assert response.status_code == 200

        data_lines = _parse_sse_data_lines(response.text)
        token_data = json.loads(data_lines[0])
        assert token_data["token"] == "Signal rejected."

        astream_mock.assert_called_once()
        assert astream_mock.call_args[0][0] == Command(resume=False)


class TestApprovalRequestValidation:
    async def test_rejects_missing_thread_id(self, client: AsyncClient):
        """Should return 422 when thread_id is missing."""
        response = await client.post(
            "/chat/approve",
            json={"approved": True},
        )
        assert response.status_code == 422

    async def test_rejects_missing_approved(self, client: AsyncClient):
        """Should return 422 when approved field is missing."""
        response = await client.post(
            "/chat/approve",
            json={"thread_id": "some-thread"},
        )
        assert response.status_code == 422
