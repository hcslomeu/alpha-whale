"""Configuration for AlphaWhale agent tracing and observability."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """Environment-based settings for agent observability.

    Reads standard LANGSMITH_* env vars (no prefix) so that both this class
    and LangChain's auto-tracing use the same variables from .env.
    """

    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "alpha-whale"

    # LLM response caching (requires Redis)
    llm_cache_enabled: bool = False
    llm_cache_redis_url: str = "redis://localhost:6379/1"
