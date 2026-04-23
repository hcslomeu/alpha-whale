"""Tests for the RAG ingestion pipeline (ingestion.rag.pipeline)."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from llama_index.core.schema import TextNode

from ingestion.rag.config import RAGSettings
from ingestion.rag.edgar import EdgarFiling, FilingType
from ingestion.rag.firecrawl_source import NewsArticle, NewsArticleMetadata
from ingestion.rag.pipeline import (
    IngestionRequest,
    IngestionResult,
    chunk,
    ingest_articles,
    ingest_filings,
    run_pipeline,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rag_settings() -> RAGSettings:
    return RAGSettings(
        pinecone_api_key="test-pinecone",
        openai_api_key="test-openai",
        cohere_api_key="test-cohere",
        firecrawl_api_key="test-firecrawl",
        edgar_user_agent="TestApp test@example.com",
        pinecone_index_name="test-index",
        pinecone_namespace="test-ns",
    )


@pytest.fixture()
def sample_filing() -> EdgarFiling:
    return EdgarFiling(
        accession_number="0000320193-24-000081",
        ticker="AAPL",
        filing_type=FilingType.TEN_K,
        filed_date=date(2024, 11, 1),
        company_name="Apple Inc",
        filing_url="https://sec.gov/filing.htm",
        text="Apple reported revenue of 394 billion dollars in fiscal year 2024.",
    )


@pytest.fixture()
def sample_article() -> NewsArticle:
    return NewsArticle(
        text="Fed raised interest rates by 25 basis points in December meeting.",
        metadata=NewsArticleMetadata(
            title="Fed Raises Rates",
            published_date="2024-12-15",
            source_domain="reuters.com",
            url="https://reuters.com/fed-rates",
        ),
    )


@pytest.fixture()
def default_request() -> IngestionRequest:
    return IngestionRequest(
        tickers=["AAPL"],
        filing_types=[FilingType.TEN_K],
        news_urls=["https://reuters.com/fed-rates"],
    )


# ---------------------------------------------------------------------------
# IngestionRequest tests
# ---------------------------------------------------------------------------


class TestIngestionRequest:
    def test_defaults(self) -> None:
        req = IngestionRequest()
        assert req.tickers == []
        assert req.filing_types == [FilingType.TEN_K, FilingType.TEN_Q]
        assert req.news_urls == []
        assert req.max_filings_per_query == 5
        assert req.show_progress is False

    def test_custom_values(self) -> None:
        req = IngestionRequest(
            tickers=["AAPL", "MSFT"],
            filing_types=[FilingType.TEN_K],
            news_urls=["https://example.com"],
            max_filings_per_query=10,
            show_progress=True,
        )
        assert req.tickers == ["AAPL", "MSFT"]
        assert req.max_filings_per_query == 10
        assert req.show_progress is True


class TestIngestionResult:
    def test_defaults(self) -> None:
        result = IngestionResult()
        assert result.filings_fetched == 0
        assert result.articles_fetched == 0
        assert result.nodes_chunked == 0
        assert result.nodes_indexed == 0

    def test_frozen(self) -> None:
        result = IngestionResult(filings_fetched=5)
        with pytest.raises(AttributeError):
            result.filings_fetched = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ingest_filings tests
# ---------------------------------------------------------------------------


class TestIngestFilings:
    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.EdgarClient")
    async def test_fetches_filings_for_all_tickers(
        self,
        mock_client_cls: MagicMock,
        sample_filing: EdgarFiling,
        rag_settings: RAGSettings,
    ) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.search_and_fetch = AsyncMock(return_value=[sample_filing])

        request = IngestionRequest(
            tickers=["AAPL", "MSFT"],
            filing_types=[FilingType.TEN_K],
        )
        filings = await ingest_filings(request, rag_settings)

        assert len(filings) == 2
        assert mock_client.search_and_fetch.call_count == 2

    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.EdgarClient")
    async def test_fetches_all_filing_types(
        self,
        mock_client_cls: MagicMock,
        sample_filing: EdgarFiling,
        rag_settings: RAGSettings,
    ) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.search_and_fetch = AsyncMock(return_value=[sample_filing])

        request = IngestionRequest(
            tickers=["AAPL"],
            filing_types=[FilingType.TEN_K, FilingType.TEN_Q],
        )
        filings = await ingest_filings(request, rag_settings)

        assert len(filings) == 2
        assert mock_client.search_and_fetch.call_count == 2

    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.EdgarClient")
    async def test_empty_tickers_returns_empty(
        self,
        mock_client_cls: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        request = IngestionRequest(tickers=[])
        filings = await ingest_filings(request, rag_settings)
        assert filings == []

    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.EdgarClient")
    async def test_passes_max_results(
        self,
        mock_client_cls: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.search_and_fetch = AsyncMock(return_value=[])

        request = IngestionRequest(
            tickers=["AAPL"],
            filing_types=[FilingType.TEN_K],
            max_filings_per_query=3,
        )
        await ingest_filings(request, rag_settings)

        call_kwargs = mock_client.search_and_fetch.call_args.kwargs
        assert call_kwargs["max_results"] == 3


# ---------------------------------------------------------------------------
# ingest_articles tests
# ---------------------------------------------------------------------------


class TestIngestArticles:
    @patch("ingestion.rag.pipeline.asyncio")
    @patch("ingestion.rag.pipeline.FirecrawlNewsSource")
    async def test_scrapes_news_urls(
        self,
        mock_source_cls: MagicMock,
        mock_asyncio: MagicMock,
        sample_article: NewsArticle,
        rag_settings: RAGSettings,
    ) -> None:
        mock_source = mock_source_cls.return_value
        mock_source.scrape_urls.return_value = [sample_article]
        mock_asyncio.to_thread = AsyncMock(return_value=[sample_article])

        request = IngestionRequest(news_urls=["https://example.com"])
        articles = await ingest_articles(request, rag_settings)

        assert len(articles) == 1
        mock_asyncio.to_thread.assert_called_once_with(
            mock_source.scrape_urls, ["https://example.com"]
        )

    @patch("ingestion.rag.pipeline.FirecrawlNewsSource")
    async def test_empty_urls_returns_empty(
        self,
        mock_source_cls: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        request = IngestionRequest(news_urls=[])
        articles = await ingest_articles(request, rag_settings)
        assert articles == []
        mock_source_cls.assert_not_called()


# ---------------------------------------------------------------------------
# chunk tests
# ---------------------------------------------------------------------------


class TestChunk:
    @patch("ingestion.rag.pipeline.chunk_articles")
    @patch("ingestion.rag.pipeline.chunk_filings")
    def test_combines_filing_and_article_nodes(
        self,
        mock_chunk_filings: MagicMock,
        mock_chunk_articles: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        filing_node = TextNode(text="filing chunk", metadata={"source": "edgar"})
        article_node = TextNode(text="article chunk", metadata={"source": "firecrawl"})
        mock_chunk_filings.return_value = [filing_node]
        mock_chunk_articles.return_value = [article_node]

        nodes = chunk([], [], rag_settings)

        assert len(nodes) == 2
        assert nodes[0].metadata["source"] == "edgar"
        assert nodes[1].metadata["source"] == "firecrawl"

    @patch("ingestion.rag.pipeline.chunk_articles")
    @patch("ingestion.rag.pipeline.chunk_filings")
    def test_empty_inputs_returns_empty(
        self,
        mock_chunk_filings: MagicMock,
        mock_chunk_articles: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        mock_chunk_filings.return_value = []
        mock_chunk_articles.return_value = []

        nodes = chunk([], [], rag_settings)
        assert nodes == []


# ---------------------------------------------------------------------------
# run_pipeline end-to-end tests
# ---------------------------------------------------------------------------


class TestRunPipeline:
    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.index")
    @patch("ingestion.rag.pipeline.chunk")
    @patch("ingestion.rag.pipeline.ingest_articles", new_callable=AsyncMock)
    @patch("ingestion.rag.pipeline.ingest_filings", new_callable=AsyncMock)
    async def test_full_pipeline_returns_result(
        self,
        mock_ingest_filings: AsyncMock,
        mock_ingest_articles: AsyncMock,
        mock_chunk: MagicMock,
        mock_index: MagicMock,
        rag_settings: RAGSettings,
        sample_filing: EdgarFiling,
        sample_article: NewsArticle,
    ) -> None:
        mock_ingest_filings.return_value = [sample_filing]
        mock_ingest_articles.return_value = [sample_article]
        nodes = [TextNode(text="chunk1"), TextNode(text="chunk2")]
        mock_chunk.return_value = nodes

        request = IngestionRequest(
            tickers=["AAPL"],
            news_urls=["https://example.com"],
        )
        result = await run_pipeline(request, rag_settings)

        assert result.filings_fetched == 1
        assert result.articles_fetched == 1
        assert result.nodes_chunked == 2
        assert result.nodes_indexed == 2
        mock_index.assert_called_once()

    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.index")
    @patch("ingestion.rag.pipeline.chunk")
    @patch("ingestion.rag.pipeline.ingest_articles", new_callable=AsyncMock)
    @patch("ingestion.rag.pipeline.ingest_filings", new_callable=AsyncMock)
    async def test_empty_nodes_skips_indexing(
        self,
        mock_ingest_filings: AsyncMock,
        mock_ingest_articles: AsyncMock,
        mock_chunk: MagicMock,
        mock_index: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        mock_ingest_filings.return_value = []
        mock_ingest_articles.return_value = []
        mock_chunk.return_value = []

        request = IngestionRequest(tickers=["AAPL"])
        result = await run_pipeline(request, rag_settings)

        assert result.nodes_indexed == 0
        mock_index.assert_not_called()

    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.index")
    @patch("ingestion.rag.pipeline.chunk")
    @patch("ingestion.rag.pipeline.ingest_articles", new_callable=AsyncMock)
    @patch("ingestion.rag.pipeline.ingest_filings", new_callable=AsyncMock)
    async def test_uses_default_settings_when_none(
        self,
        mock_ingest_filings: AsyncMock,
        mock_ingest_articles: AsyncMock,
        mock_chunk: MagicMock,
        mock_index: MagicMock,
    ) -> None:
        mock_ingest_filings.return_value = []
        mock_ingest_articles.return_value = []
        mock_chunk.return_value = []

        request = IngestionRequest()

        with patch("ingestion.rag.pipeline.RAGSettings") as mock_settings_cls:
            mock_settings_cls.return_value = MagicMock()
            await run_pipeline(request, None)
            mock_settings_cls.assert_called_once()

    @pytest.mark.asyncio()
    @patch("ingestion.rag.pipeline.index")
    @patch("ingestion.rag.pipeline.chunk")
    @patch("ingestion.rag.pipeline.ingest_articles", new_callable=AsyncMock)
    @patch("ingestion.rag.pipeline.ingest_filings", new_callable=AsyncMock)
    async def test_show_progress_forwarded(
        self,
        mock_ingest_filings: AsyncMock,
        mock_ingest_articles: AsyncMock,
        mock_chunk: MagicMock,
        mock_index: MagicMock,
        rag_settings: RAGSettings,
    ) -> None:
        mock_ingest_filings.return_value = []
        mock_ingest_articles.return_value = []
        nodes = [TextNode(text="chunk")]
        mock_chunk.return_value = nodes

        request = IngestionRequest(show_progress=True)
        await run_pipeline(request, rag_settings)

        call_kwargs = mock_index.call_args.kwargs
        assert call_kwargs["show_progress"] is True
