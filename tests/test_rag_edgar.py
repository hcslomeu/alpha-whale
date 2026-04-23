"""Tests for SEC EDGAR data source."""

from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from ingestion.rag.edgar import (
    EdgarClient,
    EdgarSearchResult,
    FilingType,
    clean_html,
)

# --- Fixtures ---

SAMPLE_SEARCH_RESPONSE = {
    "hits": {
        "total": {"value": 2},
        "hits": [
            {
                "_id": "edgar/data/320193/000032019323000106/aapl-20230930.htm",
                "_source": {
                    "file_num": "0001-193125-23-268539",
                    "file_date": "2023-11-03",
                    "period_of_report": "2023-09-30",
                    "display_names": ["Apple Inc."],
                    "forms": "10-K",
                },
            },
            {
                "_id": "edgar/data/320193/000032019322000108/aapl-20220924.htm",
                "_source": {
                    "file_num": "0001-193125-22-276508",
                    "file_date": "2022-10-28",
                    "period_of_report": "2022-09-24",
                    "display_names": ["Apple Inc."],
                    "forms": "10-K",
                },
            },
        ],
    }
}

SAMPLE_FILING_HTML = """
<html>
<head>
    <title>10-K Filing</title>
    <style>body { font-family: Arial; }</style>
    <script>console.log('tracking');</script>
</head>
<body>
    <h1>UNITED STATES SECURITIES AND EXCHANGE COMMISSION</h1>
    <h2>FORM 10-K</h2>
    <div>
        <p>Apple Inc.</p>
        <p>Annual Report for the fiscal year ended September 30, 2023</p>
    </div>
    <h3>PART I</h3>
    <div>
        <h4>Item 1. Business</h4>
        <p>The Company designs, manufactures and markets smartphones,
        personal computers, tablets, wearables and accessories.</p>
    </div>
    <div>
        <h4>Item 1A. Risk Factors</h4>
        <p>The Company's operations and financial results are subject to
        various risks and uncertainties.</p>
    </div>
    <noscript>JavaScript is required</noscript>
</body>
</html>
"""


@pytest.fixture()
def edgar_client() -> EdgarClient:
    return EdgarClient(user_agent="TestApp test@example.com")


@pytest.fixture()
def sample_search_result() -> EdgarSearchResult:
    return EdgarSearchResult(
        accession_number="0001-193125-23-268539",
        filing_type=FilingType.TEN_K,
        filed_date=date(2023, 11, 3),
        period_of_report=date(2023, 9, 30),
        company_name="Apple Inc.",
        filing_url="https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm",
    )


# --- clean_html tests ---


class TestCleanHTML:
    """Test HTML to plain text conversion."""

    def test_strips_script_and_style_tags(self) -> None:
        result = clean_html(SAMPLE_FILING_HTML)
        assert "console.log" not in result
        assert "font-family" not in result

    def test_strips_noscript_tags(self) -> None:
        result = clean_html(SAMPLE_FILING_HTML)
        assert "JavaScript is required" not in result

    def test_preserves_heading_text(self) -> None:
        result = clean_html(SAMPLE_FILING_HTML)
        assert "UNITED STATES SECURITIES AND EXCHANGE COMMISSION" in result
        assert "FORM 10-K" in result

    def test_preserves_paragraph_text(self) -> None:
        result = clean_html(SAMPLE_FILING_HTML)
        assert "Apple Inc." in result
        assert "designs, manufactures and markets" in result

    def test_preserves_section_structure(self) -> None:
        result = clean_html(SAMPLE_FILING_HTML)
        assert "Item 1. Business" in result
        assert "Item 1A. Risk Factors" in result

    def test_deduplicates_adjacent_lines(self) -> None:
        html = "<div><p>Same line</p></div><div><p>Same line</p></div><p>Different</p>"
        result = clean_html(html)
        assert result.count("Same line") == 1
        assert "Different" in result

    def test_empty_html_returns_empty_string(self) -> None:
        assert clean_html("") == ""
        assert clean_html("<html><body></body></html>") == ""

    def test_skips_single_char_fragments(self) -> None:
        html = "<p>A</p><p>Real content here</p><p>B</p>"
        result = clean_html(html)
        assert "Real content here" in result
        assert result.count("A") == 0 or "A" not in result.split("\n\n")


# --- EdgarClient._parse_search_response tests ---


