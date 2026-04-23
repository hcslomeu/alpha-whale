"""CLI entry point: ``uv run python -m ingestion``."""

import asyncio
import sys

from dotenv import load_dotenv

from ingestion.config import IngestionSettings
from ingestion.pipeline import run_pipeline


def main() -> None:
    """Run the ingestion pipeline with settings from environment variables."""
    load_dotenv()
    settings = IngestionSettings()
    report = asyncio.run(run_pipeline(settings))

    for r in report.results:
        status = "OK" if r.error is None else f"FAILED: {r.error}"
        print(f"  {r.ticker}: {r.ohlcv_rows} OHLCV, {r.indicator_rows} indicators — {status}")

    print(f"\nDone: {report.succeeded} succeeded, {report.failed} failed")

    if report.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
