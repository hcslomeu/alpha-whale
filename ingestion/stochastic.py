"""Stochastic Oscillator computation from OHLCV data.

Computes %K and %D locally since Massive API does not provide this indicator.
"""

from datetime import date
from decimal import Decimal

from ingestion.schemas import OHLCVBar

K_PERIOD = 14
D_PERIOD = 3


def compute_stochastic(
    bars: list[OHLCVBar],
) -> dict[date, tuple[Decimal, Decimal | None]]:
    """Compute Stochastic %K and %D from OHLCV bars.

    Args:
        bars: OHLCV bars sorted by date ascending. Bars with fewer than
            ``K_PERIOD`` preceding bars are skipped.

    Returns:
        Mapping of date to (stoch_k, stoch_d). stoch_d is None when
        fewer than ``D_PERIOD`` %K values are available.
    """
    if len(bars) < K_PERIOD:
        return {}

    # Phase 1: compute %K for each bar that has a full 14-day window
    k_values: list[tuple[date, Decimal]] = []

    for i in range(K_PERIOD - 1, len(bars)):
        window = bars[i - K_PERIOD + 1 : i + 1]
        highest_high = max(b.high for b in window)
        lowest_low = min(b.low for b in window)

        spread = highest_high - lowest_low
        if spread == 0:
            k = Decimal(50)
        else:
            k = (bars[i].close - lowest_low) / spread * 100

        k_values.append((bars[i].date, k))

    # Phase 2: compute %D as 3-day SMA of %K
    result: dict[date, tuple[Decimal, Decimal | None]] = {}

    for idx, (dt, k) in enumerate(k_values):
        if idx < D_PERIOD - 1:
            result[dt] = (k, None)
        else:
            d_window = [k_values[j][1] for j in range(idx - D_PERIOD + 1, idx + 1)]
            d = sum(d_window, start=Decimal("0")) / Decimal(D_PERIOD)
            result[dt] = (k, d)

    return result
