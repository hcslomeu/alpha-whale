"""Bronze layer: upsert raw market data and indicators into Supabase."""

from supabase import AsyncClient

from ingestion.schemas import IndicatorRow, OHLCVBar


async def upsert_market_data(
    client: AsyncClient,
    bars: list[OHLCVBar],
) -> int:
    """Upsert OHLCV bars into the ``market_data_daily`` table.

    Uses the ``(ticker, date)`` unique constraint for idempotent writes.

    Args:
        client: Authenticated async Supabase client.
        bars: OHLCV bars to upsert.

    Returns:
        Number of rows upserted.
    """
    if not bars:
        return 0

    rows = [bar.model_dump(mode="json") for bar in bars]
    await client.table("market_data_daily").upsert(rows, on_conflict="ticker,date").execute()
    return len(rows)


async def upsert_indicators(
    client: AsyncClient,
    indicators: list[IndicatorRow],
) -> int:
    """Upsert indicator rows into the ``technical_indicators_daily`` table.

    Uses the ``(ticker, date)`` unique constraint for idempotent writes.

    Args:
        client: Authenticated async Supabase client.
        indicators: Indicator rows to upsert.

    Returns:
        Number of rows upserted.
    """
    if not indicators:
        return 0

    rows = [row.model_dump(mode="json") for row in indicators]
    await (
        client.table("technical_indicators_daily").upsert(rows, on_conflict="ticker,date").execute()
    )
    return len(rows)
