"""Tests for the query_knowledge_base agent tool (Phase 7)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from llama_index.core.schema import NodeWithScore, TextNode

from agent.tools import query_knowledge_base

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _reset_rag_globals() -> None:
    """Reset cached RAG components between tests."""
    import agent.tools as tools_module

    tools_module._rag_index = None
    tools_module._rag_settings = None


def _make_node_with_score(text: str, score: float, metadata: dict | None = None) -> NodeWithScore:
    node = TextNode(text=text, metadata=metadata or {})
    return NodeWithScore(node=node, score=score)


def _mock_settings() -> MagicMock:
    s = MagicMock()
    s.similarity_top_k = 10
    s.cohere_rerank_model = "rerank-v3.5"
    s.rerank_top_n = 5
    s.cohere_api_key.get_secret_value.return_value = "test-key"
    return s


# ---------------------------------------------------------------------------
# Tool schema tests
# ---------------------------------------------------------------------------


class TestToolSchema:
    def test_tool_name(self) -> None:
        assert query_knowledge_base.name == "query_knowledge_base"

    def test_tool_has_description(self) -> None:
        assert "SEC" in query_knowledge_base.description
        assert "knowledge base" in query_knowledge_base.description.lower()

    def test_tool_args_schema(self) -> None:
        schema = query_knowledge_base.args_schema
        assert schema is not None
        json_schema = schema.model_json_schema()  # type: ignore[union-attr]
        props = json_schema["properties"]
        assert "query" in props
        assert "ticker_filter" in props
        assert "top_k" in props


# ---------------------------------------------------------------------------
# Tool invocation tests
# ---------------------------------------------------------------------------


class TestQueryKnowledgeBase:
    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_returns_results_with_metadata(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        nodes = [
            _make_node_with_score(
                "Apple revenue grew 15%",
                0.95,
                {"source": "edgar", "ticker": "AAPL", "filing_type": "10-K"},
            ),
        ]
        mock_vir_cls.return_value.retrieve.return_value = nodes
        mock_rerank_cls.return_value.postprocess_nodes.return_value = nodes

        result = query_knowledge_base.invoke({"query": "Apple revenue"})

        assert result["count"] == 1
        assert result["results"][0]["score"] == 0.95
        assert result["results"][0]["metadata"]["ticker"] == "AAPL"

    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_empty_results(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        mock_vir_cls.return_value.retrieve.return_value = []

        result = query_knowledge_base.invoke({"query": "nonexistent topic"})

        assert result["count"] == 0
        assert result["results"] == []
        mock_rerank_cls.return_value.postprocess_nodes.assert_not_called()

    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_ticker_filter_creates_metadata_filter(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        mock_vir_cls.return_value.retrieve.return_value = []

        query_knowledge_base.invoke({"query": "revenue", "ticker_filter": "aapl"})

        call_kwargs = mock_vir_cls.call_args.kwargs
        assert call_kwargs["filters"] is not None
        assert call_kwargs["filters"].filters[0].value == "AAPL"

    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_no_ticker_filter_passes_none(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        mock_vir_cls.return_value.retrieve.return_value = []

        query_knowledge_base.invoke({"query": "market news"})

        call_kwargs = mock_vir_cls.call_args.kwargs
        assert call_kwargs["filters"] is None

    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_top_k_forwarded_to_reranker(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        mock_vir_cls.return_value.retrieve.return_value = [_make_node_with_score("text", 0.9)]
        mock_rerank_cls.return_value.postprocess_nodes.return_value = []

        query_knowledge_base.invoke({"query": "test", "top_k": 3})

        assert mock_rerank_cls.call_args.kwargs["top_n"] == 3

    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_text_truncated_to_500_chars(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        long_text = "A" * 1000
        nodes = [_make_node_with_score(long_text, 0.8)]
        mock_vir_cls.return_value.retrieve.return_value = nodes
        mock_rerank_cls.return_value.postprocess_nodes.return_value = nodes

        result = query_knowledge_base.invoke({"query": "test"})

        assert len(result["results"][0]["text"]) == 500

    @patch("agent.tools.logger")
    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_query_failure_returns_error(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
        _mock_logger: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        mock_vir_cls.return_value.retrieve.side_effect = RuntimeError("connection failed")

        result = query_knowledge_base.invoke({"query": "test"})

        assert "error" in result

    @patch("agent.tools.logger")
    @patch("agent.tools._get_rag_index")
    def test_init_failure_returns_error(
        self,
        mock_get_index: MagicMock,
        _mock_logger: MagicMock,
    ) -> None:
        mock_get_index.side_effect = RuntimeError("missing API key")

        result = query_knowledge_base.invoke({"query": "test"})

        assert result == {"error": "Knowledge base unavailable"}

    @patch("agent.tools.CohereRerank")
    @patch("agent.tools.VectorIndexRetriever")
    @patch("agent.tools._get_rag_index")
    def test_multiple_results_ordered(
        self,
        mock_get_index: MagicMock,
        mock_vir_cls: MagicMock,
        mock_rerank_cls: MagicMock,
    ) -> None:
        mock_get_index.return_value = (MagicMock(), _mock_settings())
        nodes = [
            _make_node_with_score("First result", 0.95),
            _make_node_with_score("Second result", 0.80),
            _make_node_with_score("Third result", 0.65),
        ]
        mock_vir_cls.return_value.retrieve.return_value = nodes
        mock_rerank_cls.return_value.postprocess_nodes.return_value = nodes

        result = query_knowledge_base.invoke({"query": "test"})

        assert result["count"] == 3
        scores = [r["score"] for r in result["results"]]
        assert scores == [0.95, 0.8, 0.65]
