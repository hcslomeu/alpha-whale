"""Tests for AlphaWhale Supabase-backed agent tools."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.tools import compare_assets, get_stock_price, get_technical_indicators


def _make_supabase_mock(rows: list[dict[str, Any]]) -> MagicMock:
    """Build a mock Supabase sync client returning given rows for any query."""
    result = MagicMock()
    result.data = rows

    builder = MagicMock()
    builder.select.return_value = builder
    builder.eq.return_value = builder
    builder.order.return_value = builder
    builder.limit.return_value = builder
    builder.execute.return_value = result

    client = MagicMock()
    client.table.return_value = builder
    return client


SAMPLE_PRICE_ROWS = [
    {
        "date": "2026-03-12",
        "ticker": "AAPL",
        "open": 178.5,
        "high": 180.2,
        "low": 177.8,
        "close": 179.9,
        "volume": 52_000_000,
    },
    {
        "date": "2026-03-11",
        "ticker": "AAPL",
        "open": 176.0,
        "high": 179.1,
        "low": 175.5,
        "close": 178.5,
        "volume": 48_000_000,
    },
]

SAMPLE_INDICATOR_ROWS = [
    {
        "date": "2026-03-12",
        "ticker": "AAPL",
        "ema_8": 178.12,
        "ema_80": 172.45,
        "sma_200": 165.30,
        "macd_value": 2.15,
        "macd_signal": 1.87,
        "macd_histogram": 0.28,
        "rsi_14": 62.4,
        "stoch_k": 71.2,
        "stoch_d": 68.5,
    },
]


# --- get_stock_price ---


class TestGetStockPrice:
    def test_returns_ticker_and_rows(self):
        mock = _make_supabase_mock(SAMPLE_PRICE_ROWS)
        with patch("agent.tools._get_supabase", return_value=mock):
            result = get_stock_price.invoke({"ticker": "AAPL"})
        assert result["ticker"] == "AAPL"
        assert len(result["rows"]) == 2

    def test_maps_btc_ticker_to_polygon_format(self):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            get_stock_price.invoke({"ticker": "BTC"})
        mock.table.return_value.select.return_value.eq.assert_called_with("ticker", "X:BTCUSD")

    def test_uppercases_ticker(self):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            get_stock_price.invoke({"ticker": "aapl"})
        mock.table.return_value.select.return_value.eq.assert_called_with("ticker", "AAPL")

    def test_empty_result_returns_error(self):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            result = get_stock_price.invoke({"ticker": "UNKNOWN"})
        assert "error" in result

    def test_tool_metadata(self):
        assert get_stock_price.name == "get_stock_price"
        assert "OHLCV" in get_stock_price.description

    def test_custom_days_param(self):
        mock = _make_supabase_mock(SAMPLE_PRICE_ROWS)
        with patch("agent.tools._get_supabase", return_value=mock):
            get_stock_price.invoke({"ticker": "AAPL", "days": 10})
        mock.table.return_value.select.return_value.eq.return_value.order.return_value.limit.assert_called_with(
            10
        )


# --- get_technical_indicators ---


class TestGetTechnicalIndicators:
    def test_returns_ticker_and_rows(self):
        mock = _make_supabase_mock(SAMPLE_INDICATOR_ROWS)
        with patch("agent.tools._get_supabase", return_value=mock):
            result = get_technical_indicators.invoke({"ticker": "AAPL"})
        assert result["ticker"] == "AAPL"
        assert len(result["rows"]) == 1

    def test_row_contains_indicator_fields(self):
        mock = _make_supabase_mock(SAMPLE_INDICATOR_ROWS)
        with patch("agent.tools._get_supabase", return_value=mock):
            result = get_technical_indicators.invoke({"ticker": "AAPL"})
        row = result["rows"][0]
        for field in ("rsi_14", "macd_value", "ema_8", "stoch_k"):
            assert field in row, f"Missing field: {field}"

    def test_maps_eth_ticker(self):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            get_technical_indicators.invoke({"ticker": "ETH"})
        mock.table.return_value.select.return_value.eq.assert_called_with("ticker", "X:ETHUSD")

    def test_empty_result_returns_error(self):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            result = get_technical_indicators.invoke({"ticker": "UNKNOWN"})
        assert "error" in result

    def test_tool_metadata(self):
        assert get_technical_indicators.name == "get_technical_indicators"
        assert "RSI" in get_technical_indicators.description


# --- compare_assets ---


class TestCompareAssets:
    def test_returns_data_for_each_ticker(self):
        mock = _make_supabase_mock([{"date": "2026-03-12", "close": 179.9}])
        with patch("agent.tools._get_supabase", return_value=mock):
            result = compare_assets.invoke({"tickers": ["AAPL", "MSFT"]})
        assert "AAPL" in result["data"]
        assert "MSFT" in result["data"]

    def test_returns_correct_metric_and_days(self):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            result = compare_assets.invoke({"tickers": ["NVDA"], "metric": "volume", "days": 3})
        assert result["metric"] == "volume"
        assert result["days"] == 3

    def test_invalid_metric_returns_error(self):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            result = compare_assets.invoke({"tickers": ["AAPL"], "metric": "invalid"})
        assert "error" in result

    def test_tool_metadata(self):
        assert compare_assets.name == "compare_assets"
        assert "compare" in compare_assets.description.lower()

    @pytest.mark.parametrize(
        "ticker,expected",
        [
            ("BTC", "X:BTCUSD"),
            ("ETH", "X:ETHUSD"),
            ("SOL", "X:SOLUSD"),
            ("AAPL", "AAPL"),
        ],
    )
    def test_ticker_mapping(self, ticker: str, expected: str):
        mock = _make_supabase_mock([])
        with patch("agent.tools._get_supabase", return_value=mock):
            compare_assets.invoke({"tickers": [ticker]})
        mock.table.return_value.select.return_value.eq.assert_called_with("ticker", expected)
