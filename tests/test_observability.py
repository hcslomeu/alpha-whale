"""Tests for shared Logfire observability helpers."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI

import core.observability as observability
from core.exceptions import ConfigurationError
from core.observability import (
    ObservabilitySettings,
    configure_observability,
    get_logfire_instance,
    instrument_fastapi_app,
)


class _FakeLogfire:
    """Minimal Logfire test double."""

    def __init__(self) -> None:
        self.configure_calls: list[dict[str, object]] = []
        self.instrument_fastapi_calls: list[tuple[FastAPI, dict[str, object]]] = []
        self.instrument_openai_calls = 0

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)

    def instrument_openai(self) -> None:
        self.instrument_openai_calls += 1

    def instrument_fastapi(self, app: FastAPI, **kwargs: object) -> None:
        self.instrument_fastapi_calls.append((app, kwargs))


@pytest.fixture(autouse=True)
def reset_observability(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset env vars and module state between tests."""
    observability._reset_observability_state()

    for env_var in (
        "LOGFIRE_ENABLED",
        "LOGFIRE_TOKEN",
        "LOGFIRE_SEND_TO_LOGFIRE",
        "LOGFIRE_ENVIRONMENT",
        "LOGFIRE_CAPTURE_HEADERS",
        "LOGFIRE_FASTAPI_EXCLUDED_URLS",
        "ENVIRONMENT",
    ):
        monkeypatch.delenv(env_var, raising=False)

    yield

    observability._reset_observability_state()


class TestObservabilitySettings:
    """Tests for ObservabilitySettings."""

    def test_defaults_to_disabled_and_development_environment(self) -> None:
        settings = ObservabilitySettings()

        assert settings.logfire_enabled is False
        assert settings.logfire_send_to_logfire is True
        assert settings.logfire_capture_headers is False
        assert settings.logfire_fastapi_excluded_urls == r"^https?://[^/]+/health/?$"
        assert settings.resolved_environment == "development"

    def test_falls_back_to_environment_when_logfire_environment_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENVIRONMENT", "staging")

        settings = ObservabilitySettings()

        assert settings.resolved_environment == "staging"


class TestConfigureObservability:
    """Tests for configure_observability."""

    def test_skips_when_logfire_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            observability,
            "_get_logfire",
            lambda: pytest.fail("Logfire should not be imported when disabled"),
        )

        assert configure_observability(service_name="alpha-whale-api") is False
        assert get_logfire_instance() is None

    def test_configures_logfire_and_openai_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_logfire = _FakeLogfire()
        monkeypatch.setenv("LOGFIRE_ENABLED", "true")
        monkeypatch.setenv("LOGFIRE_TOKEN", "test-token")
        monkeypatch.setenv("LOGFIRE_ENVIRONMENT", "production")
        monkeypatch.setattr(observability, "_get_logfire", lambda: fake_logfire)

        assert configure_observability(service_name="alpha-whale-api") is True
        assert configure_observability(service_name="alpha-whale-api") is True

        assert fake_logfire.configure_calls == [
            {
                "send_to_logfire": True,
                "token": "test-token",
                "service_name": "alpha-whale-api",
                "environment": "production",
            }
        ]
        assert fake_logfire.instrument_openai_calls == 1

    def test_raises_when_enabled_without_logfire_package(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGFIRE_ENABLED", "true")
        monkeypatch.setattr(
            observability,
            "_get_logfire",
            lambda: (_ for _ in ()).throw(
                ConfigurationError(
                    "LOGFIRE_ENABLED=true requires the 'logfire' package to be installed."
                )
            ),
        )

        with pytest.raises(ConfigurationError):
            configure_observability(service_name="alpha-whale-api")


class TestInstrumentFastAPIApp:
    """Tests for FastAPI instrumentation helper."""

    def test_skips_fastapi_instrumentation_when_disabled(self) -> None:
        app = FastAPI()

        assert instrument_fastapi_app(app, service_name="alpha-whale-api") is False
        assert not hasattr(app.state, "logfire_instrumented")

    def test_instruments_fastapi_with_shared_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_logfire = _FakeLogfire()
        app = FastAPI()

        monkeypatch.setenv("LOGFIRE_ENABLED", "true")
        monkeypatch.setenv("LOGFIRE_CAPTURE_HEADERS", "true")
        monkeypatch.setenv("LOGFIRE_FASTAPI_EXCLUDED_URLS", "^https?://[^/]+/healthz$")
        monkeypatch.setattr(observability, "_get_logfire", lambda: fake_logfire)

        assert instrument_fastapi_app(app, service_name="alpha-whale-api") is True
        assert instrument_fastapi_app(app, service_name="alpha-whale-api") is True

        assert app.state.logfire_instrumented is True
        assert fake_logfire.instrument_openai_calls == 1
        assert fake_logfire.instrument_fastapi_calls == [
            (
                app,
                {
                    "capture_headers": True,
                    "excluded_urls": "^https?://[^/]+/healthz$",
                },
            )
        ]
