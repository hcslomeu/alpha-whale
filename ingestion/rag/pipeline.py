"""End-to-end RAG ingestion pipeline.

Orchestrates the full medallion flow: Bronze (EDGAR + Firecrawl) →
Silver (chunking) → Gold (Pinecone indexing). Provides both a
composable async API and a CLI entry point for batch ingestion.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode

from core import get_logger
from ingestion.rag.chunking import chunk_articles, chunk_filings
from ingestion.rag.config import RAGSettings
from ingestion.rag.edgar import EdgarClient, EdgarFiling, FilingType
from ingestion.rag.firecrawl_source import FirecrawlNewsSource, NewsArticle
from ingestion.rag.indexing import index_nodes

logger = get_logger("rag.pipeline")


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Summary of a pipeline run."""

    filings_fetched: int = 0
    articles_fetched: int = 0
    nodes_chunked: int = 0
    nodes_indexed: int = 0


@dataclass
class IngestionRequest:
    """Parameters for a pipeline run."""

    tickers: list[str] = field(default_factory=list)
    filing_types: list[FilingType] = field(
        default_factory=lambda: [FilingType.TEN_K, FilingType.TEN_Q]
    )
    news_urls: list[str] = field(default_factory=list)
    max_filings_per_query: int = 5
    show_progress: bool = False


async def ingest_filings(
    request: IngestionRequest,
    settings: RAGSettings,
) -> list[EdgarFiling]:
    """Bronze layer — fetch SEC filings for all tickers and filing types."""
    client = EdgarClient(user_agent=settings.edgar_user_agent)
    filings: list[EdgarFiling] = []

    for ticker in request.tickers:
        for filing_type in request.filing_types:
            batch = await client.search_and_fetch(
                ticker,
                filing_type,
                max_results=request.max_filings_per_query,
            )
            filings.extend(batch)
            logger.info(
                "filings_ingested",
                ticker=ticker,
                filing_type=filing_type.value,
                count=len(batch),
            )

    return filings


async def ingest_articles(
    request: IngestionRequest,
    settings: RAGSettings,
) -> list[NewsArticle]:
    """Bronze layer — scrape financial news articles via Firecrawl.

    Firecrawl SDK is synchronous, so scraping runs in a thread to
    avoid blocking the async event loop.
    """
    if not request.news_urls:
        return []

    source = FirecrawlNewsSource(settings=settings)
    articles = await asyncio.to_thread(source.scrape_urls, request.news_urls)
    logger.info("articles_ingested", count=len(articles))
    return articles


def chunk(
    filings: list[EdgarFiling],
    articles: list[NewsArticle],
    settings: RAGSettings,
) -> list[TextNode]:
    """Silver layer — split filings and articles into TextNodes."""
    filing_nodes = chunk_filings(filings, settings)
    article_nodes = chunk_articles(articles, settings)
    all_nodes = filing_nodes + article_nodes
    logger.info(
        "chunking_complete",
        filing_nodes=len(filing_nodes),
        article_nodes=len(article_nodes),
        total=len(all_nodes),
    )
    return all_nodes


def index(
    nodes: list[TextNode],
    settings: RAGSettings,
    *,
    show_progress: bool = False,
) -> VectorStoreIndex:
    """Gold layer — embed and upsert nodes to Pinecone."""
    idx = index_nodes(nodes, settings, show_progress=show_progress)
    logger.info("indexing_complete", nodes_indexed=len(nodes))
    return idx


async def run_pipeline(
    request: IngestionRequest,
    settings: RAGSettings | None = None,
) -> IngestionResult:
    """Execute the full Bronze → Silver → Gold pipeline.

    Args:
        request: Specifies tickers, filing types, and news URLs to ingest.
        settings: RAG configuration. Uses environment defaults if None.

    Returns:
        IngestionResult with counts for each stage.
    """
    settings = settings or RAGSettings()

    # Bronze
    filings = await ingest_filings(request, settings)
    articles = await ingest_articles(request, settings)

    # Silver
    nodes = chunk(filings, articles, settings)

    if not nodes:
        logger.warning("pipeline_empty", reason="no nodes produced from ingestion")
        return IngestionResult(
            filings_fetched=len(filings),
            articles_fetched=len(articles),
        )

    # Gold
    index(nodes, settings, show_progress=request.show_progress)

    result = IngestionResult(
        filings_fetched=len(filings),
        articles_fetched=len(articles),
        nodes_chunked=len(nodes),
        nodes_indexed=len(nodes),
    )
    logger.info(
        "pipeline_complete",
        filings=result.filings_fetched,
        articles=result.articles_fetched,
        nodes=result.nodes_indexed,
    )
    return result


def run_pipeline_sync(
    request: IngestionRequest,
    settings: RAGSettings | None = None,
) -> IngestionResult:
    """Synchronous wrapper for CLI usage."""
    return asyncio.run(run_pipeline(request, settings))
