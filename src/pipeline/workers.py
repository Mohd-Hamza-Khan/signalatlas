"""
SignalAtlas Pipeline Workers

Worker classes for processing crawl queues.
"""

import asyncio
from typing import Any, Dict, List, Optional

from structlog import get_logger

from ..crawlers import BaseCrawler, CrawlRequest
from ..pipeline.documents import DocumentProcessor, ProcessedDocument
from ..storage import get_db_context
from ..storage.models import RawDocument, Source

logger = get_logger(__name__)


class CrawlWorker:
    """
    Worker that processes crawl requests from the queue.

    Responsibilities:
    - Fetch URLs
    - Process into normalized documents
    - Store raw documents in database
    - Pass to extraction queue
    """

    def __init__(self, crawler: BaseCrawler):
        self.crawler = crawler
        self.doc_processor = DocumentProcessor()

    async def process_url(self, url: str) -> Optional[ProcessedDocument]:
        """
        Process a single URL through the full crawl pipeline.

        Args:
            url: URL to crawl

        Returns:
            ProcessedDocument or None on failure
        """
        request = CrawlRequest(
            url=url,
            source_name=self.crawler.source_name,
        )

        async with self.doc_processor:
            doc = await self.doc_processor.process(request)

        if doc:
            await self._save_raw_document(doc)

        return doc

    async def _save_raw_document(self, doc: ProcessedDocument) -> None:
        """Save raw document to database."""
        async with get_db_context() as session:
            # Get or create source
            source = await session.execute(
                Source.__table__.select().where(Source.name == doc.source_name)
            )
            source_id = source.scalar_one().id if source.scalar_one() else None

            # Check for duplicate
            existing = await session.execute(
                RawDocument.__table__.select().where(
                    RawDocument.content_hash == doc.content_hash
                )
            )
            if existing.scalar_one():
                logger.debug("Duplicate document skipped", url=doc.url)
                return

            # Create raw document
            raw_doc = RawDocument(
                source_id=source_id,
                url=doc.url,
                normalized_url=doc.normalized_url,
                content_hash=doc.content_hash,
                http_status=doc.http_status,
                content_type=doc.content_type,
                raw_html=doc.raw_html.decode("utf-8", errors="replace") if doc.raw_html else None,
                clean_text=doc.clean_text,
                fetched_at=doc.fetched_at,
                metadata=doc.metadata or {},
            )
            session.add(raw_doc)
            await session.commit()
            logger.info("Saved raw document", url=doc.url, source=doc.source_name)

    async def crawl_batch(
        self,
        urls: List[str],
        max_concurrent: int = 5,
    ) -> List[ProcessedDocument]:
        """
        Crawl multiple URLs concurrently.

        Args:
            urls: List of URLs to crawl
            max_concurrent: Maximum concurrent crawls

        Returns:
            List of processed documents
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def crawl_one(url: str) -> Optional[ProcessedDocument]:
            async with semaphore:
                return await self.process_url(url)

        tasks = [crawl_one(url) for url in urls]
        processed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in processed:
            if isinstance(result, ProcessedDocument):
                results.append(result)
            elif isinstance(result, Exception):
                logger.error("Crawl error", error=str(result))

        return results
