"""Tests for AgentSettings configuration."""

import pytest

from agent.config import AgentSettings


class TestAgentSettingsDefaults:
    """Test defaults when no env vars are set.

    load_dotenv() may populate os.environ from .env, so we must
    explicitly clear the LANGSMITH_* vars to test true defaults.
    """

    def test_tracing_defaults_to_false(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
        settings = AgentSettings()
        assert settings.langsmith_tracing is False

    def test_api_key_defaults_to_none(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        settings = AgentSettings()
        assert settings.langsmith_api_key is None

    def test_project_defaults_to_alpha_whale(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
        settings = AgentSettings()
        assert settings.langsmith_project == "alpha-whale"


class TestAgentSettingsFromEnv:
    def test_loads_tracing_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        settings = AgentSettings()
        assert settings.langsmith_tracing is True

    def test_loads_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_test_abc123")
        settings = AgentSettings()
        assert settings.langsmith_api_key is not None
        assert settings.langsmith_api_key.get_secret_value() == "lsv2_test_abc123"

    def test_loads_project_from_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGSMITH_PROJECT", "my-custom-project")
        settings = AgentSettings()
        assert settings.langsmith_project == "my-custom-project"


class TestSecretStrMasking:
    def test_api_key_masked_in_repr(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_secret_key")
        settings = AgentSettings()
        settings_repr = repr(settings)
        assert "lsv2_secret_key" not in settings_repr
        assert "**********" in settings_repr

    def test_api_key_accessible_via_get_secret_value(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_real_key")
        settings = AgentSettings()
        assert settings.langsmith_api_key is not None
        assert settings.langsmith_api_key.get_secret_value() == "lsv2_real_key"
