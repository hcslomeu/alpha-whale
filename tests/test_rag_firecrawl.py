"""Tests for the Firecrawl news source."""

from unittest.mock import MagicMock, patch

import pytest

from ingestion.rag.config import RAGSettings
from ingestion.rag.firecrawl_source import FirecrawlNewsSource

REQUIRED_ENV = {
    "PINECONE_API_KEY": "test-pinecone-key",
    "OPENAI_API_KEY": "test-openai-key",
    "COHERE_API_KEY": "test-cohere-key",
    "FIRECRAWL_API_KEY": "test-firecrawl-key",
    "RAG_EDGAR_USER_AGENT": "TestApp test@example.com",
}


@pytest.fixture()
def rag_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set all required env vars for RAGSettings."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)


def test_scrape_url_returns_news_article(rag_env: None) -> None:
    url = "https://www.reuters.com/markets/us/example-story"
    response = {
        "markdown": "# Fed holds rates",
        "metadata": {
            "title": "Fed holds rates",
            "published_time": "2026-03-24T14:30:00Z",
            "source_url": url,
        },
    }

    with patch("ingestion.rag.firecrawl_source.FirecrawlApp") as mock_app:
        mock_client = MagicMock()
        mock_client.scrape.return_value = response
        mock_app.return_value = mock_client

        source = FirecrawlNewsSource()
        article = source.scrape_url(url)

    assert article is not None
    assert article.text == "# Fed holds rates"
    assert article.metadata.title == "Fed holds rates"
    assert article.metadata.published_date == "2026-03-24T14:30:00Z"
    assert article.metadata.source_domain == "reuters.com"
    assert article.metadata.url == url
    mock_app.assert_called_once_with(api_key="test-firecrawl-key")
    mock_client.scrape.assert_called_once_with(
        url,
        formats=["markdown"],
        only_main_content=True,
    )


def test_scrape_urls_batch_returns_articles(rag_env: None) -> None:
    urls = [
        "https://example.com/article-1",
        "https://news.example.com/article-2",
    ]
    mock_client = MagicMock()
    mock_client.batch_scrape.return_value = {
        "data": [
            {
                "markdown": "# Article 1",
                "metadata": {
                    "title": "Article 1",
                    "published_time": "2026-03-24",
                    "source_url": urls[0],
                },
            },
            {
                "markdown": "# Article 2",
                "metadata": {
                    "title": "Article 2",
                    "published_time": "2026-03-23",
                    "source_url": urls[1],
                },
            },
        ]
    }

    source = FirecrawlNewsSource(settings=RAGSettings(), client=mock_client)
    articles = source.scrape_urls(urls)

    assert [article.metadata.title for article in articles] == ["Article 1", "Article 2"]
    assert [article.metadata.source_domain for article in articles] == [
        "example.com",
        "news.example.com",
    ]
    mock_client.batch_scrape.assert_called_once_with(
        urls,
        formats=["markdown"],
        only_main_content=True,
        ignore_invalid_urls=True,
    )


def test_scrape_url_extracts_metadata_from_response(rag_env: None) -> None:
    url = "https://www.ft.com/content/example"
    mock_client = MagicMock()
    mock_client.scrape.return_value = {
        "markdown": "Markets wrap",
        "metadata": {
            "og_title": "FT Markets Wrap",
            "publishedTime": "2026-03-24T10:15:00Z",
        },
    }

    source = FirecrawlNewsSource(settings=RAGSettings(), client=mock_client)
    article = source.scrape_url(url)

    assert article is not None
    assert article.metadata.title == "FT Markets Wrap"
    assert article.metadata.published_date == "2026-03-24T10:15:00Z"
    assert article.metadata.source_domain == "ft.com"
    assert article.metadata.url == url


def test_scrape_url_returns_none_on_api_error(rag_env: None) -> None:
    url = "https://example.com/failure"
    mock_client = MagicMock()
    mock_client.scrape.side_effect = RuntimeError("service unavailable")

    with patch("ingestion.rag.firecrawl_source.logger") as mock_logger:
        source = FirecrawlNewsSource(settings=RAGSettings(), client=mock_client)
        article = source.scrape_url(url)

    assert article is None
    mock_logger.warning.assert_called_once()
    assert mock_logger.warning.call_args.kwargs["url"] == url


def test_scrape_urls_falls_back_to_single_scrapes_when_batch_fails(rag_env: None) -> None:
    urls = [
        "https://example.com/article-1",
        "https://example.com/article-2",
        "https://example.com/article-3",
    ]
    mock_client = MagicMock()
    mock_client.batch_scrape.side_effect = RuntimeError("batch timeout")

    def scrape_side_effect(
        url: str, *, formats: list[str], only_main_content: bool
    ) -> dict[str, object]:
        if url == urls[1]:
            raise RuntimeError("page blocked")
        return {
            "markdown": f"content for {url}",
            "metadata": {
                "title": f"title for {url}",
                "source_url": url,
            },
        }

    mock_client.scrape.side_effect = scrape_side_effect

    with patch("ingestion.rag.firecrawl_source.logger") as mock_logger:
        source = FirecrawlNewsSource(settings=RAGSettings(), client=mock_client)
        articles = source.scrape_urls(urls)

    assert [article.metadata.url for article in articles] == [urls[0], urls[2]]
    assert mock_client.scrape.call_count == 3
    assert mock_logger.warning.call_count == 2
