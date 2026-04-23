"""Tests for Stochastic Oscillator computation."""

from datetime import date, timedelta
from decimal import Decimal

from ingestion.schemas import OHLCVBar
from ingestion.stochastic import D_PERIOD, K_PERIOD, compute_stochastic


def _make_bar(day_offset: int, high: str, low: str, close: str) -> OHLCVBar:
    """Build a minimal OHLCVBar for testing."""
    return OHLCVBar(
        ticker="AAPL",
        asset_type="stock",
        date=date(2026, 1, 1) + timedelta(days=day_offset),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=100,
    )


class TestComputeStochastic:
    def test_fewer_bars_than_k_period_returns_empty(self) -> None:
        bars = [_make_bar(i, "110", "90", "100") for i in range(K_PERIOD - 1)]
        assert compute_stochastic(bars) == {}

    def test_exact_k_period_bars_produces_one_entry(self) -> None:
        bars = [_make_bar(i, "110", "90", "100") for i in range(K_PERIOD)]
        result = compute_stochastic(bars)
        assert len(result) == 1

    def test_k_value_with_known_numbers(self) -> None:
        """14 bars where high=200, low=100, close=150 → %K = 50."""
        bars = [_make_bar(i, "200", "100", "150") for i in range(K_PERIOD)]
        result = compute_stochastic(bars)

        dt = bars[-1].date
        k, d = result[dt]
        assert k == Decimal(50)
        assert d is None  # only 1 %K value, need 3 for %D

    def test_k_value_at_high_boundary(self) -> None:
        """Close equals highest high → %K = 100."""
        bars = [_make_bar(i, "200", "100", "200") for i in range(K_PERIOD)]
        result = compute_stochastic(bars)

        k, _ = result[bars[-1].date]
        assert k == Decimal(100)

    def test_k_value_at_low_boundary(self) -> None:
        """Close equals lowest low → %K = 0."""
        bars = [_make_bar(i, "200", "100", "100") for i in range(K_PERIOD)]
        result = compute_stochastic(bars)

        k, _ = result[bars[-1].date]
        assert k == Decimal(0)

    def test_flat_market_returns_50(self) -> None:
        """All prices identical (spread = 0) → %K defaults to 50."""
        bars = [_make_bar(i, "100", "100", "100") for i in range(K_PERIOD)]
        result = compute_stochastic(bars)

        k, _ = result[bars[-1].date]
        assert k == Decimal(50)

    def test_d_value_is_sma_of_k(self) -> None:
        """With enough bars, %D should be the 3-day SMA of %K."""
        # 16 bars = K_PERIOD(14) + D_PERIOD(3) - 1 → 3 %K values, first %D on last bar
        num_bars = K_PERIOD + D_PERIOD - 1
        bars = [_make_bar(i, "200", "100", "150") for i in range(num_bars)]
        result = compute_stochastic(bars)

        # All bars have the same high/low/close, so all %K = 50, %D = 50
        dates = sorted(result.keys())
        assert len(dates) == D_PERIOD  # 3 entries with %K values

        # First two: %D is None (not enough %K values yet)
        assert result[dates[0]][1] is None
        assert result[dates[1]][1] is None

        # Third: %D is SMA of three identical %K values
        _, d = result[dates[2]]
        assert d == Decimal(50)

    def test_d_value_with_varying_closes(self) -> None:
        """Verify %D averages different %K values correctly."""
        # 16 bars, first 13 are identical, last 3 have different closes
        bars = [_make_bar(i, "200", "100", "150") for i in range(13)]
        bars.append(_make_bar(13, "200", "100", "100"))  # %K = 0
        bars.append(_make_bar(14, "200", "100", "150"))  # %K = 50
        bars.append(_make_bar(15, "200", "100", "200"))  # %K = 100

        result = compute_stochastic(bars)
        dates = sorted(result.keys())

        # Last entry: %D = (0 + 50 + 100) / 3 = 50
        _, d = result[dates[-1]]
        assert d == Decimal(50)

    def test_output_dates_match_input_bars(self) -> None:
        """Result dates should come from the input bars, starting at bar index K_PERIOD-1."""
        bars = [_make_bar(i, "200", "100", "150") for i in range(20)]
        result = compute_stochastic(bars)

        expected_dates = {bars[i].date for i in range(K_PERIOD - 1, 20)}
        assert set(result.keys()) == expected_dates

    def test_empty_list_returns_empty(self) -> None:
        assert compute_stochastic([]) == {}
