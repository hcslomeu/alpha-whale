"""Async Redis client with retry, graceful degradation, and structured logging."""

from __future__ import annotations

from typing import Any, Self
from urllib.parse import urlparse

import redis.asyncio as aioredis
import redis.exceptions as redis_exc
import tenacity
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from core.logging import get_logger

logger = get_logger("redis")


def _safe_url(url: str) -> str:
    """Redact credentials from a Redis URL for safe logging."""
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(f":{parsed.password}@", ":***@")
    return url


def _log_retry(retry_state: tenacity.RetryCallState) -> None:
    """Log retry attempts with structured context."""
    attempt = retry_state.attempt_number
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning("redis_retry", attempt=attempt, error=str(exc) if exc else None)


class AsyncRedisClient:
    """Async Redis client with graceful degradation.

    All public methods swallow errors and return None/False so the application
    continues to work when Redis is unavailable — cache misses simply fall
    through to the primary data source.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        key_prefix: str = "ai-mono:",
        default_ttl: int = 300,
        connect_timeout: float = 5.0,
        max_retries: int = 3,
        client: aioredis.Redis | None = None,
    ) -> None:
        self._url = url
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl
        self._connect_timeout = connect_timeout
        self._max_retries = max_retries
        self._client = client

    async def __aenter__(self) -> Self:
        if self._client is None:
            self._client = aioredis.from_url(
                self._url,
                socket_connect_timeout=self._connect_timeout,
                decode_responses=True,
            )
        await self._client.ping()  # type: ignore[misc]
        logger.info("redis_connected", url=_safe_url(self._url))
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
            logger.info("redis_disconnected")

    def _prefixed(self, key: str) -> str:
        """Apply the configured key prefix."""
        return f"{self._key_prefix}{key}"

    def _retry(self) -> tenacity.AsyncRetrying:
        """Create a retry policy for transient Redis errors."""
        return tenacity.AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(initial=0.1, max=2.0),
            retry=retry_if_exception_type((redis_exc.ConnectionError, redis_exc.TimeoutError)),
            before_sleep=_log_retry,
            reraise=True,
        )

    async def get(self, key: str) -> str | None:
        """Retrieve a cached value. Returns None on miss or error."""
        try:
            async for attempt in self._retry():
                with attempt:
                    result: str | None = await self._client.get(self._prefixed(key))  # type: ignore[union-attr]
                    return result
        except Exception:
            logger.warning("redis_get_failed", key=key)
        return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Store a value with TTL. Returns False on error."""
        try:
            async for attempt in self._retry():
                with attempt:
                    await self._client.set(  # type: ignore[union-attr]
                        self._prefixed(key),
                        value,
                        ex=ttl or self._default_ttl,
                    )
                    return True
        except Exception:
            logger.warning("redis_set_failed", key=key)
        return False

    async def delete(self, key: str) -> bool:
        """Remove a key. Returns False on error."""
        try:
            async for attempt in self._retry():
                with attempt:
                    await self._client.delete(self._prefixed(key))  # type: ignore[union-attr]
                    return True
        except Exception:
            logger.warning("redis_delete_failed", key=key)
        return False

    async def health_check(self) -> bool:
        """Check Redis connectivity via PING."""
        try:
            if self._client is None:
                return False
            await self._client.ping()  # type: ignore[misc]
            return True
        except Exception:
            return False