class TestParseSearchResponse:
    """Test EDGAR search API response parsing."""

    def test_parses_hits_into_search_results(self, edgar_client: EdgarClient) -> None:
        results = edgar_client._parse_search_response(
            SAMPLE_SEARCH_RESPONSE, "AAPL", FilingType.TEN_K
        )
        assert len(results) == 2

    def test_extracts_company_name(self, edgar_client: EdgarClient) -> None:
        results = edgar_client._parse_search_response(
            SAMPLE_SEARCH_RESPONSE, "AAPL", FilingType.TEN_K
        )
        assert results[0].company_name == "Apple Inc."

    def test_extracts_filed_date(self, edgar_client: EdgarClient) -> None:
        results = edgar_client._parse_search_response(
            SAMPLE_SEARCH_RESPONSE, "AAPL", FilingType.TEN_K
        )
        assert results[0].filed_date == date(2023, 11, 3)

    def test_extracts_period_of_report(self, edgar_client: EdgarClient) -> None:
        results = edgar_client._parse_search_response(
            SAMPLE_SEARCH_RESPONSE, "AAPL", FilingType.TEN_K
        )
        assert results[0].period_of_report == date(2023, 9, 30)

    def test_builds_filing_url(self, edgar_client: EdgarClient) -> None:
        results = edgar_client._parse_search_response(
            SAMPLE_SEARCH_RESPONSE, "AAPL", FilingType.TEN_K
        )
        assert results[0].filing_url.startswith("https://www.sec.gov/Archives/")

    def test_empty_response_returns_empty_list(self, edgar_client: EdgarClient) -> None:
        results = edgar_client._parse_search_response(
            {"hits": {"hits": []}}, "AAPL", FilingType.TEN_K
        )
        assert results == []

    def test_missing_hits_key_returns_empty_list(self, edgar_client: EdgarClient) -> None:
        results = edgar_client._parse_search_response({}, "AAPL", FilingType.TEN_K)
        assert results == []


# --- EdgarClient.search_filings tests ---


class TestSearchFilings:
    """Test EDGAR search API integration."""

    async def test_search_calls_api_with_correct_params(self, edgar_client: EdgarClient) -> None:
        mock_response = AsyncMock()
        mock_response.json.return_value = SAMPLE_SEARCH_RESPONSE

        with patch.object(EdgarClient, "search_filings", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = edgar_client._parse_search_response(
                SAMPLE_SEARCH_RESPONSE, "AAPL", FilingType.TEN_K
            )
            results = await mock_search("AAPL", FilingType.TEN_K)
            assert len(results) == 2

    async def test_search_with_date_range(self, edgar_client: EdgarClient) -> None:
        with patch.object(EdgarClient, "search_filings", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            results = await mock_search(
                "AAPL",
                FilingType.TEN_K,
                start_date=date(2023, 1, 1),
                end_date=date(2023, 12, 31),
            )
            assert results == []
            mock_search.assert_called_once()


# --- EdgarClient.fetch_filing tests ---


class TestFetchFiling:
    """Test filing HTML fetch and conversion."""

    async def test_fetch_returns_filing_with_clean_text(
        self,
        edgar_client: EdgarClient,
        sample_search_result: EdgarSearchResult,
    ) -> None:
        mock_response = httpx.Response(
            status_code=200,
            text=SAMPLE_FILING_HTML,
            request=httpx.Request("GET", sample_search_result.filing_url),
        )
        with patch("ingestion.rag.edgar.AsyncHTTPClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            filing = await edgar_client.fetch_filing(sample_search_result, "AAPL")

        assert filing.ticker == "AAPL"
        assert filing.filing_type == FilingType.TEN_K
        assert "Apple Inc." in filing.text
        assert "console.log" not in filing.text

    async def test_fetch_preserves_metadata(
        self,
        edgar_client: EdgarClient,
        sample_search_result: EdgarSearchResult,
    ) -> None:
        mock_response = httpx.Response(
            status_code=200,
            text="<html><body><p>Content</p></body></html>",
            request=httpx.Request("GET", sample_search_result.filing_url),
        )
        with patch("ingestion.rag.edgar.AsyncHTTPClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            filing = await edgar_client.fetch_filing(sample_search_result, "AAPL")

        assert filing.accession_number == sample_search_result.accession_number
        assert filing.filed_date == sample_search_result.filed_date
        assert filing.company_name == "Apple Inc."
        assert filing.filing_url == sample_search_result.filing_url


# --- EdgarFiling model tests ---


class TestEdgarFilingModel:
    """Test Pydantic model behavior."""

    def test_filing_type_enum_values(self) -> None:
        assert FilingType.TEN_K.value == "10-K"
        assert FilingType.TEN_Q.value == "10-Q"

    def test_filing_text_defaults_to_empty(self) -> None:
        from ingestion.rag.edgar import EdgarFiling

        filing = EdgarFiling(
            accession_number="test",
            ticker="AAPL",
            filing_type=FilingType.TEN_K,
            filed_date=date(2023, 11, 3),
            company_name="Apple Inc.",
            filing_url="https://example.com",
        )
        assert filing.text == ""
