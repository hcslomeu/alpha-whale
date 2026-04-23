"""Tests for Silver-layer chunking (ingestion.rag.chunking)."""

from datetime import date

import pytest
from llama_index.core.schema import MetadataMode, TextNode

from ingestion.rag.chunking import (
    _article_to_document,
    _filing_to_document,
    chunk_articles,
    chunk_filings,
)
from ingestion.rag.config import RAGSettings
from ingestion.rag.edgar import EdgarFiling, FilingType
from ingestion.rag.firecrawl_source import NewsArticle, NewsArticleMetadata

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
        chunk_size=1024,
        chunk_overlap=200,
    )


@pytest.fixture()
def small_chunk_settings() -> RAGSettings:
    """Settings with small chunk size to force multiple chunks."""
    return RAGSettings(
        pinecone_api_key="test-pinecone",
        openai_api_key="test-openai",
        cohere_api_key="test-cohere",
        firecrawl_api_key="test-firecrawl",
        edgar_user_agent="TestApp test@example.com",
        chunk_size=128,
        chunk_overlap=20,
    )


@pytest.fixture()
def sample_filing() -> EdgarFiling:
    return EdgarFiling(
        accession_number="0000320193-24-000081",
        ticker="AAPL",
        filing_type=FilingType.TEN_K,
        filed_date=date(2024, 11, 1),
        company_name="Apple Inc",
        filing_url="https://www.sec.gov/Archives/edgar/data/320193/filing.htm",
        text="Apple Inc reported total revenue of 394 billion dollars. "
        "The company continued to invest in research and development. "
        "Operating expenses increased year over year due to new product launches.",
    )


@pytest.fixture()
def sample_article() -> NewsArticle:
    return NewsArticle(
        text="Federal Reserve raised interest rates by 25 basis points. "
        "Market analysts expect further tightening in the coming months. "
        "Bond yields surged following the announcement.",
        metadata=NewsArticleMetadata(
            title="Fed Raises Rates Again",
            published_date="2024-12-15",
            source_domain="reuters.com",
            url="https://reuters.com/fed-rates-2024",
        ),
    )


def _long_text(sentences: int = 50) -> str:
    """Generate text long enough to produce multiple chunks."""
    base = (
        "The company reported strong quarterly earnings driven by cloud services growth. "
        "Revenue increased by fifteen percent compared to the same period last year. "
    )
    return base * sentences


# ---------------------------------------------------------------------------
# Document conversion tests
# ---------------------------------------------------------------------------


class TestFilingToDocument:
    def test_text_preserved(self, sample_filing: EdgarFiling) -> None:
        doc = _filing_to_document(sample_filing)
        assert doc.text == sample_filing.text

    def test_metadata_keys(self, sample_filing: EdgarFiling) -> None:
        doc = _filing_to_document(sample_filing)
        expected_keys = {
            "source",
            "ticker",
            "filing_type",
            "filed_date",
            "company_name",
            "accession_number",
            "filing_url",
        }
        assert set(doc.metadata.keys()) == expected_keys

    def test_metadata_values(self, sample_filing: EdgarFiling) -> None:
        doc = _filing_to_document(sample_filing)
        assert doc.metadata["source"] == "edgar"
        assert doc.metadata["ticker"] == "AAPL"
        assert doc.metadata["filing_type"] == "10-K"
        assert doc.metadata["filed_date"] == "2024-11-01"
        assert doc.metadata["company_name"] == "Apple Inc"
        assert doc.metadata["accession_number"] == "0000320193-24-000081"
        assert doc.metadata["filing_url"] == sample_filing.filing_url

    def test_embed_excludes_technical_keys(self, sample_filing: EdgarFiling) -> None:
        doc = _filing_to_document(sample_filing)
        embed_content = doc.get_content(metadata_mode=MetadataMode.EMBED)
        assert "accession_number" not in embed_content
        assert "filed_date" not in embed_content
        assert "filing_url" not in embed_content

    def test_embed_includes_semantic_keys(self, sample_filing: EdgarFiling) -> None:
        doc = _filing_to_document(sample_filing)
        embed_content = doc.get_content(metadata_mode=MetadataMode.EMBED)
        assert "ticker: AAPL" in embed_content
        assert "filing_type: 10-K" in embed_content
        assert "company_name: Apple Inc" in embed_content
        assert "source: edgar" in embed_content

    def test_llm_includes_filed_date(self, sample_filing: EdgarFiling) -> None:
        doc = _filing_to_document(sample_filing)
        llm_content = doc.get_content(metadata_mode=MetadataMode.LLM)
        assert "filed_date: 2024-11-01" in llm_content

    def test_llm_excludes_technical_ids(self, sample_filing: EdgarFiling) -> None:
        doc = _filing_to_document(sample_filing)
        llm_content = doc.get_content(metadata_mode=MetadataMode.LLM)
        assert "accession_number" not in llm_content
        assert "filing_url" not in llm_content


