"""Hybrid retrieval with BM25 + Vector fusion and Cohere reranking.

Combines keyword-based BM25 retrieval with semantic vector search via
QueryFusionRetriever (Reciprocal Rank Fusion), then applies CohereRerank
as a postprocessor for final result quality.
"""

from __future__ import annotations

from collections.abc import Sequence

from llama_index.core import VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever, VectorIndexRetriever
from llama_index.core.retrievers.fusion_retriever import FUSION_MODES
from llama_index.core.schema import BaseNode, NodeWithScore
from llama_index.postprocessor.cohere_rerank import CohereRerank
from llama_index.retrievers.bm25 import BM25Retriever

from ingestion.rag.config import RAGSettings


def build_hybrid_retriever(
    index: VectorStoreIndex,
    nodes: Sequence[BaseNode],
    settings: RAGSettings,
) -> QueryFusionRetriever:
    """Build a hybrid retriever combining BM25 keyword and vector semantic search.

    Args:
        index: Gold-layer VectorStoreIndex (from Phase 5 indexing).
        nodes: Silver-layer TextNodes (from Phase 4 chunking) for BM25.
        settings: RAG pipeline configuration.

    Returns:
        QueryFusionRetriever using Reciprocal Rank Fusion.
    """
    vector_retriever = VectorIndexRetriever(
        index=index,
        similarity_top_k=settings.similarity_top_k,
    )
    bm25_retriever = BM25Retriever.from_defaults(
        nodes=list(nodes),
        similarity_top_k=settings.similarity_top_k,
    )
    return QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        mode=FUSION_MODES.RECIPROCAL_RANK,
        similarity_top_k=settings.similarity_top_k,
        num_queries=1,
        use_async=False,
    )


def build_reranker(settings: RAGSettings) -> CohereRerank:
    """Build a Cohere reranker postprocessor."""
    return CohereRerank(
        model=settings.cohere_rerank_model,
        top_n=settings.rerank_top_n,
        api_key=settings.cohere_api_key.get_secret_value(),
    )


def retrieve_and_rerank(
    query: str,
    retriever: QueryFusionRetriever,
    reranker: CohereRerank,
) -> list[NodeWithScore]:
    """Execute hybrid retrieval followed by reranking.

    Args:
        query: User search query.
        retriever: Pre-built hybrid retriever from build_hybrid_retriever().
        reranker: Pre-built Cohere reranker from build_reranker().

    Returns:
        Reranked list of NodeWithScore, ordered by relevance.
    """
    fused_nodes = retriever.retrieve(query)
    if not fused_nodes:
        return []
    return reranker.postprocess_nodes(fused_nodes, query_str=query)
