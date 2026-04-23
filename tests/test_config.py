"""Tests for configuration module."""

import pytest
from pydantic import ValidationError

from core.config import Settings
from core.config.settings import get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self) -> None:
        """Settings should have sensible defaults when no env vars set."""
        settings = Settings()

        assert settings.app_name == "ai-engineering-monorepo"
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"

    def test_loads_from_environment_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings should load values from environment variables."""
        monkeypatch.setenv("APP_NAME", "test-app")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        settings = Settings()

        assert settings.app_name == "test-app"
        assert settings.environment == "production"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

    def test_rejects_invalid_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings should reject environment values not in the allowed list."""
        monkeypatch.setenv("ENVIRONMENT", "invalid")

        with pytest.raises(ValidationError):
            Settings()


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_cached_instance(self) -> None:
        """get_settings should return the same instance on repeated calls."""
        get_settings.cache_clear()  # Clear cache from previous tests

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