class TestArticleToDocument:
    def test_text_preserved(self, sample_article: NewsArticle) -> None:
        doc = _article_to_document(sample_article)
        assert doc.text == sample_article.text

    def test_metadata_keys(self, sample_article: NewsArticle) -> None:
        doc = _article_to_document(sample_article)
        expected_keys = {"source", "ticker", "title", "published_date", "source_domain", "url"}
        assert set(doc.metadata.keys()) == expected_keys

    def test_metadata_values(self, sample_article: NewsArticle) -> None:
        doc = _article_to_document(sample_article)
        assert doc.metadata["source"] == "firecrawl"
        assert doc.metadata["title"] == "Fed Raises Rates Again"
        assert doc.metadata["published_date"] == "2024-12-15"
        assert doc.metadata["source_domain"] == "reuters.com"
        assert doc.metadata["url"] == "https://reuters.com/fed-rates-2024"

    def test_embed_excludes_date_and_url(self, sample_article: NewsArticle) -> None:
        doc = _article_to_document(sample_article)
        embed_content = doc.get_content(metadata_mode=MetadataMode.EMBED)
        assert "published_date" not in embed_content
        assert "reuters.com/fed-rates" not in embed_content

    def test_embed_includes_semantic_keys(self, sample_article: NewsArticle) -> None:
        doc = _article_to_document(sample_article)
        embed_content = doc.get_content(metadata_mode=MetadataMode.EMBED)
        assert "title: Fed Raises Rates Again" in embed_content
        assert "source_domain: reuters.com" in embed_content
        assert "source: firecrawl" in embed_content

    def test_llm_includes_published_date(self, sample_article: NewsArticle) -> None:
        doc = _article_to_document(sample_article)
        llm_content = doc.get_content(metadata_mode=MetadataMode.LLM)
        assert "published_date: 2024-12-15" in llm_content

    def test_llm_excludes_url(self, sample_article: NewsArticle) -> None:
        doc = _article_to_document(sample_article)
        llm_content = doc.get_content(metadata_mode=MetadataMode.LLM)
        assert "reuters.com/fed-rates" not in llm_content

    def test_none_metadata_defaults_to_empty(self) -> None:
        article = NewsArticle(
            text="Some content",
            metadata=NewsArticleMetadata(
                title=None,
                published_date=None,
                source_domain=None,
                url=None,
            ),
        )
        doc = _article_to_document(article)
        assert doc.metadata["title"] == ""
        assert doc.metadata["published_date"] == ""
        assert doc.metadata["source_domain"] == ""
        assert doc.metadata["url"] == ""


# ---------------------------------------------------------------------------
# Chunking function tests
# ---------------------------------------------------------------------------


