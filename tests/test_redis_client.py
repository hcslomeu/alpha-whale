"""Tests for async Redis client with graceful degradation."""

from unittest.mock import AsyncMock

import fakeredis.aioredis
import redis.exceptions as redis_exc
import structlog

from core.redis_client import AsyncRedisClient


def _fake_redis() -> fakeredis.aioredis.FakeRedis:
    """Create a FakeRedis instance for testing."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


# ---------------------------------------------------------------------------
# TestAsyncRedisClient
# ---------------------------------------------------------------------------


class TestAsyncRedisClient:
    """Tests for core get/set/delete operations."""

    async def test_set_and_get_roundtrip(self):
        """Value stored via set() is retrievable via get()."""
        client = AsyncRedisClient(client=_fake_redis(), key_prefix="test:")
        async with client:
            await client.set("ticker", "AAPL")
            result = await client.get("ticker")
        assert result == "AAPL"

    async def test_get_returns_none_on_miss(self):
        """get() returns None for keys that don't exist."""
        client = AsyncRedisClient(client=_fake_redis(), key_prefix="test:")
        async with client:
            result = await client.get("nonexistent")
        assert result is None

    async def test_delete_removes_key(self):
        """delete() removes a previously set key."""
        client = AsyncRedisClient(client=_fake_redis(), key_prefix="test:")
        async with client:
            await client.set("ticker", "MSFT")
            deleted = await client.delete("ticker")
            result = await client.get("ticker")
        assert deleted is True
        assert result is None

    async def test_key_prefix_applied(self):
        """Keys are stored with the configured prefix."""
        fake = _fake_redis()
        client = AsyncRedisClient(client=fake, key_prefix="aw:")
        async with client:
            await client.set("ticker", "BTC")
            # Access the raw key directly to verify prefix
            raw = await fake.get("aw:ticker")
        assert raw == "BTC"

    async def test_ttl_is_set(self):
        """Keys have a TTL applied."""
        fake = _fake_redis()
        client = AsyncRedisClient(client=fake, key_prefix="test:", default_ttl=60)
        async with client:
            await client.set("ticker", "ETH")
            ttl = await fake.ttl("test:ticker")
        assert ttl > 0
        assert ttl <= 60

    async def test_health_check_healthy(self):
        """health_check() returns True when connected."""
        client = AsyncRedisClient(client=_fake_redis(), key_prefix="test:")
        async with client:
            assert await client.health_check() is True

    async def test_health_check_unhealthy(self):
        """health_check() returns False when client is None."""
        client = AsyncRedisClient(key_prefix="test:")
        # Don't enter context manager — _client stays None
        assert await client.health_check() is False


# ---------------------------------------------------------------------------
# TestGracefulDegradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """Tests that operations degrade gracefully on errors."""

    def _broken_client(self) -> AsyncRedisClient:
        """Create a client with methods that raise ConnectionError."""
        fake = _fake_redis()
        client = AsyncRedisClient(client=fake, key_prefix="test:", max_retries=1)
        fake.get = AsyncMock(side_effect=redis_exc.ConnectionError("gone"))
        fake.set = AsyncMock(side_effect=redis_exc.ConnectionError("gone"))
        fake.delete = AsyncMock(side_effect=redis_exc.ConnectionError("gone"))
        return client

    async def test_get_returns_none_on_error(self):
        """get() returns None when Redis raises an error."""
        client = self._broken_client()
        with structlog.testing.capture_logs():
            result = await client.get("any-key")
        assert result is None

    async def test_set_returns_false_on_error(self):
        """set() returns False when Redis raises an error."""
        client = self._broken_client()
        with structlog.testing.capture_logs():
            result = await client.set("any-key", "any-value")
        assert result is False

    async def test_delete_returns_false_on_error(self):
        """delete() returns False when Redis raises an error."""
        client = self._broken_client()
        with structlog.testing.capture_logs():
            result = await client.delete("any-key")
        assert result is False


# ---------------------------------------------------------------------------
# TestLifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """Tests for context manager lifecycle."""

    async def test_context_manager_opens_and_closes(self):
        """Client is set on enter and cleared on exit."""
        fake = _fake_redis()
        client = AsyncRedisClient(client=fake, key_prefix="test:")
        async with client:
            assert client._client is not None
        assert client._client is None
