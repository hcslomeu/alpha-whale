"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any, cast

import structlog
from structlog.types import Processor


def _get_base_processors() -> list[Processor]:
    """Return base processors shared by all formats."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _get_json_processors() -> list[Processor]:
    """Return processors for JSON output."""
    return _get_base_processors() + [structlog.processors.JSONRenderer()]


def _get_console_processors() -> list[Processor]:
    """Return processors for human-readable console output."""
    return _get_base_processors() + [structlog.dev.ConsoleRenderer(colors=True)]


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ('json' for production, 'console' for development)
    """
    processors = _get_json_processors() if log_format == "json" else _get_console_processors()

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)
        **initial_context: Key-value pairs to include in all log entries

    Returns:
        Configured structlog BoundLogger
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return cast(structlog.BoundLogger, logger)
