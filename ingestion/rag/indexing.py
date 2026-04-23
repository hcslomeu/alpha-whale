"""Gold-layer indexing for financial documents.

Embeds Silver-layer TextNodes (from chunking) using OpenAI embeddings
and upserts them to a Pinecone vector store via LlamaIndex.
"""

from __future__ import annotations

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone

from ingestion.rag.config import RAGSettings


def build_vector_store(settings: RAGSettings) -> PineconeVectorStore:
    """Create a PineconeVectorStore connected to the configured index."""
    pc = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
    index = pc.Index(settings.pinecone_index_name)
    return PineconeVectorStore(
        pinecone_index=index,
        namespace=settings.pinecone_namespace,
    )


def build_embed_model(settings: RAGSettings) -> OpenAIEmbedding:
    """Create an OpenAI embedding model from RAG settings."""
    return OpenAIEmbedding(
        model=settings.embedding_model,
        api_key=settings.openai_api_key.get_secret_value(),
        dimensions=settings.embedding_dimensions,
    )


def index_nodes(
    nodes: list[TextNode],
    settings: RAGSettings,
    *,
    show_progress: bool = False,
) -> VectorStoreIndex:
    """Embed and upsert TextNodes to Pinecone.

    Args:
        nodes: Silver-layer TextNodes from chunking (Phase 4).
        settings: RAG pipeline configuration.
        show_progress: Display a progress bar during embedding.

    Returns:
        VectorStoreIndex for immediate querying or further retrieval setup.
    """
    vector_store = build_vector_store(settings)
    embed_model = build_embed_model(settings)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex(
        nodes=nodes,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=show_progress,
    )
