"""Firecrawl news source for Bronze-layer financial article ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from firecrawl import FirecrawlApp  # type: ignore[import-untyped]

from ingestion.rag.config import RAGSettings
from py_core.logging import get_logger

logger = get_logger("firecrawl")

_MARKDOWN_FORMATS = ["markdown"]


@dataclass(slots=True, frozen=True)
class NewsArticleMetadata:
    """Metadata extracted from a scraped news article."""

    title: str | None
    published_date: str | None
    source_domain: str | None
    url: str | None


@dataclass(slots=True, frozen=True)
class NewsArticle:
    """Structured news article content for downstream RAG ingestion."""

    text: str
    metadata: NewsArticleMetadata


class FirecrawlNewsSource:
    """Wrapper around Firecrawl for scraping financial news articles."""

    def __init__(
        self,
        settings: RAGSettings | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings or RAGSettings()
        self._client = client or FirecrawlApp(
            api_key=self._settings.firecrawl_api_key.get_secret_value()
        )

    def scrape_url(self, url: str) -> NewsArticle | None:
        """Scrape a single URL into structured markdown content."""
        try:
            document = self._client.scrape(
                url,
                formats=_MARKDOWN_FORMATS,
                only_main_content=True,
            )
            article = self._build_article(document, fallback_url=url)
            logger.info(
                "firecrawl_scrape_complete",
                url=url,
                source_domain=article.metadata.source_domain,
            )
            return article
        except Exception as exc:
            logger.warning(
                "firecrawl_scrape_failed",
                url=url,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return None

    def scrape_urls(self, urls: list[str]) -> list[NewsArticle]:
        """Scrape multiple URLs, skipping failures and continuing."""
        if not urls:
            return []

        try:
            batch_result = self._client.batch_scrape(
                urls,
                formats=_MARKDOWN_FORMATS,
                only_main_content=True,
                ignore_invalid_urls=True,
            )
            articles = self._build_articles_from_batch(batch_result, urls)
            logger.info(
                "firecrawl_batch_scrape_complete",
                requested=len(urls),
                succeeded=len(articles),
            )
            return articles
        except Exception as exc:
            logger.warning(
                "firecrawl_batch_scrape_failed",
                urls_count=len(urls),
                error_type=type(exc).__name__,
                error=str(exc),
            )

        fallback_articles: list[NewsArticle] = []
        for url in urls:
            article = self.scrape_url(url)
            if article is not None:
                fallback_articles.append(article)
        return fallback_articles

    def _build_articles_from_batch(
        self,
        batch_result: Any,
        urls: list[str],
    ) -> list[NewsArticle]:
        documents = self._extract_batch_documents(batch_result)
        articles: list[NewsArticle] = []

        for index, document in enumerate(documents):
            fallback_url = urls[index] if index < len(urls) else None
            try:
                articles.append(self._build_article(document, fallback_url=fallback_url))
            except Exception as exc:
                logger.warning(
                    "firecrawl_batch_item_failed",
                    url=fallback_url,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

        return articles

    def _extract_batch_documents(self, batch_result: Any) -> list[Any]:
        if isinstance(batch_result, list):
            return batch_result
        if isinstance(batch_result, dict):
            data = batch_result.get("data", [])
            return list(data) if isinstance(data, list) else []

        data = getattr(batch_result, "data", [])
        return list(data) if isinstance(data, list) else []

    def _build_article(
        self,
        document: Any,
        *,
        fallback_url: str | None,
    ) -> NewsArticle:
        document_data = self._to_dict(document)
        metadata = self._to_dict(document_data.get("metadata"))

        text = self._get_str(document_data, "markdown") or self._get_str(document_data, "content")
        if not text:
            raise ValueError("Firecrawl document did not include markdown content")

        source_url = (
            self._get_str(metadata, "source_url")
            or self._get_str(metadata, "sourceURL")
            or self._get_str(metadata, "url")
            or self._get_str(metadata, "og_url")
            or fallback_url
        )

        article_metadata = NewsArticleMetadata(
            title=self._first_str(metadata, "title", "og_title", "ogTitle"),
            published_date=self._first_str(
                metadata,
                "published_time",
                "publishedTime",
                "published_date",
                "publishedDate",
                "dc_date",
                "dcDate",
                "dc_date_created",
                "dcDateCreated",
                "dc_terms_created",
                "dcTermsCreated",
            ),
            source_domain=self._extract_domain(source_url),
            url=source_url,
        )
        return NewsArticle(text=text, metadata=article_metadata)

    def _to_dict(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="python")
            return dumped if isinstance(dumped, dict) else {}
        return {}

    def _get_str(self, data: dict[str, Any], key: str) -> str | None:
        value = data.get(key)
        return value if isinstance(value, str) and value.strip() else None

    def _first_str(self, data: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = self._get_str(data, key)
            if value is not None:
                return value
        return None

    def _extract_domain(self, url: str | None) -> str | None:
        if not url:
            return None

        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            return domain[4:]
        return domain or None
