"""Application settings with environment variable support."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Base settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="ai-engineering-monorepo")
    environment: Literal["development", "staging", "production"] = Field(default="development")
    debug: bool = Field(default=False)

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="json")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_key_prefix: str = Field(default="ai-mono:")
    redis_default_ttl: int = Field(default=300, ge=1)
    redis_connect_timeout: float = Field(default=5.0, gt=0)
    redis_max_retries: int = Field(default=3, ge=0)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
