"""Ingestion pipeline: fetch from Massive API, compute indicators, upsert to Supabase."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from supabase import AsyncClient

from ingestion.bronze import upsert_indicators, upsert_market_data
from ingestion.config import IngestionSettings
from ingestion.massive import MassiveClient
from ingestion.schemas import IndicatorRow, IndicatorValue, MACDValue
from ingestion.stochastic import compute_stochastic
from py_core.async_utils import AsyncHTTPClient
from py_core.logging import get_logger

logger = get_logger("ingestion.pipeline")

# MAG 7 + top crypto
DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "META",
    "NVDA",
    "TSLA",
    "X:BTCUSD",
    "X:ETHUSD",
    "X:SOLUSD",
]


@dataclass
class TickerResult:
    """Outcome of ingesting one ticker."""

    ticker: str
    ohlcv_rows: int = 0
    indicator_rows: int = 0
    error: str | None = None


@dataclass
class IngestionReport:
    """Summary of a full pipeline run."""

    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    results: list[TickerResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.error is None)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.error is not None)


async def _ingest_ticker(
    ticker: str,
    massive: MassiveClient,
    supabase: AsyncClient,
    from_date: date,
    to_date: date,
) -> TickerResult:
    """Run the full ingestion flow for a single ticker."""
    result = TickerResult(ticker=ticker)

    try:
        # Step 1: fetch OHLCV bars
        bars = await massive.fetch_ohlcv(ticker, from_date, to_date)
        result.ohlcv_rows = await upsert_market_data(supabase, bars)
        logger.info("ohlcv_upserted", ticker=ticker, rows=result.ohlcv_rows)

        # Step 2: fetch all indicators concurrently
        sma_200, ema_8, ema_80, macd, rsi = await massive.fetch_all_indicators(ticker)

        # Step 3: compute stochastic from OHLCV bars
        stoch = compute_stochastic(bars)

        # Step 4: merge indicators into rows keyed by date
        indicator_rows = _merge_indicators(ticker, sma_200, ema_8, ema_80, macd, rsi, stoch)
        result.indicator_rows = await upsert_indicators(supabase, indicator_rows)
        logger.info("indicators_upserted", ticker=ticker, rows=result.indicator_rows)

    except Exception as exc:
        result.error = str(exc)
        logger.error("ticker_failed", ticker=ticker, error=str(exc))

    return result


def _merge_indicators(
    ticker: str,
    sma_200: list[IndicatorValue],
    ema_8: list[IndicatorValue],
    ema_80: list[IndicatorValue],
    macd: list[MACDValue],
    rsi: list[IndicatorValue],
    stoch: dict[date, tuple[Decimal, Decimal | None]],
) -> list[IndicatorRow]:
    """Merge all indicator sources into IndicatorRow objects keyed by date."""
    data: dict[date, dict] = {}

    for v in sma_200:
        data.setdefault(v.timestamp, {})["sma_200"] = v.value

    for v in ema_8:
        data.setdefault(v.timestamp, {})["ema_8"] = v.value

    for v in ema_80:
        data.setdefault(v.timestamp, {})["ema_80"] = v.value

    for m in macd:
        entry = data.setdefault(m.timestamp, {})
        entry["macd_value"] = m.value
        entry["macd_signal"] = m.signal
        entry["macd_histogram"] = m.histogram

    for v in rsi:
        data.setdefault(v.timestamp, {})["rsi_14"] = v.value

    for dt, (k, d) in stoch.items():
        entry = data.setdefault(dt, {})
        entry["stoch_k"] = k
        entry["stoch_d"] = d

    return [IndicatorRow(ticker=ticker, date=dt, **fields) for dt, fields in data.items()]


async def run_pipeline(
    settings: IngestionSettings,
    tickers: list[str] | None = None,
    from_date: date = date(2020, 1, 1),
    to_date: date | None = None,
) -> IngestionReport:
    """Run the full ingestion pipeline for all tickers.

    Args:
        settings: Pipeline configuration with API keys and URLs.
        tickers: Override default ticker list (useful for testing).
        from_date: Start date for OHLCV data.
        to_date: End date (defaults to today).

    Returns:
        Report with per-ticker results and timing.
    """
    tickers = tickers or DEFAULT_TICKERS
    to_date = to_date or date.today()
    report = IngestionReport()

    from ingestion.supabase_client import create_supabase_client

    supabase = await create_supabase_client(
        settings.supabase_url,
        settings.supabase_key.get_secret_value(),
    )

    async with AsyncHTTPClient(
        base_url=settings.massive_base_url,
        timeout=60.0,
        max_retries=5,
    ) as http:
        massive = MassiveClient(
            http=http,
            api_key=settings.massive_api_key.get_secret_value(),
        )

        for ticker in tickers:
            logger.info("ingesting_ticker", ticker=ticker)
            result = await _ingest_ticker(ticker, massive, supabase, from_date, to_date)
            report.results.append(result)

    report.finished_at = datetime.now(UTC)
    logger.info(
        "pipeline_complete",
        succeeded=report.succeeded,
        failed=report.failed,
    )
    return report
