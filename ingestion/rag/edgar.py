"""SEC EDGAR data source for financial filings (Bronze layer).

Fetches 10-K and 10-Q filings from SEC EDGAR Full-Text Search API,
cleans HTML to plain text, and returns structured filing data.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

from core.async_utils import AsyncHTTPClient
from core.logging import get_logger

logger = get_logger("edgar")

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# SEC rate limit: 10 req/s — AsyncHTTPClient retry handles 429 responses
_SEC_RATE_LIMIT_DELAY = 0.1


class FilingType(StrEnum):
    """Supported SEC filing types."""

    TEN_K = "10-K"
    TEN_Q = "10-Q"


class EdgarFiling(BaseModel):
    """Structured representation of an SEC filing."""

    accession_number: str
    ticker: str
    filing_type: FilingType
    filed_date: date
    period_of_report: date | None = None
    company_name: str
    filing_url: str
    text: str = ""


class EdgarSearchResult(BaseModel):
    """Metadata from EDGAR search before fetching full text."""

    accession_number: str
    filing_type: FilingType
    filed_date: date
    period_of_report: date | None = None
    company_name: str
    filing_url: str


class EdgarClient:
    """Async client for SEC EDGAR Full-Text Search API."""

    def __init__(self, user_agent: str) -> None:
        self._user_agent = user_agent
        self._headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    async def search_filings(
        self,
        ticker: str,
        filing_type: FilingType,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        max_results: int = 10,
    ) -> list[EdgarSearchResult]:
        """Search EDGAR for filings by ticker and type.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL").
            filing_type: Type of filing (10-K or 10-Q).
            start_date: Filter filings filed on or after this date.
            end_date: Filter filings filed on or before this date.
            max_results: Maximum number of results to return.

        Returns:
            List of search results with filing metadata.
        """
        params: dict[str, str | int] = {
            "q": f'"{ticker}"',
            "forms": filing_type.value,
            "from": 0,
            "size": max_results,
        }
        if start_date and end_date:
            params["dateRange"] = (
                f"custom&startdt={start_date.isoformat()}&enddt={end_date.isoformat()}"
            )

        async with AsyncHTTPClient(base_url=EDGAR_SEARCH_URL) as client:
            response = await client.get("", params=params, headers=self._headers)

        data = response.json()
        return self._parse_search_response(data, ticker, filing_type)

    def _parse_search_response(
        self,
        data: dict[str, Any],
        ticker: str,
        filing_type: FilingType,
    ) -> list[EdgarSearchResult]:
        """Parse EDGAR search API JSON into structured results."""
        results: list[EdgarSearchResult] = []
        hits = data.get("hits", {}).get("hits", [])

        for hit in hits:
            source = hit.get("_source", {})
            file_path = hit.get("_id", "")

            accession_raw = source.get("file_num", "")
            accession = accession_raw.replace("-", "") if accession_raw else ""

            filed_str = source.get("file_date", "")
            if not filed_str:
                logger.warning("edgar_hit_missing_date", hit_id=file_path)
                continue

            period_str = source.get("period_of_report", "")
            filing_url = f"https://www.sec.gov/Archives/{file_path}" if file_path else ""

            results.append(
                EdgarSearchResult(
                    accession_number=accession,
                    filing_type=filing_type,
                    filed_date=date.fromisoformat(filed_str),
                    period_of_report=date.fromisoformat(period_str) if period_str else None,
                    company_name=source.get("display_names", [ticker])[0],
                    filing_url=filing_url,
                )
            )

        logger.info(
            "edgar_search_complete",
            ticker=ticker,
            filing_type=filing_type.value,
            results_count=len(results),
        )
        return results

    async def fetch_filing(
        self,
        search_result: EdgarSearchResult,
        ticker: str,
    ) -> EdgarFiling:
        """Fetch filing HTML and convert to clean text.

        Args:
            search_result: Search result with filing URL.
            ticker: Stock ticker for metadata.

        Returns:
            EdgarFiling with cleaned text content.
        """
        async with AsyncHTTPClient() as client:
            response = await client.get(
                search_result.filing_url,
                headers={"User-Agent": self._user_agent, "Accept": "text/html"},
            )

        clean_text = clean_html(response.text)

        logger.info(
            "edgar_filing_fetched",
            ticker=ticker,
            filing_type=search_result.filing_type.value,
            text_length=len(clean_text),
        )

        return EdgarFiling(
            accession_number=search_result.accession_number,
            ticker=ticker,
            filing_type=search_result.filing_type,
            filed_date=search_result.filed_date,
            period_of_report=search_result.period_of_report,
            company_name=search_result.company_name,
            filing_url=search_result.filing_url,
            text=clean_text,
        )

    async def search_and_fetch(
        self,
        ticker: str,
        filing_type: FilingType,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        max_results: int = 10,
    ) -> list[EdgarFiling]:
        """Search for filings and fetch their full text.

        Convenience method combining search + fetch for each result.
        """
        search_results = await self.search_filings(
            ticker, filing_type, start_date=start_date, end_date=end_date, max_results=max_results
        )
        filings: list[EdgarFiling] = []
        for result in search_results:
            filing = await self.fetch_filing(result, ticker)
            filings.append(filing)

        return filings


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and extract readable text from SEC filings.

    Removes script/style elements, normalizes whitespace, and preserves
    paragraph structure with double newlines.

    Args:
        raw_html: Raw HTML content from SEC EDGAR.

    Returns:
        Clean plain text.
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "meta", "link", "noscript"]):
        tag.decompose()

    # Extract text with structure preservation
    lines: list[str] = []
    for element in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "td", "li", "span"]):
        if not isinstance(element, Tag):
            continue
        text = element.get_text(separator=" ", strip=True)
        if text and len(text) > 1:
            lines.append(text)

    # Deduplicate adjacent identical lines (common in SEC filings)
    deduped: list[str] = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    return "\n\n".join(deduped)
