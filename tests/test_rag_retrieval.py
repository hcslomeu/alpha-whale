"""Tests for hybrid retrieval (ingestion.rag.retrieval)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.postprocessor.cohere_rerank import CohereRerank

from ingestion.rag.config import RAGSettings
from ingestion.rag.retrieval import (
    build_hybrid_retriever,
    build_reranker,
    retrieve_and_rerank,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rag_settings() -> RAGSettings:
    return RAGSettings(
        pinecone_api_key="test-pinecone",
        openai_api_key="test-openai",
        cohere_api_key="test-cohere-key",
        firecrawl_api_key="test-firecrawl",
        edgar_user_agent="TestApp test@example.com",
        similarity_top_k=10,
        rerank_top_n=5,
        cohere_rerank_model="rerank-v3.5",
    )


@pytest.fixture()
def sample_nodes() -> list[TextNode]:
    return [
        TextNode(
            text="Apple reported revenue of 394 billion dollars.",
            metadata={"source": "edgar", "ticker": "AAPL"},
        ),
        TextNode(
            text="Fed raised interest rates by 25 basis points.",
            metadata={"source": "firecrawl", "title": "Fed Raises Rates"},
        ),
        TextNode(
            text="Microsoft cloud revenue grew 22 percent year over year.",
            metadata={"source": "edgar", "ticker": "MSFT"},
        ),
    ]


@pytest.fixture()
def mock_index() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# build_hybrid_retriever tests
# ---------------------------------------------------------------------------


class TestBuildHybridRetriever:
    @patch("ingestion.rag.retrieval.BM25Retriever")
    @patch("ingestion.rag.retrieval.VectorIndexRetriever")
    @patch("ingestion.rag.retrieval.QueryFusionRetriever")
    def test_creates_vector_retriever_with_top_k(
        self,
        mock_qfr: MagicMock,
        mock_vir: MagicMock,
        mock_bm25: MagicMock,
        mock_index: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        build_hybrid_retriever(mock_index, sample_nodes, rag_settings)
        mock_vir.assert_called_once_with(
            index=mock_index,
            similarity_top_k=10,
        )

    @patch("ingestion.rag.retrieval.BM25Retriever")
    @patch("ingestion.rag.retrieval.VectorIndexRetriever")
    @patch("ingestion.rag.retrieval.QueryFusionRetriever")
    def test_creates_bm25_retriever_with_nodes(
        self,
        mock_qfr: MagicMock,
        mock_vir: MagicMock,
        mock_bm25: MagicMock,
        mock_index: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        build_hybrid_retriever(mock_index, sample_nodes, rag_settings)
        mock_bm25.from_defaults.assert_called_once_with(
            nodes=sample_nodes,
            similarity_top_k=10,
        )

    @patch("ingestion.rag.retrieval.BM25Retriever")
    @patch("ingestion.rag.retrieval.VectorIndexRetriever")
    @patch("ingestion.rag.retrieval.QueryFusionRetriever")
    def test_fusion_uses_reciprocal_rank(
        self,
        mock_qfr: MagicMock,
        mock_vir: MagicMock,
        mock_bm25: MagicMock,
        mock_index: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        build_hybrid_retriever(mock_index, sample_nodes, rag_settings)
        call_kwargs = mock_qfr.call_args.kwargs
        assert call_kwargs["mode"] == FUSION_MODES.RECIPROCAL_RANK

    @patch("ingestion.rag.retrieval.BM25Retriever")
    @patch("ingestion.rag.retrieval.VectorIndexRetriever")
    @patch("ingestion.rag.retrieval.QueryFusionRetriever")
    def test_fusion_passes_both_retrievers(
        self,
        mock_qfr: MagicMock,
        mock_vir: MagicMock,
        mock_bm25: MagicMock,
        mock_index: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        build_hybrid_retriever(mock_index, sample_nodes, rag_settings)
        call_kwargs = mock_qfr.call_args.kwargs
        assert len(call_kwargs["retrievers"]) == 2
        assert call_kwargs["retrievers"][0] == mock_vir.return_value
        assert call_kwargs["retrievers"][1] == mock_bm25.from_defaults.return_value

    @patch("ingestion.rag.retrieval.BM25Retriever")
    @patch("ingestion.rag.retrieval.VectorIndexRetriever")
    @patch("ingestion.rag.retrieval.QueryFusionRetriever")
    def test_num_queries_is_one(
        self,
        mock_qfr: MagicMock,
        mock_vir: MagicMock,
        mock_bm25: MagicMock,
        mock_index: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        """num_queries=1 disables LLM-based query generation."""
        build_hybrid_retriever(mock_index, sample_nodes, rag_settings)
        call_kwargs = mock_qfr.call_args.kwargs
        assert call_kwargs["num_queries"] == 1

    @patch("ingestion.rag.retrieval.BM25Retriever")
    @patch("ingestion.rag.retrieval.VectorIndexRetriever")
    @patch("ingestion.rag.retrieval.QueryFusionRetriever")
    def test_similarity_top_k_forwarded(
        self,
        mock_qfr: MagicMock,
        mock_vir: MagicMock,
        mock_bm25: MagicMock,
        mock_index: MagicMock,
        sample_nodes: list[TextNode],
        rag_settings: RAGSettings,
    ) -> None:
        build_hybrid_retriever(mock_index, sample_nodes, rag_settings)
        call_kwargs = mock_qfr.call_args.kwargs
        assert call_kwargs["similarity_top_k"] == 10


# ---------------------------------------------------------------------------
# build_reranker tests
# ---------------------------------------------------------------------------


class TestBuildReranker:
    def test_return_type(self, rag_settings: RAGSettings) -> None:
        reranker = build_reranker(rag_settings)
        assert isinstance(reranker, CohereRerank)

    def test_model_configured(self, rag_settings: RAGSettings) -> None:
        reranker = build_reranker(rag_settings)
        assert reranker.model == "rerank-v3.5"

    def test_top_n_configured(self, rag_settings: RAGSettings) -> None:
        reranker = build_reranker(rag_settings)
        assert reranker.top_n == 5

    @patch("ingestion.rag.retrieval.CohereRerank")
    def test_api_key_passed(self, mock_rerank_cls: MagicMock, rag_settings: RAGSettings) -> None:
        build_reranker(rag_settings)
        mock_rerank_cls.assert_called_once_with(
            model="rerank-v3.5",
            top_n=5,
            api_key="test-cohere-key",
        )


# ---------------------------------------------------------------------------
# retrieve_and_rerank tests
# ---------------------------------------------------------------------------


class TestRetrieveAndRerank:
    def test_calls_retriever_with_query(self) -> None:
        mock_retriever = MagicMock()
        mock_reranker = MagicMock()
        mock_retriever.retrieve.return_value = [MagicMock(spec=NodeWithScore)]

        retrieve_and_rerank("AAPL revenue", mock_retriever, mock_reranker)

        mock_retriever.retrieve.assert_called_once_with("AAPL revenue")

    def test_passes_results_to_reranker(self) -> None:
        mock_retriever = MagicMock()
        mock_reranker = MagicMock()
        fused = [MagicMock(spec=NodeWithScore), MagicMock(spec=NodeWithScore)]
        mock_retriever.retrieve.return_value = fused

        retrieve_and_rerank("AAPL revenue", mock_retriever, mock_reranker)

        mock_reranker.postprocess_nodes.assert_called_once_with(fused, query_str="AAPL revenue")

    def test_returns_reranked_results(self) -> None:
        mock_retriever = MagicMock()
        mock_reranker = MagicMock()
        reranked = [MagicMock(spec=NodeWithScore)]
        mock_retriever.retrieve.return_value = [MagicMock(spec=NodeWithScore)]
        mock_reranker.postprocess_nodes.return_value = reranked

        result = retrieve_and_rerank("query", mock_retriever, mock_reranker)

        assert result == reranked

    def test_empty_retrieval_skips_reranking(self) -> None:
        mock_retriever = MagicMock()
        mock_reranker = MagicMock()
        mock_retriever.retrieve.return_value = []

        result = retrieve_and_rerank("query", mock_retriever, mock_reranker)

        assert result == []
        mock_reranker.postprocess_nodes.assert_not_called()

    def test_preserves_result_order(self) -> None:
        mock_retriever = MagicMock()
        mock_reranker = MagicMock()
        node_a = MagicMock(spec=NodeWithScore)
        node_b = MagicMock(spec=NodeWithScore)
        mock_retriever.retrieve.return_value = [node_a, node_b]
        mock_reranker.postprocess_nodes.return_value = [node_b, node_a]

        result = retrieve_and_rerank("query", mock_retriever, mock_reranker)

        assert result[0] == node_b
        assert result[1] == node_a
