"""Supabase async client factory."""

from supabase import AsyncClient, acreate_client


async def create_supabase_client(url: str, key: str) -> AsyncClient:
    """Create an authenticated async Supabase client.

    Args:
        url: Supabase project URL (e.g. ``https://xxx.supabase.co``).
        key: Supabase service-role or anon key.

    Returns:
        Initialised ``AsyncClient`` ready for queries.
    """
    return await acreate_client(url, key)
