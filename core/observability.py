"""Shared Logfire observability bootstrap helpers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.exceptions import ConfigurationError

if TYPE_CHECKING:
    from fastapi import FastAPI


_configured_service_name: str | None = None
_openai_instrumented = False
_settings: ObservabilitySettings | None = None


class ObservabilitySettings(BaseSettings):
    """Settings for shared Logfire instrumentation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    logfire_enabled: bool = Field(default=False)
    logfire_token: SecretStr | None = Field(default=None)
    logfire_send_to_logfire: bool = Field(default=True)
    logfire_environment: str | None = Field(default=None)
    app_environment: str | None = Field(default=None, validation_alias="ENVIRONMENT")
    logfire_capture_headers: bool = Field(default=False)
    logfire_fastapi_excluded_urls: str = Field(default=r"^https?://[^/]+/health/?$")

    @property
    def resolved_environment(self) -> str:
        """Return the environment label to attach to Logfire resources."""
        return self.logfire_environment or self.app_environment or "development"


def _reset_observability_state() -> None:
    """Reset module-level state for tests."""
    global _configured_service_name, _openai_instrumented, _settings
    _configured_service_name = None
    _openai_instrumented = False
    _settings = None


def _get_logfire() -> Any:
    """Import logfire lazily so disabled environments don't need the package loaded."""
    try:
        return import_module("logfire")
    except ModuleNotFoundError as exc:
        raise ConfigurationError(
            "LOGFIRE_ENABLED=true requires the 'logfire' package to be installed."
        ) from exc


def _get_settings() -> ObservabilitySettings:
    """Return cached observability settings."""
    global _settings
    if _settings is None:
        _settings = ObservabilitySettings()
    return _settings


def get_logfire_instance() -> Any | None:
    """Return the Logfire module when observability is enabled."""
    settings = _get_settings()
    if not settings.logfire_enabled:
        return None
    return _get_logfire()


def configure_observability(*, service_name: str) -> bool:
    """Configure shared Logfire instrumentation for the current process."""
    global _configured_service_name, _openai_instrumented

    settings = _get_settings()
    if not settings.logfire_enabled:
        return False

    logfire = _get_logfire()
    token = settings.logfire_token.get_secret_value() if settings.logfire_token else None

    if _configured_service_name != service_name:
        logfire.configure(
            send_to_logfire=settings.logfire_send_to_logfire,
            token=token,
            service_name=service_name,
            environment=settings.resolved_environment,
        )
        _configured_service_name = service_name

    if not _openai_instrumented:
        logfire.instrument_openai()
        _openai_instrumented = True

    return True


def instrument_fastapi_app(app: FastAPI, *, service_name: str) -> bool:
    """Configure Logfire and instrument a FastAPI app when enabled."""
    if not configure_observability(service_name=service_name):
        return False

    if getattr(app.state, "logfire_instrumented", False):
        return True

    settings = _get_settings()
    logfire = _get_logfire()
    logfire.instrument_fastapi(
        app,
        capture_headers=settings.logfire_capture_headers,
        excluded_urls=settings.logfire_fastapi_excluded_urls,
    )
    app.state.logfire_instrumented = True
    return True
