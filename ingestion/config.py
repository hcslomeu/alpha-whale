"""Configuration for AlphaWhale ingestion pipeline."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class IngestionSettings(BaseSettings):
    """Environment-based settings for the Massive API + Supabase pipeline.

    Supabase credentials use bare names (SUPABASE_URL, SUPABASE_KEY) shared
    across services. Ingestion-specific settings use the INGESTION_ prefix.
    """

    supabase_url: str = Field(validation_alias="SUPABASE_URL")
    supabase_key: SecretStr = Field(validation_alias="SUPABASE_KEY")
    massive_api_key: SecretStr = Field(validation_alias="INGESTION_MASSIVE_API_KEY")
    massive_base_url: str = Field(
        default="https://api.polygon.io", validation_alias="INGESTION_MASSIVE_BASE_URL"
    )

    model_config = {"env_prefix": "INGESTION_", "populate_by_name": True}
