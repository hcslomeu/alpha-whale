"""Core utilities for alpha-whale."""

from core.async_utils import AsyncHTTPClient, gather_with_concurrency, retry_with_backoff
from core.config import Settings
from core.exceptions import (
    ConfigurationError,
    ExtractionError,
    HTTPClientError,
    PyCorError,
    RedisClientError,
    ValidationError,
)
from core.extraction import create_instructor_client, extract
from core.logging import configure_logging, get_logger
from core.observability import (
    ObservabilitySettings,
    configure_observability,
    get_logfire_instance,
    instrument_fastapi_app,
)
from core.redis_client import AsyncRedisClient

__all__ = [
    "AsyncHTTPClient",
    "AsyncRedisClient",
    "ConfigurationError",
    "ExtractionError",
    "HTTPClientError",
    "ObservabilitySettings",
    "PyCorError",
    "RedisClientError",
    "Settings",
    "ValidationError",
    "configure_logging",
    "configure_observability",
    "create_instructor_client",
    "extract",
    "gather_with_concurrency",
    "get_logger",
    "get_logfire_instance",
    "instrument_fastapi_app",
    "retry_with_backoff",
]
