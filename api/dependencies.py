"""FastAPI dependency injection providers."""

from typing import Annotated

from fastapi import Depends, Request
from langgraph.graph.state import CompiledStateGraph
from supabase import AsyncClient

from api.config import APISettings
from core import AsyncRedisClient


def get_supabase(request: Request) -> AsyncClient:
    """Retrieve the shared Supabase client from app state."""
    client: AsyncClient = request.app.state.supabase
    return client


def get_settings(request: Request) -> APISettings:
    """Retrieve shared settings from app state."""
    settings: APISettings = request.app.state.settings
    return settings


def get_redis_client(request: Request) -> AsyncRedisClient | None:
    """Retrieve the shared Redis client from app state (None if caching disabled)."""
    client: AsyncRedisClient | None = request.app.state.redis_client
    return client


def get_graph() -> CompiledStateGraph:
    """Return the compiled LangGraph agent (with MemorySaver checkpointer)."""
    from agent.graph import app as agent_app

    graph: CompiledStateGraph = agent_app
    return graph


# Type aliases for cleaner route signatures
SupabaseDep = Annotated[AsyncClient, Depends(get_supabase)]
GraphDep = Annotated[CompiledStateGraph, Depends(get_graph)]
SettingsDep = Annotated[APISettings, Depends(get_settings)]
RedisClientDep = Annotated[AsyncRedisClient | None, Depends(get_redis_client)]
