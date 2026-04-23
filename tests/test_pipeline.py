"""Tests for ingestion pipeline, bronze upserts, and merge logic."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.bronze import upsert_indicators, upsert_market_data
from ingestion.pipeline import (
    DEFAULT_TICKERS,
    IngestionReport,
    TickerResult,
    _merge_indicators,
    run_pipeline,
)
from ingestion.schemas import IndicatorRow, IndicatorValue, MACDValue, OHLCVBar

# --- Fixtures ---


def _bar(day: int = 15, ticker: str = "AAPL") -> OHLCVBar:
    return OHLCVBar(
        ticker=ticker,
        asset_type="stock",
        date=date(2026, 1, day),
        open=Decimal("150"),
        high=Decimal("155"),
        low=Decimal("149"),
        close=Decimal("154"),
        volume=1000,
    )


def _indicator_row(day: int = 15, ticker: str = "AAPL") -> IndicatorRow:
    return IndicatorRow(
        ticker=ticker,
        date=date(2026, 1, day),
        rsi_14=Decimal("65.0"),
    )


# --- Dataclass tests ---


class TestTickerResult:
    def test_defaults(self) -> None:
        r = TickerResult(ticker="AAPL")
        assert r.ohlcv_rows == 0
        assert r.indicator_rows == 0
        assert r.error is None

    def test_with_error(self) -> None:
        r = TickerResult(ticker="AAPL", error="API timeout")
        assert r.error == "API timeout"


class TestIngestionReport:
    def test_succeeded_and_failed_counts(self) -> None:
        report = IngestionReport(
            results=[
                TickerResult(ticker="AAPL", ohlcv_rows=100),
                TickerResult(ticker="MSFT", error="failed"),
                TickerResult(ticker="GOOGL", ohlcv_rows=50),
            ]
        )
        assert report.succeeded == 2
        assert report.failed == 1

    def test_empty_report(self) -> None:
        report = IngestionReport()
        assert report.succeeded == 0
        assert report.failed == 0


# --- Bronze upserts ---


class TestUpsertMarketData:
    @pytest.mark.asyncio()
    async def test_upserts_bars(self) -> None:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute = AsyncMock()

        bars = [_bar(15), _bar(16)]
        count = await upsert_market_data(mock_client, bars)

        assert count == 2
        mock_client.table.assert_called_once_with("market_data_daily")
        mock_table.upsert.assert_called_once()
        args = mock_table.upsert.call_args
        assert args[1]["on_conflict"] == "ticker,date"

    @pytest.mark.asyncio()
    async def test_empty_list_returns_zero(self) -> None:
        mock_client = MagicMock()
        count = await upsert_market_data(mock_client, [])
        assert count == 0
        mock_client.table.assert_not_called()


class TestUpsertIndicators:
    @pytest.mark.asyncio()
    async def test_upserts_indicators(self) -> None:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute = AsyncMock()

        rows = [_indicator_row(15), _indicator_row(16)]
        count = await upsert_indicators(mock_client, rows)

        assert count == 2
        mock_client.table.assert_called_once_with("technical_indicators_daily")

    @pytest.mark.asyncio()
    async def test_empty_list_returns_zero(self) -> None:
        mock_client = MagicMock()
        count = await upsert_indicators(mock_client, [])
        assert count == 0


# --- Merge indicators ---


class TestMergeIndicators:
    def test_merges_all_sources(self) -> None:
        dt = date(2026, 1, 15)
        sma = [IndicatorValue(timestamp=dt, value=Decimal("145"))]
        ema_8 = [IndicatorValue(timestamp=dt, value=Decimal("152"))]
        ema_80 = [IndicatorValue(timestamp=dt, value=Decimal("148"))]
        macd = [
            MACDValue(
                timestamp=dt, value=Decimal("2"), signal=Decimal("1.5"), histogram=Decimal("0.5")
            )
        ]
        rsi = [IndicatorValue(timestamp=dt, value=Decimal("65"))]
        stoch = {dt: (Decimal("75"), Decimal("70"))}

        rows = _merge_indicators("AAPL", sma, ema_8, ema_80, macd, rsi, stoch)

        assert len(rows) == 1
        row = rows[0]
        assert row.ticker == "AAPL"
        assert row.date == dt
        assert row.sma_200 == Decimal("145")
        assert row.ema_8 == Decimal("152")
        assert row.ema_80 == Decimal("148")
        assert row.macd_value == Decimal("2")
        assert row.rsi_14 == Decimal("65")
        assert row.stoch_k == Decimal("75")
        assert row.stoch_d == Decimal("70")

    def test_handles_different_dates(self) -> None:
        """Indicators on different dates produce separate rows."""
        dt1 = date(2026, 1, 15)
        dt2 = date(2026, 1, 16)
        sma = [IndicatorValue(timestamp=dt1, value=Decimal("145"))]
        ema_8 = [IndicatorValue(timestamp=dt2, value=Decimal("152"))]

        rows = _merge_indicators("AAPL", sma, ema_8, [], [], [], {})

        assert len(rows) == 2
        dates = {r.date for r in rows}
        assert dates == {dt1, dt2}

    def test_empty_inputs(self) -> None:
        rows = _merge_indicators("AAPL", [], [], [], [], [], {})
        assert rows == []


# --- run_pipeline ---


class TestRunPipeline:
    @pytest.mark.asyncio()
    async def test_runs_for_single_ticker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "test-key")
        monkeypatch.setenv("INGESTION_MASSIVE_API_KEY", "test-key")

        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute = AsyncMock()

        mock_http = AsyncMock()

        # OHLCV response
        ohlcv_resp = MagicMock()
        ohlcv_resp.json.return_value = {
            "results": [{"t": 1768435200000, "o": 150, "h": 155, "l": 149, "c": 154, "v": 1000}],
        }

        # Indicator response (single value)
        ind_resp = MagicMock()
        ind_resp.json.return_value = {
            "results": {"values": [{"timestamp": 1768435200000, "value": 100.0}]},
        }

        # MACD response
        macd_resp = MagicMock()
        macd_resp.json.return_value = {
            "results": {
                "values": [
                    {"timestamp": 1768435200000, "value": 1.0, "signal": 0.5, "histogram": 0.5}
                ]
            },
        }

        # Order: ohlcv, then sma, ema_8, ema_80, macd, rsi
        mock_http.get.side_effect = [ohlcv_resp, ind_resp, ind_resp, ind_resp, macd_resp, ind_resp]

        with (
            patch(
                "ingestion.supabase_client.create_supabase_client",
                new_callable=AsyncMock,
                return_value=mock_supabase,
            ),
            patch("ingestion.pipeline.AsyncHTTPClient") as MockHTTP,
        ):
            MockHTTP.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            MockHTTP.return_value.__aexit__ = AsyncMock(return_value=None)

            from ingestion.config import IngestionSettings

            settings = IngestionSettings()
            report = await run_pipeline(settings, tickers=["AAPL"])

        assert len(report.results) == 1
        assert report.results[0].ticker == "AAPL"
        assert report.results[0].error is None
        assert report.results[0].ohlcv_rows == 1
        assert report.succeeded == 1
        assert report.failed == 0

    def test_default_tickers_has_10(self) -> None:
        assert len(DEFAULT_TICKERS) == 10
        assert "AAPL" in DEFAULT_TICKERS
        assert "X:BTCUSD" in DEFAULT_TICKERS
