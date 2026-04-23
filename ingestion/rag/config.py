"""Configuration for the RAG pipeline."""

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings


class RAGSettings(BaseSettings):
    """Environment-based settings for the RAG pipeline.

    API keys use bare names shared across services.
    RAG-specific tuning parameters use the RAG_ prefix.
    """

    # --- API Keys (shared, no prefix) ---
    pinecone_api_key: SecretStr = Field(validation_alias="PINECONE_API_KEY")
    openai_api_key: SecretStr = Field(validation_alias="OPENAI_API_KEY")
    cohere_api_key: SecretStr = Field(validation_alias="COHERE_API_KEY")
    firecrawl_api_key: SecretStr = Field(validation_alias="FIRECRAWL_API_KEY")

    # --- Pinecone ---
    pinecone_index_name: str = Field(
        default="alphawhale-knowledge", validation_alias="RAG_PINECONE_INDEX"
    )
    pinecone_namespace: str = Field(
        default="financial-docs", validation_alias="RAG_PINECONE_NAMESPACE"
    )

    # --- Embeddings ---
    embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="RAG_EMBEDDING_MODEL"
    )
    embedding_dimensions: int = Field(default=1536, validation_alias="RAG_EMBEDDING_DIMENSIONS")

    # --- Chunking (Silver layer) ---
    chunk_size: int = Field(default=1024, validation_alias="RAG_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, validation_alias="RAG_CHUNK_OVERLAP")

    # --- Retrieval ---
    similarity_top_k: int = Field(default=10, validation_alias="RAG_SIMILARITY_TOP_K")
    rerank_top_n: int = Field(default=5, validation_alias="RAG_RERANK_TOP_N")
    cohere_rerank_model: str = Field(
        default="rerank-v3.5", validation_alias="RAG_COHERE_RERANK_MODEL"
    )

    # --- EDGAR ---
    edgar_user_agent: str = Field(
        validation_alias="RAG_EDGAR_USER_AGENT",
        description="SEC requires a User-Agent with company/email, e.g. 'MyApp admin@example.com'",
    )

    model_config = {"env_prefix": "RAG_", "populate_by_name": True}

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_must_be_less_than_chunk_size(cls, v: int, info: ValidationInfo) -> int:
        """Ensure overlap is smaller than chunk size."""
        chunk_size = info.data.get("chunk_size")
        if chunk_size and v >= chunk_size:
            msg = f"chunk_overlap ({v}) must be less than chunk_size ({chunk_size})"
            raise ValueError(msg)
        return v
