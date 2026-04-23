"""Configuration for AlphaWhale API service."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Environment-based settings for the FastAPI service.

    Supabase credentials use bare names (SUPABASE_URL, SUPABASE_KEY) shared
    across services. API-specific settings use the API_ prefix.
    """

    app_name: str = "AlphaWhale API"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]
    supabase_url: str = Field(validation_alias="SUPABASE_URL")
    supabase_key: SecretStr = Field(validation_alias="SUPABASE_KEY")

    # Redis cache
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    cache_ttl: int = 300
    cache_enabled: bool = False

    model_config = {"env_prefix": "API_", "populate_by_name": True}
