"""Silver-layer chunking for financial documents.

Converts Bronze-layer outputs (EdgarFiling, NewsArticle) into LlamaIndex
TextNodes using SentenceSplitter with metadata preservation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, TextNode

from ingestion.rag.config import RAGSettings
from ingestion.rag.edgar import EdgarFiling
from ingestion.rag.firecrawl_source import NewsArticle

T = TypeVar("T")


def _filing_to_document(filing: EdgarFiling) -> Document:
    """Convert an EdgarFiling into a LlamaIndex Document with SEC metadata."""
    return Document(
        text=filing.text,
        metadata={
            "source": "edgar",
            "ticker": filing.ticker,
            "filing_type": filing.filing_type.value,
            "filed_date": filing.filed_date.isoformat(),
            "company_name": filing.company_name,
            "accession_number": filing.accession_number,
            "filing_url": filing.filing_url,
        },
        excluded_embed_metadata_keys=["accession_number", "filed_date", "filing_url"],
        excluded_llm_metadata_keys=["accession_number", "filing_url"],
    )


def _article_to_document(article: NewsArticle, *, ticker: str = "") -> Document:
    """Convert a NewsArticle into a LlamaIndex Document with news metadata."""
    return Document(
        text=article.text,
        metadata={
            "source": "firecrawl",
            "ticker": ticker,
            "title": article.metadata.title or "",
            "published_date": article.metadata.published_date or "",
            "source_domain": article.metadata.source_domain or "",
            "url": article.metadata.url or "",
        },
        excluded_embed_metadata_keys=["published_date", "url"],
        excluded_llm_metadata_keys=["url"],
    )


def _chunk_documents(
    items: list[T],
    *,
    to_document: Callable[[T], Document],
    settings: RAGSettings,
) -> list[TextNode]:
    """Chunk documents with shared SentenceSplitter settings."""
    if not items:
        return []

    documents = [to_document(item) for item in items]
    splitter = SentenceSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    return cast(list[TextNode], nodes)


def chunk_filings(
    filings: list[EdgarFiling],
    settings: RAGSettings,
) -> list[TextNode]:
    """Chunk SEC filings into TextNodes for vector indexing.

    Args:
        filings: Bronze-layer filing data from EdgarClient.
        settings: RAG pipeline configuration (chunk_size, chunk_overlap).

    Returns:
        List of TextNodes with preserved filing metadata.
    """
    return _chunk_documents(
        filings,
        to_document=_filing_to_document,
        settings=settings,
    )


def chunk_articles(
    articles: list[NewsArticle],
    settings: RAGSettings,
    *,
    ticker: str = "",
) -> list[TextNode]:
    """Chunk news articles into TextNodes for vector indexing.

    Args:
        articles: Bronze-layer article data from FirecrawlNewsSource.
        settings: RAG pipeline configuration (chunk_size, chunk_overlap).
        ticker: Optional ticker to tag on all article chunks for filtering.

    Returns:
        List of TextNodes with preserved article metadata.
    """
    return _chunk_documents(
        articles,
        to_document=lambda article: _article_to_document(article, ticker=ticker),
        settings=settings,
    )
