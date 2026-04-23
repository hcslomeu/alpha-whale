"""Tests for RAG pipeline configuration."""

import pytest
from pydantic import ValidationError

from ingestion.rag.config import RAGSettings

# Minimal env vars required to instantiate RAGSettings
REQUIRED_ENV = {
    "PINECONE_API_KEY": "test-pinecone-key",
    "OPENAI_API_KEY": "test-openai-key",
    "COHERE_API_KEY": "test-cohere-key",
    "FIRECRAWL_API_KEY": "test-firecrawl-key",
    "RAG_EDGAR_USER_AGENT": "TestApp test@example.com",
}


@pytest.fixture()
def rag_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all required env vars for RAGSettings."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


class TestRAGSettingsDefaults:
    """Verify default values when only required env vars are set."""

    def test_pinecone_index_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.pinecone_index_name == "alphawhale-knowledge"

    def test_pinecone_namespace_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.pinecone_namespace == "financial-docs"

    def test_embedding_model_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.embedding_model == "text-embedding-3-small"

    def test_embedding_dimensions_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.embedding_dimensions == 1536

    def test_chunk_size_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.chunk_size == 1024

    def test_chunk_overlap_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.chunk_overlap == 200

    def test_similarity_top_k_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.similarity_top_k == 10

    def test_rerank_top_n_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.rerank_top_n == 5

    def test_cohere_rerank_model_default(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.cohere_rerank_model == "rerank-v3.5"


class TestRAGSettingsSecrets:
    """Verify API keys are stored as SecretStr."""

    def test_api_keys_are_secret(self, rag_env: None) -> None:
        settings = RAGSettings()
        assert settings.pinecone_api_key.get_secret_value() == "test-pinecone-key"
        assert settings.openai_api_key.get_secret_value() == "test-openai-key"
        assert settings.cohere_api_key.get_secret_value() == "test-cohere-key"
        assert settings.firecrawl_api_key.get_secret_value() == "test-firecrawl-key"

    def test_secret_not_exposed_in_repr(self, rag_env: None) -> None:
        settings = RAGSettings()
        repr_str = repr(settings)
        assert "test-pinecone-key" not in repr_str
        assert "test-openai-key" not in repr_str


class TestRAGSettingsValidation:
    """Verify validation rules."""

    def test_missing_required_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("PINECONE_API_KEY")
        with pytest.raises(ValidationError, match="PINECONE_API_KEY"):
            RAGSettings(_env_file=None)

    def test_missing_edgar_user_agent_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for key, value in REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("RAG_EDGAR_USER_AGENT")
        with pytest.raises(ValidationError, match="RAG_EDGAR_USER_AGENT"):
            RAGSettings(_env_file=None)

    def test_chunk_overlap_exceeds_chunk_size_raises(
        self, rag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAG_CHUNK_SIZE", "512")
        monkeypatch.setenv("RAG_CHUNK_OVERLAP", "600")
        with pytest.raises(ValidationError, match="chunk_overlap.*must be less than"):
            RAGSettings()

    def test_env_override_works(self, rag_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAG_CHUNK_SIZE", "256")
        monkeypatch.setenv("RAG_CHUNK_OVERLAP", "50")
        monkeypatch.setenv("RAG_SIMILARITY_TOP_K", "20")
        settings = RAGSettings()
        assert settings.chunk_size == 256
        assert settings.chunk_overlap == 50
        assert settings.similarity_top_k == 20
