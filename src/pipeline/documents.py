"""
SignalAtlas Raw Document Processor

Processes raw crawled documents to ensure data fidelity.
Every document must have:
- original URL
- normalized URL
- HTTP status
- raw HTML (where permitted)
- cleaned text
- content hash
- fetched_at
- source name
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from structlog import get_logger

from ..crawlers.base import CrawlRequest, CrawlResponse, AsyncHttpClient
from ..normalization import normalizer, url_normalizer, date_normalizer
from ..utils.hashing import hasher

logger = get_logger(__name__)


@dataclass
class ProcessedDocument:
    """A fully processed document with all required fields."""
    url: str
    normalized_url: str
    http_status: int
    raw_html: Optional[bytes]
    clean_text: str
    content_hash: str
    fetched_at: datetime
    source_name: str
    content_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentProcessor:
    """
    Processes raw crawl responses into normalized documents.

    Ensures all required fields are present and properly formatted.
    """

    def __init__(self):
        self.http_client = AsyncHttpClient()

    async def __aenter__(self):
        await self.http_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.__aexit__(exc_type, exc_val, exc_tb)

    async def process(
        self,
        request: CrawlRequest,
        response: Optional[CrawlResponse] = None,
    ) -> Optional[ProcessedDocument]:
        """
        Process a crawl request/response into a normalized document.

        Args:
            request: The original crawl request
            response: Optional pre-fetched response

        Returns:
            ProcessedDocument with all required fields, or None on failure
        """
        if response is None:
            # Fetch if not provided
            try:
                response = await self.http_client.fetch(request)
            except Exception as e:
                logger.error(
                    "Failed to fetch document",
                    url=request.url,
                    error=str(e),
                    source=request.source_name,
                )
                return None

        try:
            # Extract title from HTML
            title = normalizer.extract_title(response.body)

            # Extract metadata
            metadata = normalizer.extract_metadata(response.body)

            # Extract headings
            headings = normalizer.extract_headings(response.body)

            # Extract paragraphs
            paragraphs = normalizer.extract_paragraphs(response.body)

            # Build processed document
            doc = ProcessedDocument(
                url=str(response.url),
                normalized_url=url_normalizer.normalize(str(response.url)),
                http_status=response.status_code,
                raw_html=response.body,
                clean_text=normalizer.clean_html(response.body),
                content_hash=hasher.hash_bytes(response.body),
                fetched_at=datetime.utcnow(),
                source_name=request.source_name,
                content_type=response.content_type,
                metadata={
                    "title": title,
                    "metadata": metadata,
                    "headings": headings,
                    "paragraphs": paragraphs,
                    "fetch_duration": response.fetch_duration,
                    "attempt": response.attempt,
                },
            )

            # Validate all required fields
            if not self._validate(doc):
                logger.warning(
                    "Document missing required fields",
                    url=doc.url,
                    source=doc.source_name,
                )
                return None

            return doc

        except Exception as e:
            logger.error(
                "Failed to process document",
                url=request.url,
                error=str(e),
                source=request.source_name,
            )
            return None

    def _validate(self, doc: ProcessedDocument) -> bool:
        """Validate that all required fields are present."""
        required_fields = [
            "url",
            "normalized_url",
            "http_status",
            "clean_text",
            "content_hash",
            "fetched_at",
            "source_name",
        ]

        for field in required_fields:
            if not getattr(doc, field):
                logger.debug(f"Missing field: {field}")
                return False

        return True

    async def process_batch(
        self,
        requests: List[CrawlRequest],
        max_concurrent: int = 10,
    ) -> List[ProcessedDocument]:
        """
        Process multiple documents concurrently.

        Args:
            requests: List of crawl requests
            max_concurrent: Maximum concurrent requests

        Returns:
            List of processed documents
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def process_one(req: CrawlRequest) -> Optional[ProcessedDocument]:
            async with semaphore:
                return await self.process(req)

        tasks = [process_one(req) for req in requests]
        processed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in processed:
            if isinstance(result, ProcessedDocument):
                results.append(result)
            elif isinstance(result, Exception):
                logger.error("Document processing error", error=str(result))

        return results


# Singleton for convenience
processor = DocumentProcessor()
