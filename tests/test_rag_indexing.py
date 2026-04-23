"""Tests for Gold-layer indexing (ingestion.rag.indexing)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.pinecone import PineconeVectorStore

from ingestion.rag.config import RAGSettings
from ingestion.rag.indexing import build_embed_model, build_vector_store, index_nodes

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rag_settings() -> RAGSettings:
    return RAGSettings(
        pinecone_api_key="test-pinecone-key",
        openai_api_key="test-openai-key",
        cohere_api_key="test-cohere",
        firecrawl_api_key="test-firecrawl",
        edgar_user_agent="TestApp test@example.com",
        pinecone_index_name="test-index",
        pinecone_namespace="test-namespace",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
    )


@pytest.fixture()
def sample_nodes() -> list[TextNode]:
    """TextNodes as they would come from Phase 4 chunking."""
    return [
        TextNode(
            text="Apple reported revenue of 394 billion dollars.",
            metadata={
                "source": "edgar",
                "ticker": "AAPL",
                "filing_type": "10-K",
                "filed_date": "2024-11-01",
                "company_name": "Apple Inc",
                "accession_number": "0000320193-24-000081",
                "filing_url": "https://sec.gov/filing.htm",
            },
            excluded_embed_metadata_keys=["accession_number", "filed_date", "filing_url"],
            excluded_llm_metadata_keys=["accession_number", "filing_url"],
        ),
        TextNode(
            text="Fed raised interest rates by 25 basis points.",
            metadata={
                "source": "firecrawl",
                "title": "Fed Raises Rates",
                "published_date": "2024-12-15",
                "source_domain": "reuters.com",
                "url": "https://reuters.com/fed-rates",
            },
            excluded_embed_metadata_keys=["published_date", "url"],
            excluded_llm_metadata_keys=["url"],
        ),
    ]


# ---------------------------------------------------------------------------
# build_vector_store tests
# ---------------------------------------------------------------------------


class TestBuildVectorStore:
    @patch("ingestion.rag.indexing.Pinecone")
    def test_creates_pinecone_client_with_api_key(
        self, mock_pinecone_cls: MagicMock, rag_settings: RAGSettings
    ) -> None:
        build_vector_store(rag_settings)
        mock_pinecone_cls.assert_called_once_with(api_key="test-pinecone-key")

    @patch("ingestion.rag.indexing.Pinecone")
    def test_connects_to_configured_index(
        self, mock_pinecone_cls: MagicMock, rag_settings: RAGSettings
    ) -> None:
        mock_pc = mock_pinecone_cls.return_value
        build_vector_store(rag_settings)
        mock_pc.Index.assert_called_once_with("test-index")

    @patch("ingestion.rag.indexing.PineconeVectorStore")
    @patch("ingestion.rag.indexing.Pinecone")
    def test_returns_vector_store_with_namespace(
        self,
        mock_pinecone_cls: MagicMock,
        mock_vs_cls: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        mock_pc = mock_pinecone_cls.return_value
        mock_index = mock_pc.Index.return_value

        build_vector_store(rag_settings)

        mock_vs_cls.assert_called_once_with(
            pinecone_index=mock_index,
            namespace="test-namespace",
        )

    @patch("ingestion.rag.indexing.Pinecone")
    def test_return_type(self, mock_pinecone_cls: MagicMock, rag_settings: RAGSettings) -> None:
        result = build_vector_store(rag_settings)
        assert isinstance(result, PineconeVectorStore)


# ---------------------------------------------------------------------------
# build_embed_model tests
# ---------------------------------------------------------------------------


class TestBuildEmbedModel:
    def test_return_type(self, rag_settings: RAGSettings) -> None:
        model = build_embed_model(rag_settings)
        assert isinstance(model, OpenAIEmbedding)

    def test_model_name(self, rag_settings: RAGSettings) -> None:
        model = build_embed_model(rag_settings)
        assert model.model_name == "text-embedding-3-small"

    def test_dimensions(self, rag_settings: RAGSettings) -> None:
        model = build_embed_model(rag_settings)
        assert model.dimensions == 1536

    def test_api_key_passed(self, rag_settings: RAGSettings) -> None:
        model = build_embed_model(rag_settings)
        assert model.api_key == "test-openai-key"

    def test_custom_model(self, rag_settings: RAGSettings) -> None:
        custom_settings = RAGSettings(
            pinecone_api_key=rag_settings.pinecone_api_key,
            openai_api_key=rag_settings.openai_api_key,
            cohere_api_key=rag_settings.cohere_api_key,
            firecrawl_api_key=rag_settings.firecrawl_api_key,
            edgar_user_agent=rag_settings.edgar_user_agent,
            pinecone_index_name=rag_settings.pinecone_index_name,
            pinecone_namespace=rag_settings.pinecone_namespace,
            embedding_model="text-embedding-3-large",
            embedding_dimensions=3072,
        )
        model = build_embed_model(custom_settings)
        assert model.model_name == "text-embedding-3-large"
        assert model.dimensions == 3072


# ---------------------------------------------------------------------------
# index_nodes tests
# ---------------------------------------------------------------------------


class TestIndexNodes:
    @patch("ingestion.rag.indexing.VectorStoreIndex")
    @patch("ingestion.rag.indexing.StorageContext")
    @patch("ingestion.rag.indexing.build_embed_model")
    @patch("ingestion.rag.indexing.build_vector_store")
    def test_returns_vector_store_index(
        self,
        mock_build_vs: MagicMock,
        mock_build_em: MagicMock,
        mock_sc: MagicMock,
        mock_vsi: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        result = index_nodes(sample_nodes, rag_settings)
        assert result == mock_vsi.return_value

    @patch("ingestion.rag.indexing.VectorStoreIndex")
    @patch("ingestion.rag.indexing.StorageContext")
    @patch("ingestion.rag.indexing.build_embed_model")
    @patch("ingestion.rag.indexing.build_vector_store")
    def test_creates_storage_context_with_vector_store(
        self,
        mock_build_vs: MagicMock,
        mock_build_em: MagicMock,
        mock_sc: MagicMock,
        mock_vsi: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        index_nodes(sample_nodes, rag_settings)
        mock_sc.from_defaults.assert_called_once_with(
            vector_store=mock_build_vs.return_value,
        )

    @patch("ingestion.rag.indexing.VectorStoreIndex")
    @patch("ingestion.rag.indexing.StorageContext")
    @patch("ingestion.rag.indexing.build_embed_model")
    @patch("ingestion.rag.indexing.build_vector_store")
    def test_passes_nodes_to_index(
        self,
        mock_build_vs: MagicMock,
        mock_build_em: MagicMock,
        mock_sc: MagicMock,
        mock_vsi: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        index_nodes(sample_nodes, rag_settings)
        mock_vsi.assert_called_once_with(
            nodes=sample_nodes,
            storage_context=mock_sc.from_defaults.return_value,
            embed_model=mock_build_em.return_value,
            show_progress=False,
        )

    @patch("ingestion.rag.indexing.VectorStoreIndex")
    @patch("ingestion.rag.indexing.StorageContext")
    @patch("ingestion.rag.indexing.build_embed_model")
    @patch("ingestion.rag.indexing.build_vector_store")
    def test_show_progress_forwarded(
        self,
        mock_build_vs: MagicMock,
        mock_build_em: MagicMock,
        mock_sc: MagicMock,
        mock_vsi: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        index_nodes(sample_nodes, rag_settings, show_progress=True)
        call_kwargs = mock_vsi.call_args.kwargs
        assert call_kwargs["show_progress"] is True

    @patch("ingestion.rag.indexing.VectorStoreIndex")
    @patch("ingestion.rag.indexing.StorageContext")
    @patch("ingestion.rag.indexing.build_embed_model")
    @patch("ingestion.rag.indexing.build_vector_store")
    def test_empty_nodes_still_creates_index(
        self,
        mock_build_vs: MagicMock,
        mock_build_em: MagicMock,
        mock_sc: MagicMock,
        mock_vsi: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        result = index_nodes([], rag_settings)
        mock_vsi.assert_called_once()
        assert mock_vsi.call_args.kwargs["nodes"] == []
        assert result == mock_vsi.return_value

    @patch("ingestion.rag.indexing.VectorStoreIndex")
    @patch("ingestion.rag.indexing.StorageContext")
    @patch("ingestion.rag.indexing.build_embed_model")
    @patch("ingestion.rag.indexing.build_vector_store")
    def test_delegates_to_builders(
        self,
        mock_build_vs: MagicMock,
        mock_build_em: MagicMock,
        mock_sc: MagicMock,
        mock_vsi: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        index_nodes(sample_nodes, rag_settings)
        mock_build_vs.assert_called_once_with(rag_settings)
        mock_build_em.assert_called_once_with(rag_settings)
