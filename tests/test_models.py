"""Tests for AlphaWhale agent extraction models."""

import pytest
from pydantic import ValidationError

from agent.models import (
    AssetMention,
    IndicatorRequest,
    RiskAssessment,
    RiskLevel,
    TradeSignal,
    UserIntent,
)

# ---------------------------------------------------------------------------
# TestAssetMention
# ---------------------------------------------------------------------------


class TestAssetMention:
    """Tests for the AssetMention model."""

    def test_valid_stock(self):
        """Accepts a valid stock mention."""
        mention = AssetMention(ticker="AAPL", asset_type="stock", confidence=0.95)
        assert mention.ticker == "AAPL"
        assert mention.asset_type == "stock"
        assert mention.confidence == 0.95

    def test_valid_crypto(self):
        """Accepts a valid crypto mention."""
        mention = AssetMention(ticker="BTC", asset_type="crypto", confidence=0.8)
        assert mention.asset_type == "crypto"

    def test_rejects_invalid_confidence(self):
        """Rejects confidence outside 0.0-1.0."""
        with pytest.raises(ValidationError):
            AssetMention(ticker="AAPL", asset_type="stock", confidence=1.5)

    def test_rejects_invalid_asset_type(self):
        """Rejects asset types not in the Literal."""
        with pytest.raises(ValidationError):
            AssetMention(ticker="AAPL", asset_type="forex", confidence=0.5)


# ---------------------------------------------------------------------------
# TestIndicatorRequest
# ---------------------------------------------------------------------------


class TestIndicatorRequest:
    """Tests for the IndicatorRequest model."""

    def test_valid_indicator(self):
        """Accepts a valid indicator request."""
        req = IndicatorRequest(indicator="rsi_14", action="show")
        assert req.indicator == "rsi_14"
        assert req.action == "show"

    def test_all_valid_actions(self):
        """Accepts all valid action literals."""
        for action in ("add", "remove", "show"):
            req = IndicatorRequest(indicator="ema_8", action=action)
            assert req.action == action

    def test_rejects_invalid_indicator(self):
        """Rejects indicator names not in the Literal."""
        with pytest.raises(ValidationError):
            IndicatorRequest(indicator="bollinger", action="add")


# ---------------------------------------------------------------------------
# TestTradeSignal
# ---------------------------------------------------------------------------


class TestTradeSignal:
    """Tests for the TradeSignal model."""

    def test_valid_signal(self):
        """Accepts a complete valid trade signal."""
        signal = TradeSignal(
            ticker="NVDA",
            signal="bullish",
            confidence=0.85,
            reasoning="RSI oversold + EMA crossover",
            indicators_used=["rsi_14", "ema_8"],
        )
        assert signal.ticker == "NVDA"
        assert signal.signal == "bullish"
        assert signal.indicators_used == ["rsi_14", "ema_8"]

    def test_rejects_confidence_below_zero(self):
        """Rejects negative confidence."""
        with pytest.raises(ValidationError):
            TradeSignal(
                ticker="AAPL",
                signal="neutral",
                confidence=-0.1,
                reasoning="test",
                indicators_used=[],
            )

    def test_rejects_confidence_above_one(self):
        """Rejects confidence greater than 1.0."""
        with pytest.raises(ValidationError):
            TradeSignal(
                ticker="AAPL",
                signal="neutral",
                confidence=1.1,
                reasoning="test",
                indicators_used=[],
            )

    def test_rejects_invalid_signal(self):
        """Rejects signal values not in the Literal."""
        with pytest.raises(ValidationError):
            TradeSignal(
                ticker="AAPL",
                signal="strong_buy",
                confidence=0.5,
                reasoning="test",
                indicators_used=[],
            )


# ---------------------------------------------------------------------------
# TestUserIntent
# ---------------------------------------------------------------------------


class TestUserIntent:
    """Tests for the UserIntent model."""

    def test_combines_assets_and_indicators(self):
        """Accepts a full intent with assets and indicators."""
        intent = UserIntent(
            assets=[
                AssetMention(ticker="AAPL", asset_type="stock", confidence=0.9),
                AssetMention(ticker="BTC", asset_type="crypto", confidence=0.85),
            ],
            indicators=[
                IndicatorRequest(indicator="rsi_14", action="show"),
            ],
            query_type="indicators",
        )
        assert len(intent.assets) == 2
        assert len(intent.indicators) == 1
        assert intent.query_type == "indicators"

    def test_empty_assets_and_indicators(self):
        """Accepts an intent with no assets or indicators (general query)."""
        intent = UserIntent(query_type="general")
        assert intent.assets == []
        assert intent.indicators == []

    def test_rejects_invalid_query_type(self):
        """Rejects query types not in the Literal."""
        with pytest.raises(ValidationError):
            UserIntent(query_type="sentiment")


# ---------------------------------------------------------------------------
# TestRiskLevel
# ---------------------------------------------------------------------------


class TestRiskLevel:
    """Tests for the RiskLevel enum."""

    def test_values(self):
        """Enum has exactly three levels."""
        assert set(RiskLevel) == {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH}

    def test_string_comparison(self):
        """Enum values compare equal to their string representation."""
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.LOW == "low"

    def test_serialises_to_string(self):
        """StrEnum serialises directly to its value string."""
        assert str(RiskLevel.MEDIUM) == "medium"
        assert RiskLevel.MEDIUM.value == "medium"


# ---------------------------------------------------------------------------
# TestRiskAssessment
# ---------------------------------------------------------------------------


class TestRiskAssessment:
    """Tests for the RiskAssessment model."""

    def test_valid_assessment(self):
        """Accepts a complete valid risk assessment."""
        assessment = RiskAssessment(
            level=RiskLevel.HIGH,
            reasoning="Confidence 0.9 on bullish signal",
            requires_approval=True,
        )
        assert assessment.level == RiskLevel.HIGH
        assert assessment.requires_approval is True

    def test_accepts_string_level(self):
        """Accepts raw string that matches enum value."""
        assessment = RiskAssessment(
            level="low",
            reasoning="Low confidence neutral signal",
            requires_approval=False,
        )
        assert assessment.level == RiskLevel.LOW

    def test_rejects_invalid_level(self):
        """Rejects risk levels not in the enum."""
        with pytest.raises(ValidationError):
            RiskAssessment(
                level="critical",
                reasoning="test",
                requires_approval=True,
            )

    def test_rejects_extra_fields(self):
        """extra='forbid' rejects unknown fields."""
        with pytest.raises(ValidationError):
            RiskAssessment(
                level="high",
                reasoning="test",
                requires_approval=True,
                severity=10,
            )
