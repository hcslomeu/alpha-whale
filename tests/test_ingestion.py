"""Tests for AlphaWhale ingestion schemas and configuration."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ingestion.config import IngestionSettings
from ingestion.schemas import IndicatorRow, MACDValue, OHLCVBar

# --- Fixtures ---


@pytest.fixture()
def settings(monkeypatch: pytest.MonkeyPatch) -> IngestionSettings:
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-supabase-key")
    monkeypatch.setenv("INGESTION_MASSIVE_API_KEY", "test-massive-key")
    return IngestionSettings()


# --- IngestionSettings ---


class TestIngestionSettings:
    def test_loads_from_env(self, settings: IngestionSettings) -> None:
        assert settings.supabase_url == "https://test.supabase.co"
        assert settings.supabase_key.get_secret_value() == "test-supabase-key"
        assert settings.massive_api_key.get_secret_value() == "test-massive-key"

    def test_default_base_url(self, settings: IngestionSettings) -> None:
        assert settings.massive_base_url == "https://api.polygon.io"

    def test_missing_required_field_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_KEY", raising=False)
        monkeypatch.delenv("INGESTION_MASSIVE_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            IngestionSettings()

    def test_secret_str_hides_value(self, settings: IngestionSettings) -> None:
        assert "test-supabase-key" not in repr(settings)
        assert "test-massive-key" not in repr(settings)


# --- OHLCVBar ---


class TestOHLCVBar:
    def test_creates_with_required_fields(self) -> None:
        bar = OHLCVBar(
            ticker="AAPL",
            asset_type="stock",
            date=date(2026, 3, 12),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.50"),
            close=Decimal("154.00"),
            volume=1_000_000,
        )
        assert bar.ticker == "AAPL"
        assert bar.close == Decimal("154.00")
        assert bar.vwap is None
        assert bar.num_transactions is None

    def test_optional_fields(self) -> None:
        bar = OHLCVBar(
            ticker="X:BTCUSD",
            asset_type="crypto",
            date=date(2026, 3, 12),
            open=Decimal("97000.00"),
            high=Decimal("98000.00"),
            low=Decimal("96500.00"),
            close=Decimal("97800.00"),
            volume=12345,
            vwap=Decimal("97400.50"),
            num_transactions=5000,
        )
        assert bar.vwap == Decimal("97400.50")
        assert bar.num_transactions == 5000

    def test_rejects_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            OHLCVBar(ticker="AAPL", asset_type="stock", date=date(2026, 3, 12))


# --- IndicatorRow ---


class TestIndicatorRow:
    def test_all_optional_indicators(self) -> None:
        row = IndicatorRow(ticker="AAPL", date=date(2026, 3, 12))
        assert row.ema_8 is None
        assert row.rsi_14 is None
        assert row.stoch_k is None

    def test_partial_indicators(self) -> None:
        row = IndicatorRow(
            ticker="AAPL",
            date=date(2026, 3, 12),
            rsi_14=Decimal("65.4"),
            macd_value=Decimal("2.35"),
            macd_signal=Decimal("1.80"),
            macd_histogram=Decimal("0.55"),
        )
        assert row.rsi_14 == Decimal("65.4")
        assert row.sma_200 is None


# --- MACDValue ---


class TestMACDValue:
    def test_creates_with_all_fields(self) -> None:
        macd = MACDValue(
            timestamp=date(2026, 3, 12),
            value=Decimal("2.35"),
            signal=Decimal("1.80"),
            histogram=Decimal("0.55"),
        )
        assert macd.histogram == Decimal("0.55")

    def test_rejects_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            MACDValue(timestamp=date(2026, 3, 12), value=Decimal("2.35"))
