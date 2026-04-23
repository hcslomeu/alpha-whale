"""Tests for async HTTP client utilities."""

import asyncio

import httpx
import pytest

from core.async_utils import (
    AsyncHTTPClient,
    gather_with_concurrency,
    retry_with_backoff,
)
from core.exceptions import HTTPClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_transport(handler):
    """Create a mock transport from a handler function."""
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# TestRetryWithBackoff
# ---------------------------------------------------------------------------


class TestRetryWithBackoff:
    """Tests for the retry_with_backoff factory."""

    async def test_retries_on_transient_status(self):
        """Retries when a retryable HTTP status code (503) is encountered."""
        call_count = 0

        async def flaky_request():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                response = httpx.Response(503, request=httpx.Request("GET", "http://test"))
                raise httpx.HTTPStatusError("503", request=response.request, response=response)
            return "ok"

        retry = retry_with_backoff(max_attempts=3, min_wait=0.01, max_wait=0.02)
        async for attempt in retry:
            with attempt:
                result = await flaky_request()

        assert result == "ok"
        assert call_count == 3

    async def test_stops_after_max_attempts(self):
        """Raises after exhausting all retry attempts."""

        async def always_fails():
            response = httpx.Response(503, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("503", request=response.request, response=response)

        retry = retry_with_backoff(max_attempts=2, min_wait=0.01, max_wait=0.02)
        with pytest.raises(httpx.HTTPStatusError):
            async for attempt in retry:
                with attempt:
                    await always_fails()

    async def test_no_retry_on_client_error(self):
        """Does not retry on non-retryable status codes (400, 404)."""
        call_count = 0

        async def client_error():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError("404", request=response.request, response=response)

        retry = retry_with_backoff(max_attempts=3, min_wait=0.01, max_wait=0.02)
        with pytest.raises(httpx.HTTPStatusError):
            async for attempt in retry:
                with attempt:
                    await client_error()

        assert call_count == 1

    async def test_retries_on_transport_error(self):
        """Retries on connection-level transport errors."""
        call_count = 0

        async def transport_flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection refused")
            return "recovered"

        retry = retry_with_backoff(max_attempts=3, min_wait=0.01, max_wait=0.02)
        async for attempt in retry:
            with attempt:
                result = await transport_flaky()

        assert result == "recovered"
        assert call_count == 2


# ---------------------------------------------------------------------------
# TestAsyncHTTPClient
# ---------------------------------------------------------------------------


class TestAsyncHTTPClient:
    """Tests for the AsyncHTTPClient context manager."""

    async def test_successful_get(self):
        """GET request returns parsed response."""
        transport = _mock_transport(lambda req: httpx.Response(200, json={"data": "hello"}))

        async with AsyncHTTPClient(transport=transport) as client:
            response = await client.get("http://test/api")

        assert response.status_code == 200
        assert response.json() == {"data": "hello"}

    async def test_successful_post(self):
        """POST request sends body and returns response."""
        transport = _mock_transport(lambda req: httpx.Response(201, json={"id": 1}))

        async with AsyncHTTPClient(transport=transport) as client:
            response = await client.post("http://test/api", json={"name": "test"})

        assert response.status_code == 201
        assert response.json() == {"id": 1}

    async def test_transport_error_raises_http_client_error(self):
        """Transport error (e.g., connection timeout) triggers HTTPClientError."""

        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Read timed out")

        transport = httpx.MockTransport(timeout_handler)

        async with AsyncHTTPClient(max_retries=1, transport=transport) as client:
            with pytest.raises(HTTPClientError, match="failed"):
                await client.get("http://test/slow")

    async def test_retry_then_success(self):
        """Client retries on 503 then succeeds on next attempt."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return httpx.Response(503)
            return httpx.Response(200, json={"ok": True})

        transport = _mock_transport(handler)

        async with AsyncHTTPClient(max_retries=3, transport=transport) as client:
            response = await client.get("http://test/api")

        assert response.status_code == 200
        assert call_count == 2

    async def test_persistent_failure_raises_http_client_error(self):
        """Raises HTTPClientError with details after all retries exhausted."""
        transport = _mock_transport(lambda req: httpx.Response(500))

        async with AsyncHTTPClient(max_retries=2, transport=transport) as client:
            with pytest.raises(HTTPClientError) as exc_info:
                await client.get("http://test/fail")

        assert exc_info.value.details["status_code"] == 500
        assert exc_info.value.details["method"] == "GET"
        assert "url" in exc_info.value.details
        assert "response_text" in exc_info.value.details

    async def test_context_manager_closes_client(self):
        """Client is properly closed after exiting context manager."""
        transport = _mock_transport(lambda req: httpx.Response(200))

        http_client = AsyncHTTPClient(transport=transport)
        async with http_client as client:
            assert client._client is not None
            await client.get("http://test/api")

        assert http_client._client is None


# ---------------------------------------------------------------------------
# TestGatherWithConcurrency
# ---------------------------------------------------------------------------


class TestGatherWithConcurrency:
    """Tests for gather_with_concurrency."""

    async def test_respects_concurrency_limit(self):
        """No more than `limit` coroutines run simultaneously."""
        peak = 0
        current = 0
        lock = asyncio.Lock()

        async def tracked_task(duration: float) -> str:
            nonlocal peak, current
            async with lock:
                current += 1
                peak = max(peak, current)
            await asyncio.sleep(duration)
            async with lock:
                current -= 1
            return "done"

        results = await gather_with_concurrency(
            2,
            tracked_task(0.05),
            tracked_task(0.05),
            tracked_task(0.05),
            tracked_task(0.05),
        )

        assert len(results) == 4
        assert all(r == "done" for r in results)
        assert peak <= 2

    async def test_returns_results_in_order(self):
        """Results are returned in the same order as input coroutines."""

        async def numbered(n: int) -> int:
            await asyncio.sleep(0.05 - n * 0.01)
            return n

        results = await gather_with_concurrency(
            2,
            numbered(0),
            numbered(1),
            numbered(2),
        )

        assert results == [0, 1, 2]

    async def test_propagates_exceptions(self):
        """Exceptions from coroutines are propagated, not swallowed."""

        async def failing() -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await gather_with_concurrency(2, failing())

    async def test_handles_empty_input(self):
        """Returns empty list when no coroutines are provided."""
        results = await gather_with_concurrency(5)
        assert results == []

    async def test_rejects_zero_limit(self):
        """Raises ValueError when limit is zero or negative."""
        with pytest.raises(ValueError, match="positive integer"):
            await gather_with_concurrency(0)


# ---------------------------------------------------------------------------
# TestHTTPClientError
# ---------------------------------------------------------------------------


class TestHTTPClientError:
    """Tests for the HTTPClientError exception."""

    def test_stores_details(self):
        """Exception stores URL, method, and status_code in details dict."""
        error = HTTPClientError(
            "Request failed",
            details={"url": "/api", "method": "POST", "status_code": 502},
        )

        assert error.message == "Request failed"
        assert error.details["url"] == "/api"
        assert error.details["method"] == "POST"
        assert error.details["status_code"] == 502
        assert isinstance(error, HTTPClientError)
