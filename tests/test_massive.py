"""Tests for Massive API client."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

from ingestion.massive import MassiveClient, _asset_type, _ts_to_date

# --- Helpers ---

# Unix ms for 2026-01-15
TS_JAN_15 = 1768435200000
# Unix ms for 2026-01-16
TS_JAN_16 = 1768521600000


def _json_response(data: dict) -> httpx.Response:
    """Build a fake httpx.Response with JSON body."""
    return httpx.Response(status_code=200, json=data)


@pytest.fixture()
def mock_http() -> AsyncMock:
    """AsyncHTTPClient mock with a .get() that returns JSON responses."""
    return AsyncMock()


@pytest.fixture()
def client(mock_http: AsyncMock) -> MassiveClient:
    return MassiveClient(http=mock_http, api_key="test-key")


# --- Helper function tests ---


class TestHelpers:
    def test_ts_to_date(self) -> None:
        assert _ts_to_date(TS_JAN_15) == date(2026, 1, 15)

    def test_asset_type_stock(self) -> None:
        assert _asset_type("AAPL") == "stock"
        assert _asset_type("MSFT") == "stock"

    def test_asset_type_crypto(self) -> None:
        assert _asset_type("X:BTCUSD") == "crypto"
        assert _asset_type("X:ETHUSD") == "crypto"


# --- fetch_ohlcv ---


class TestFetchOHLCV:
    @pytest.mark.asyncio()
    async def test_returns_parsed_bars(self, client: MassiveClient, mock_http: AsyncMock) -> None:
        mock_http.get.return_value = _json_response(
            {
                "results": [
                    {
                        "t": TS_JAN_15,
                        "o": 150.0,
                        "h": 155.0,
                        "l": 149.0,
                        "c": 154.0,
                        "v": 1000000,
                        "vw": 152.5,
                        "n": 5000,
                    },
                ],
            }
        )

        bars = await client.fetch_ohlcv("AAPL", date(2026, 1, 1), date(2026, 1, 31))

        assert len(bars) == 1
        bar = bars[0]
        assert bar.ticker == "AAPL"
        assert bar.asset_type == "stock"
        assert bar.date == date(2026, 1, 15)
        assert bar.close == Decimal("154.0")
        assert bar.vwap == Decimal("152.5")
        assert bar.num_transactions == 5000

    @pytest.mark.asyncio()
    async def test_handles_pagination(self, client: MassiveClient, mock_http: AsyncMock) -> None:
        page_1 = _json_response(
            {
                "results": [{"t": TS_JAN_15, "o": 150, "h": 155, "l": 149, "c": 154, "v": 100}],
                "next_url": "/v2/aggs/next-page",
            }
        )
        page_2 = _json_response(
            {
                "results": [{"t": TS_JAN_16, "o": 154, "h": 158, "l": 153, "c": 157, "v": 200}],
            }
        )
        mock_http.get.side_effect = [page_1, page_2]

        bars = await client.fetch_ohlcv("AAPL", date(2026, 1, 1), date(2026, 1, 31))

        assert len(bars) == 2
        assert bars[0].date == date(2026, 1, 15)
        assert bars[1].date == date(2026, 1, 16)
        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio()
    async def test_empty_results(self, client: MassiveClient, mock_http: AsyncMock) -> None:
        mock_http.get.return_value = _json_response({"results": []})

        bars = await client.fetch_ohlcv("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert bars == []

    @pytest.mark.asyncio()
    async def test_optional_fields_missing(
        self, client: MassiveClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get.return_value = _json_response(
            {
                "results": [{"t": TS_JAN_15, "o": 150, "h": 155, "l": 149, "c": 154, "v": 100}],
            }
        )

        bars = await client.fetch_ohlcv("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        assert bars[0].vwap is None
        assert bars[0].num_transactions is None

    @pytest.mark.asyncio()
    async def test_crypto_ticker(self, client: MassiveClient, mock_http: AsyncMock) -> None:
        mock_http.get.return_value = _json_response(
            {
                "results": [
                    {"t": TS_JAN_15, "o": 97000, "h": 98000, "l": 96000, "c": 97500, "v": 500}
                ],
            }
        )

        bars = await client.fetch_ohlcv("X:BTCUSD", date(2026, 1, 1), date(2026, 1, 31))
        assert bars[0].asset_type == "crypto"
        assert bars[0].ticker == "X:BTCUSD"


# --- Single-value indicators (SMA, EMA, RSI) ---


class TestSingleIndicators:
    @pytest.mark.asyncio()
    async def test_fetch_sma(self, client: MassiveClient, mock_http: AsyncMock) -> None:
        mock_http.get.return_value = _json_response(
            {
                "results": {
                    "values": [
                        {"timestamp": TS_JAN_15, "value": 145.25},
                        {"timestamp": TS_JAN_16, "value": 145.50},
                    ],
                },
            }
        )

        values = await client.fetch_sma("AAPL", window=200)

        assert len(values) == 2
        assert values[0].timestamp == date(2026, 1, 15)
        assert values[0].value == Decimal("145.25")

    @pytest.mark.asyncio()
    async def test_fetch_ema(self, client: MassiveClient, mock_http: AsyncMock) -> None:
        mock_http.get.return_value = _json_response(
            {
                "results": {"values": [{"timestamp": TS_JAN_15, "value": 152.80}]},
            }
        )

        values = await client.fetch_ema("AAPL", window=8)

        assert len(values) == 1
        assert values[0].value == Decimal("152.80")

    @pytest.mark.asyncio()
    async def test_fetch_rsi(self, client: MassiveClient, mock_http: AsyncMock) -> None:
        mock_http.get.return_value = _json_response(
            {
                "results": {"values": [{"timestamp": TS_JAN_15, "value": 65.4}]},
            }
        )

        values = await client.fetch_rsi("AAPL", window=14)

        assert len(values) == 1
        assert values[0].value == Decimal("65.4")

    @pytest.mark.asyncio()
    async def test_empty_indicator_results(
        self, client: MassiveClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get.return_value = _json_response({"results": {"values": []}})

        values = await client.fetch_sma("AAPL")
        assert values == []


# --- MACD ---


class TestFetchMACD:
    @pytest.mark.asyncio()
    async def test_returns_three_components(
        self, client: MassiveClient, mock_http: AsyncMock
    ) -> None:
        mock_http.get.return_value = _json_response(
            {
                "results": {
                    "values": [
                        {
                            "timestamp": TS_JAN_15,
                            "value": 2.35,
                            "signal": 1.80,
                            "histogram": 0.55,
                        },
                    ],
                },
            }
        )

        values = await client.fetch_macd("AAPL")

        assert len(values) == 1
        assert values[0].value == Decimal("2.35")
        assert values[0].signal == Decimal("1.80")
        assert values[0].histogram == Decimal("0.55")


# --- fetch_all_indicators ---


class TestFetchAllIndicators:
    @pytest.mark.asyncio()
    async def test_returns_five_result_lists(
        self, client: MassiveClient, mock_http: AsyncMock
    ) -> None:
        single_resp = _json_response(
            {
                "results": {"values": [{"timestamp": TS_JAN_15, "value": 100.0}]},
            }
        )
        macd_resp = _json_response(
            {
                "results": {
                    "values": [
                        {"timestamp": TS_JAN_15, "value": 1.0, "signal": 0.5, "histogram": 0.5},
                    ],
                },
            }
        )
        # Order: sma, ema_8, ema_80, macd, rsi
        mock_http.get.side_effect = [single_resp, single_resp, single_resp, macd_resp, single_resp]

        # delay=0 skips sleep in tests
        sma, ema_8, ema_80, macd, rsi = await client.fetch_all_indicators("AAPL", delay=0)

        assert len(sma) == 1
        assert len(ema_8) == 1
        assert len(ema_80) == 1
        assert len(macd) == 1
        assert len(rsi) == 1
        assert mock_http.get.call_count == 5