class TestChunkFilings:
    def test_empty_input(self, rag_settings: RAGSettings) -> None:
        assert chunk_filings([], rag_settings) == []

    def test_short_filing_single_chunk(
        self, sample_filing: EdgarFiling, rag_settings: RAGSettings
    ) -> None:
        nodes = chunk_filings([sample_filing], rag_settings)
        assert len(nodes) == 1
        assert isinstance(nodes[0], TextNode)

    def test_metadata_preserved_through_chunking(
        self, sample_filing: EdgarFiling, rag_settings: RAGSettings
    ) -> None:
        nodes = chunk_filings([sample_filing], rag_settings)
        node = nodes[0]
        assert node.metadata["source"] == "edgar"
        assert node.metadata["ticker"] == "AAPL"
        assert node.metadata["filing_type"] == "10-K"
        assert node.metadata["company_name"] == "Apple Inc"
        assert node.metadata["accession_number"] == "0000320193-24-000081"
        assert node.metadata["filing_url"] == sample_filing.filing_url

    def test_exclusion_keys_preserved_through_chunking(
        self, sample_filing: EdgarFiling, rag_settings: RAGSettings
    ) -> None:
        nodes = chunk_filings([sample_filing], rag_settings)
        node = nodes[0]
        assert "accession_number" in node.excluded_embed_metadata_keys
        assert "filed_date" in node.excluded_embed_metadata_keys
        assert "filing_url" in node.excluded_embed_metadata_keys

    def test_long_filing_produces_multiple_chunks(self, small_chunk_settings: RAGSettings) -> None:
        filing = EdgarFiling(
            accession_number="0000320193-24-000081",
            ticker="AAPL",
            filing_type=FilingType.TEN_K,
            filed_date=date(2024, 11, 1),
            company_name="Apple Inc",
            filing_url="https://www.sec.gov/Archives/filing.htm",
            text=_long_text(50),
        )
        nodes = chunk_filings([filing], small_chunk_settings)
        assert len(nodes) > 1
        for node in nodes:
            assert node.metadata["ticker"] == "AAPL"
            assert node.metadata["source"] == "edgar"

    def test_multiple_filings_chunked_together(self, rag_settings: RAGSettings) -> None:
        filings = [
            EdgarFiling(
                accession_number=f"acc-{i}",
                ticker=ticker,
                filing_type=FilingType.TEN_K,
                filed_date=date(2024, 1, 1),
                company_name=f"Company {ticker}",
                filing_url=f"https://sec.gov/{i}",
                text=f"Financial report for {ticker}.",
            )
            for i, ticker in enumerate(["AAPL", "MSFT", "GOOGL"])
        ]
        nodes = chunk_filings(filings, rag_settings)
        tickers = {n.metadata["ticker"] for n in nodes}
        assert tickers == {"AAPL", "MSFT", "GOOGL"}


class TestChunkArticles:
    def test_empty_input(self, rag_settings: RAGSettings) -> None:
        assert chunk_articles([], rag_settings) == []

    def test_short_article_single_chunk(
        self, sample_article: NewsArticle, rag_settings: RAGSettings
    ) -> None:
        nodes = chunk_articles([sample_article], rag_settings)
        assert len(nodes) == 1
        assert isinstance(nodes[0], TextNode)

    def test_metadata_preserved_through_chunking(
        self, sample_article: NewsArticle, rag_settings: RAGSettings
    ) -> None:
        nodes = chunk_articles([sample_article], rag_settings)
        node = nodes[0]
        assert node.metadata["source"] == "firecrawl"
        assert node.metadata["title"] == "Fed Raises Rates Again"
        assert node.metadata["published_date"] == "2024-12-15"
        assert node.metadata["source_domain"] == "reuters.com"
        assert node.metadata["url"] == "https://reuters.com/fed-rates-2024"

    def test_exclusion_keys_preserved_through_chunking(
        self, sample_article: NewsArticle, rag_settings: RAGSettings
    ) -> None:
        nodes = chunk_articles([sample_article], rag_settings)
        node = nodes[0]
        assert "published_date" in node.excluded_embed_metadata_keys
        assert "url" in node.excluded_embed_metadata_keys

    def test_long_article_produces_multiple_chunks(self, small_chunk_settings: RAGSettings) -> None:
        article = NewsArticle(
            text=_long_text(50),
            metadata=NewsArticleMetadata(
                title="Market Report",
                published_date="2024-12-15",
                source_domain="reuters.com",
                url="https://reuters.com/report",
            ),
        )
        nodes = chunk_articles([article], small_chunk_settings)
        assert len(nodes) > 1
        for node in nodes:
            assert node.metadata["source"] == "firecrawl"
            assert node.metadata["title"] == "Market Report"

    def test_overlap_produces_expected_node_count(
        self,
    ) -> None:
        """More overlap should produce more chunks for the same text."""
        text = _long_text(30)
        article = NewsArticle(
            text=text,
            metadata=NewsArticleMetadata(
                title="Test",
                published_date=None,
                source_domain=None,
                url=None,
            ),
        )
        no_overlap = RAGSettings(
            pinecone_api_key="k",
            openai_api_key="k",
            cohere_api_key="k",
            firecrawl_api_key="k",
            edgar_user_agent="Test test@test.com",
            chunk_size=128,
            chunk_overlap=0,
        )
        with_overlap = RAGSettings(
            pinecone_api_key="k",
            openai_api_key="k",
            cohere_api_key="k",
            firecrawl_api_key="k",
            edgar_user_agent="Test test@test.com",
            chunk_size=128,
            chunk_overlap=40,
        )
        nodes_no_overlap = chunk_articles([article], no_overlap)
        nodes_with_overlap = chunk_articles([article], with_overlap)
        assert len(nodes_with_overlap) >= len(nodes_no_overlap)
