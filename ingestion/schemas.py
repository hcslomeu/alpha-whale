"""Pydantic models for market data and technical indicators."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, model_validator


class OHLCVBar(BaseModel):
    """Single day of OHLCV price data from Massive API.

    Maps directly to the ``market_data_daily`` Supabase table.
    """

    ticker: str
    asset_type: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap: Decimal | None = None
    num_transactions: int | None = None


class IndicatorValue(BaseModel):
    """Single-value indicator reading (SMA, EMA, RSI) from Massive API."""

    timestamp: date
    value: Decimal


class MACDValue(BaseModel):
    """MACD indicator reading with three components."""

    timestamp: date
    value: Decimal
    signal: Decimal
    histogram: Decimal


class IndicatorRow(BaseModel):
    """Merged indicator row for the ``technical_indicators_daily`` table.

    Combines all indicator types into one row per ticker per date.
    All numeric fields are rounded to 4 decimal places on creation.
    """

    ticker: str
    date: date
    ema_8: Decimal | None = None
    ema_80: Decimal | None = None
    sma_200: Decimal | None = None
    macd_value: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None
    rsi_14: Decimal | None = None
    stoch_k: Decimal | None = None
    stoch_d: Decimal | None = None

    @model_validator(mode="after")
    def _round_decimals(self) -> "IndicatorRow":
        precision = Decimal("0.0001")
        for field_name in (
            "ema_8",
            "ema_80",
            "sma_200",
            "macd_value",
            "macd_signal",
            "macd_histogram",
            "rsi_14",
            "stoch_k",
            "stoch_d",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, value.quantize(precision))
        return self
