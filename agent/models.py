"""Domain models for structured LLM extraction.

These Pydantic models define the schemas that Instructor uses to extract
structured data from natural-language user input and agent analysis.
Field descriptions are sent to the LLM as part of the JSON Schema.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(StrEnum):
    """Risk classification for trade signals."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskAssessment(BaseModel):
    """Result of evaluating a trade signal's risk."""

    model_config = ConfigDict(extra="forbid")

    level: RiskLevel = Field(description="Assessed risk level")
    reasoning: str = Field(description="Explanation of the risk classification")
    requires_approval: bool = Field(
        description="Whether this signal needs human approval before acting"
    )


class AssetMention(BaseModel):
    """A financial asset detected in user text."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(description="Canonical ticker symbol (e.g. AAPL, BTC, NVDA)")
    asset_type: Literal["stock", "crypto"] = Field(
        description="Whether the asset is a stock or cryptocurrency"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the extraction (0.0 to 1.0)",
    )


class IndicatorRequest(BaseModel):
    """A technical indicator action parsed from user input."""

    model_config = ConfigDict(extra="forbid")

    indicator: Literal["ema_8", "ema_80", "sma_200", "rsi_14", "macd", "stochastic"] = Field(
        description="Technical indicator identifier"
    )
    action: Literal["add", "remove", "show"] = Field(
        description="Action to perform with the indicator"
    )


class TradeSignal(BaseModel):
    """A trading signal extracted from agent analysis."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(description="Ticker symbol the signal applies to")
    signal: Literal["bullish", "bearish", "neutral"] = Field(
        description="Overall trading direction signal"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the signal (0.0 to 1.0)",
    )
    reasoning: str = Field(description="Brief explanation of why this signal was generated")
    indicators_used: list[str] = Field(
        description="List of indicator names that contributed to the signal"
    )


class UserIntent(BaseModel):
    """Top-level extraction combining assets, indicators, and query type."""

    model_config = ConfigDict(extra="forbid")

    assets: list[AssetMention] = Field(
        default_factory=list,
        description="Financial assets mentioned in the user query",
    )
    indicators: list[IndicatorRequest] = Field(
        default_factory=list,
        description="Technical indicator actions requested by the user",
    )
    query_type: Literal["price", "indicators", "comparison", "chart", "general"] = Field(
        description="The primary type of query the user is making"
    )
