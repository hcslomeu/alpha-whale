"""RAG pipeline for financial document retrieval (WP-121).

Bronze → Silver → Gold Medallion pipeline:
- Bronze: EDGAR 10-K/10-Q filings + Firecrawl news ingestion
- Silver: SentenceSplitter chunking with financial metadata
- Gold: OpenAI embeddings indexed in Pinecone
- Retrieval: BM25 + Vector hybrid search with Cohere reranking
"""

from ingestion.rag.chunking import chunk_articles, chunk_filings
from ingestion.rag.config import RAGSettings
from ingestion.rag.edgar import EdgarClient, EdgarFiling, EdgarSearchResult, FilingType
from ingestion.rag.firecrawl_source import FirecrawlNewsSource, NewsArticle, NewsArticleMetadata
from ingestion.rag.indexing import build_embed_model, build_vector_store, index_nodes
from ingestion.rag.pipeline import (
    IngestionRequest,
    IngestionResult,
    run_pipeline,
    run_pipeline_sync,
)
from ingestion.rag.retrieval import build_hybrid_retriever, build_reranker, retrieve_and_rerank

__all__ = [
    "EdgarClient",
    "EdgarFiling",
    "EdgarSearchResult",
    "FilingType",
    "FirecrawlNewsSource",
    "IngestionRequest",
    "IngestionResult",
    "NewsArticle",
    "NewsArticleMetadata",
    "RAGSettings",
    "build_embed_model",
    "build_hybrid_retriever",
    "build_reranker",
    "build_vector_store",
    "chunk_articles",
    "chunk_filings",
    "index_nodes",
    "retrieve_and_rerank",
    "run_pipeline",
    "run_pipeline_sync",
]
