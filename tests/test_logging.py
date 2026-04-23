"""Tests for logging module."""

import json

import pytest
import structlog

from core.logging import configure_logging, get_logger


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_with_logging_methods(self) -> None:
        """get_logger should return an object with standard logging methods."""
        logger = get_logger("test")

        # Verify it has the expected logging methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")
        assert callable(logger.info)

    def test_binds_initial_context(self) -> None:
        """get_logger should attach context that appears in every log."""
        logger = get_logger("test", request_id="abc-123", user_id=456)

        # _context is where structlog stores bound values
        assert logger._context.get("request_id") == "abc-123"
        assert logger._context.get("user_id") == 456


class TestConfigureLogging:
    """Tests for configure_logging function."""

    @pytest.fixture(autouse=True)
    def _reset_structlog(self) -> None:  # noqa: PT004
        """Reset structlog after each test to prevent stale file handles."""
        yield  # type: ignore[misc]
        structlog.reset_defaults()

    def test_json_format_produces_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """JSON format should output parseable JSON."""
        configure_logging(level="INFO", log_format="json")
        logger = get_logger("test")

        logger.info("test message", key="value")

        captured = capsys.readouterr()
        log_entry = json.loads(captured.out.strip())  # Would fail if not valid JSON

        assert log_entry["event"] == "test message"
        assert log_entry["key"] == "value"
        assert "timestamp" in log_entry
        assert "level" in log_entry

    def test_filters_below_configured_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Logger should ignore messages below the configured level."""
        configure_logging(level="WARNING", log_format="json")
        logger = get_logger("test")

        logger.info("should be ignored")
        logger.warning("should appear")

        captured = capsys.readouterr()
        assert "should be ignored" not in captured.out
        assert "should appear" in captured.out
