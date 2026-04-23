"""Massive (Polygon-compatible) API client for market data and indicators."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

from ingestion.schemas import IndicatorValue, MACDValue, OHLCVBar
from py_core.async_utils import AsyncHTTPClient


def _ts_to_date(ms: int) -> date:
    """Convert a Unix-millisecond timestamp to a UTC date."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).date()


def _asset_type(ticker: str) -> str:
    """Determine asset type from ticker format."""
    return "crypto" if ticker.startswith("X:") else "stock"


class MassiveClient:
    """Async client for the Massive market-data API.

    Args:
        http: Initialised ``AsyncHTTPClient`` (caller manages lifecycle).
        api_key: Massive API key (plain string, not SecretStr).
    """

    def __init__(self, http: AsyncHTTPClient, api_key: str) -> None:
        self._http = http
        self._api_key = api_key

    def _params(self, extra: dict[str, str | int] | None = None) -> dict[str, str | int]:
        """Build query params with API key included."""
        params: dict[str, str | int] = {"apiKey": self._api_key}
        if extra:
            params.update(extra)
        return params

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------

    async def fetch_ohlcv(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[OHLCVBar]:
        """Fetch daily OHLCV bars with automatic pagination.

        Args:
            ticker: Symbol (e.g. ``"AAPL"`` or ``"X:BTCUSD"``).
            from_date: Start date (inclusive).
            to_date: End date (inclusive).

        Returns:
            List of ``OHLCVBar`` sorted by date ascending.
        """
        url = f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date.isoformat()}/{to_date.isoformat()}"
        params = self._params({"adjusted": "true", "limit": 50000, "sort": "asc"})

        bars: list[OHLCVBar] = []
        next_url: str | None = url

        while next_url is not None:
            resp = await self._http.get(next_url, params=params)
            data = resp.json()

            for r in data.get("results", []):
                bars.append(
                    OHLCVBar(
                        ticker=ticker,
                        asset_type=_asset_type(ticker),
                        date=_ts_to_date(r["t"]),
                        open=Decimal(str(r["o"])),
                        high=Decimal(str(r["h"])),
                        low=Decimal(str(r["l"])),
                        close=Decimal(str(r["c"])),
                        volume=int(r["v"]),
                        vwap=Decimal(str(r["vw"])) if "vw" in r else None,
                        num_transactions=r.get("n"),
                    )
                )

            next_url = data.get("next_url")
            # After first request, next_url is a full URL with cursor.
            # Keep only apiKey since the URL already has other params.
            params = {"apiKey": self._api_key}

        return bars

    # ------------------------------------------------------------------
    # Single-value indicators (SMA, EMA, RSI)
    # ------------------------------------------------------------------

    async def _fetch_single_indicator(
        self,
        path: str,
        ticker: str,
        extra_params: dict[str, str | int],
    ) -> list[IndicatorValue]:
        """Fetch a single-value indicator (SMA, EMA, or RSI) with pagination."""
        url = f"{path}/{ticker}"
        params = self._params(extra_params)
        all_values: list[IndicatorValue] = []
        next_url: str | None = url

        while next_url is not None:
            resp = await self._http.get(next_url, params=params)
            data = resp.json()

            for v in data.get("results", {}).get("values", []):
                all_values.append(
                    IndicatorValue(
                        timestamp=_ts_to_date(v["timestamp"]),
                        value=Decimal(str(v["value"])),
                    )
                )

            next_url = data.get("next_url")
            params = {"apiKey": self._api_key}

        return all_values

    async def fetch_sma(self, ticker: str, window: int = 200) -> list[IndicatorValue]:
        """Fetch Simple Moving Average values."""
        return await self._fetch_single_indicator(
            "/v1/indicators/sma",
            ticker,
            {"timespan": "day", "window": window, "series_type": "close", "limit": 5000},
        )

    async def fetch_ema(self, ticker: str, window: int = 8) -> list[IndicatorValue]:
        """Fetch Exponential Moving Average values."""
        return await self._fetch_single_indicator(
            "/v1/indicators/ema",
            ticker,
            {"timespan": "day", "window": window, "series_type": "close", "limit": 5000},
        )

    async def fetch_rsi(self, ticker: str, window: int = 14) -> list[IndicatorValue]:
        """Fetch Relative Strength Index values."""
        return await self._fetch_single_indicator(
            "/v1/indicators/rsi",
            ticker,
            {"timespan": "day", "window": window, "series_type": "close", "limit": 5000},
        )

    # ------------------------------------------------------------------
    # MACD
    # ------------------------------------------------------------------

    async def fetch_macd(
        self,
        ticker: str,
        short_window: int = 12,
        long_window: int = 26,
        signal_window: int = 9,
    ) -> list[MACDValue]:
        """Fetch MACD indicator values with pagination."""
        url = f"/v1/indicators/macd/{ticker}"
        params = self._params(
            {
                "timespan": "day",
                "short_window": short_window,
                "long_window": long_window,
                "signal_window": signal_window,
                "series_type": "close",
                "limit": 5000,
            }
        )

        all_values: list[MACDValue] = []
        next_url: str | None = url

        while next_url is not None:
            resp = await self._http.get(next_url, params=params)
            data = resp.json()

            for v in data.get("results", {}).get("values", []):
                all_values.append(
                    MACDValue(
                        timestamp=_ts_to_date(v["timestamp"]),
                        value=Decimal(str(v["value"])),
                        signal=Decimal(str(v["signal"])),
                        histogram=Decimal(str(v["histogram"])),
                    )
                )

            next_url = data.get("next_url")
            params = {"apiKey": self._api_key}

        return all_values

    # ------------------------------------------------------------------
    # All indicators (fetched sequentially with rate-limit delays)
    # ------------------------------------------------------------------

    async def fetch_all_indicators(
        self,
        ticker: str,
        delay: float = 12.0,
    ) -> tuple[
        list[IndicatorValue],  # sma_200
        list[IndicatorValue],  # ema_8
        list[IndicatorValue],  # ema_80
        list[MACDValue],  # macd
        list[IndicatorValue],  # rsi_14
    ]:
        """Fetch all five indicators sequentially with rate-limit delay.

        Args:
            ticker: Symbol to fetch indicators for.
            delay: Seconds to wait between API calls (free tier: 5 req/min).
        """
        sma = await self.fetch_sma(ticker, window=200)
        await asyncio.sleep(delay)
        ema_8 = await self.fetch_ema(ticker, window=8)
        await asyncio.sleep(delay)
        ema_80 = await self.fetch_ema(ticker, window=80)
        await asyncio.sleep(delay)
        macd = await self.fetch_macd(ticker)
        await asyncio.sleep(delay)
        rsi = await self.fetch_rsi(ticker, window=14)
        return (sma, ema_8, ema_80, macd, rsi)
