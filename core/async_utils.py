"""Async HTTP client utilities with retry, timeout, and structured logging."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, Self, TypeVar

import httpx
import tenacity
from tenacity import (
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from core.exceptions import HTTPClientError
from core.logging import get_logger

T = TypeVar("T")

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

logger = get_logger("http")


def _is_retryable_response(exc: BaseException) -> bool:
    """Check if an httpx.HTTPStatusError has a retryable status code."""
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in RETRYABLE_STATUS_CODES
    )


def _log_retry(retry_state: tenacity.RetryCallState) -> None:
    """Log retry attempts with structured context."""
    attempt = retry_state.attempt_number
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "retrying_request",
        attempt=attempt,
        error=str(exc) if exc else None,
    )


def retry_with_backoff(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
) -> tenacity.AsyncRetrying:
    """Create a pre-configured async retry with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time between retries in seconds.
        max_wait: Maximum wait time between retries in seconds.

    Returns:
        Configured AsyncRetrying instance for use as a context manager.
    """
    return tenacity.AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
        retry=(
            retry_if_exception_type(httpx.TransportError)
            | tenacity.retry_if_exception(_is_retryable_response)
        ),
        before_sleep=_log_retry,
        reraise=True,
    )


class AsyncHTTPClient:
    """Async HTTP client with retry, timeout, and structured logging."""

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 30.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Request URL (relative to base_url if set).
            **kwargs: Additional arguments passed to httpx.AsyncClient.request.

        Returns:
            httpx.Response on success.

        Raises:
            HTTPClientError: On persistent failure after all retries.
        """
        if not self._client:
            msg = "Client not initialized. Use 'async with AsyncHTTPClient() as client:'"
            raise RuntimeError(msg)

        retry = retry_with_backoff(max_attempts=self._max_retries)
        try:
            async for attempt in retry:
                with attempt:
                    response = await self._client.request(method, url, **kwargs)
                    response.raise_for_status()
                    logger.info(
                        "http_request",
                        method=method,
                        url=url,
                        status_code=response.status_code,
                    )
                    return response
        except httpx.HTTPStatusError as exc:
            raise HTTPClientError(
                f"{method} {url} failed with status {exc.response.status_code}",
                details={
                    "method": method,
                    "url": url,
                    "status_code": exc.response.status_code,
                    "response_text": exc.response.text[:500],
                },
            ) from exc
        except httpx.TransportError as exc:
            raise HTTPClientError(
                f"{method} {url} failed: {exc}",
                details={"method": method, "url": url},
            ) from exc

        # Unreachable, but satisfies mypy
        msg = "Retry loop exited without returning or raising"
        raise RuntimeError(msg)  # pragma: no cover

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Send a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Send a POST request."""
        return await self.request("POST", url, **kwargs)


async def gather_with_concurrency(
    limit: int,
    *coros: Coroutine[Any, Any, T],
) -> list[T]:
    """Run coroutines with a concurrency limit, returning results in order.

    Args:
        limit: Maximum number of coroutines running concurrently.
        *coros: Coroutines to execute.

    Returns:
        List of results in the same order as the input coroutines.
    """
    if limit <= 0:
        raise ValueError(f"limit must be a positive integer, got {limit}")
    semaphore = asyncio.Semaphore(limit)

    async def _limited(coro: Coroutine[Any, Any, T]) -> T:
        async with semaphore:
            return await coro

    return list(await asyncio.gather(*(_limited(c) for c in coros)))
