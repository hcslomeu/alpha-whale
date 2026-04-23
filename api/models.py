"""Request and response schemas for the AlphaWhale API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST body for /chat/stream."""

    message: str = Field(..., min_length=1, max_length=2000)
    thread_id: str | None = Field(
        default=None,
        description="Conversation thread ID. Auto-generated if not provided.",
    )


class ApprovalRequest(BaseModel):
    """POST body for /chat/approve."""

    thread_id: str = Field(..., description="Thread ID of the paused conversation.")
    approved: bool = Field(..., description="Whether the trade signal is approved.")


class ChatStreamEvent(BaseModel):
    """Shape of a single SSE event (for documentation/typing)."""

    event: str = "message"
    data: str


class MarketDataResponse(BaseModel):
    """Daily OHLCV data for a ticker (stock or crypto)."""

    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class IndicatorDataResponse(BaseModel):
    """Daily technical indicators for a ticker."""

    ticker: str
    date: str
    ema_8: float | None = None
    ema_80: float | None = None
    sma_200: float | None = None
    macd_value: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    rsi_14: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None


class HealthCheck(BaseModel):
    """Individual service check result."""

    status: str
    detail: str = ""


class HealthResponse(BaseModel):
    """Response from /health."""

    status: str = "ok"
    checks: dict[str, HealthCheck] = {}
