"""
SignalAtlas Pipeline Runner

Orchestrates the complete data pipeline:
1. Crawling
2. Extraction
3. Normalization
4. Entity Resolution
5. Storage
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from structlog import get_logger

from ..config import settings
from ..crawlers import (
    GitHubCrawler,
    NEWS_CRAWLERS,
    JOB_CRAWLERS,
)
from ..extraction.orchestrator import LLMExtractor
from ..normalization import (
    normalizer,
    url_normalizer,
    date_normalizer,
    freshness_filter,
)
from ..resolution import entity_resolver
from ..storage import storage, db
from ..utils.hashing import hasher

logger = get_logger(__name__)


class PipelineRunner:
    """
    Runs the complete data pipeline.
    """

    def __init__(self):
        self.crawlers = []
        self.extractor = None
        self._initialized = False

    async def init(self) -> None:
        """Initialize the pipeline."""
        if self._initialized:
            return

        logger.info("Initializing pipeline...")

        # Initialize database
        await db.init()

        # Initialize extractor
        self.extractor = LLMExtractor(api_key=settings.OPENROUTER_API_KEY)

        # Initialize crawlers
        self.crawlers = [
            GitHubCrawler(),
            *NEWS_CRAWLERS.values(),
            *JOB_CRAWLERS.values(),
        ]

        self._initialized = True
        logger.info("Pipeline initialized")

    async def close(self) -> None:
        """Close the pipeline."""
        logger.info("Closing pipeline...")
        await db.close()
        self._initialized = False

    async def run_crawlers(self) -> Dict[str, Any]:
        """Run all crawlers."""
        await self.init()

        results = {
            "total_crawled": 0,
            "total_failed": 0,
            "by_source": {},
        }

        for crawler in self.crawlers:
            source_name = crawler.source_name
            logger.info(f"Crawling {source_name}...")

            try:
                # Discover URLs
                urls = await crawler.discover()
                logger.info(f"Discovered {len(urls)} URLs for {source_name}")

                # Crawl each URL
                source_results = {
                    "success": 0,
                    "failed": 0,
                    "urls": [],
                }

                for url in urls[:settings.MAX_PAGES_PER_SOURCE]:
                    try:
                        from ..crawlers.base import CrawlRequest
                        request = CrawlRequest(url=url)
                        response = await crawler.fetch(request)

                        if response.status == 200:
                            # Parse response
                            parsed = await crawler.parse(response)
                            source_results["success"] += 1
                            source_results["urls"].append(url)

                            # Store raw document
                            await self._store_raw_document(
                                url, response, crawler.source_name
                            )

                            # Process parsed data
                            for item in parsed:
                                await self._process_item(item, crawler.source_name)

                        else:
                            source_results["failed"] += 1
                            logger.warning(
                                f"Failed to crawl {url}: {response.status}"
                            )

                    except Exception as e:
                        source_results["failed"] += 1
                        logger.error(f"Error crawling {url}: {e}")

                results["total_crawled"] += source_results["success"]
                results["total_failed"] += source_results["failed"]
                results["by_source"][source_name] = source_results

            except Exception as e:
                logger.error(f"Error crawling {source_name}: {e}")
                results["by_source"][source_name] = {
                    "error": str(e),
                    "success": 0,
                    "failed": 0,
                }

        logger.info(
            "Crawling completed",
            total_crawled=results["total_crawled"],
            total_failed=results["total_failed"],
        )

        return results

    async def run_extraction(self) -> Dict[str, Any]:
        """Run extraction on stored documents."""
        await self.init()

        # TODO: Implement extraction from stored documents
        logger.info("Extraction completed")

        return {
            "extracted": 0,
            "failed": 0,
        }

    async def run_resolution(self) -> Dict[str, Any]:
        """Run entity resolution."""
        await self.init()

        # TODO: Implement entity resolution on stored entities
        logger.info("Entity resolution completed")

        return {
            "resolved": 0,
            "failed": 0,
        }

    async def run(self) -> Dict[str, Any]:
        """Run the full pipeline."""
        await self.init()

        start_time = datetime.now(timezone.utc)
        logger.info("Starting full pipeline...")

        results = {}

        # Step 1: Crawl
        logger.info("Step 1: Crawling...")
        results["crawl"] = await self.run_crawlers()

        # Step 2: Extraction (on crawled data)
        logger.info("Step 2: Extracting...")
        results["extraction"] = await self.run_extraction()

        # Step 3: Resolution
        logger.info("Step 3: Resolving entities...")
        results["resolution"] = await self.run_resolution()

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        logger.info(
            "Pipeline completed",
            duration_seconds=duration,
            total_crawled=results["crawl"]["total_crawled"],
        )

        return {
            "status": "completed",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "results": results,
        }

    async def _store_raw_document(
        self,
        url: str,
        response: Any,
        source_name: str,
    ) -> None:
        """Store a raw document."""
        from ..storage import RawDocument

        normalized_url = url_normalizer.normalize(url)
        content_hash = hasher.hash_text(response.body)

        # Check for duplicate
        existing = await storage.get_record(RawDocument, content_hash)
        if existing:
            logger.debug(f"Duplicate document: {url}")
            return

        document = {
            "id": hasher.hash_text(f"{url}:{datetime.now(timezone.utc).isoformat()}"),
            "url": url,
            "normalized_url": normalized_url,
            "content_hash": content_hash,
            "http_status": response.status,
            "content_type": response.headers.get("Content-Type", "text/html"),
            "raw_html": response.body,
            "clean_text": normalizer.clean_html(response.body),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "source": source_name,
                "content_length": len(response.body),
            },
        }

        await storage.save_record(document, RawDocument)
        logger.debug(f"Stored document: {url}")

    async def _process_item(self, item: Dict[str, Any], source_name: str) -> None:
        """Process a parsed item."""
        try:
            # Normalize dates
            if "content" in item and "published_date" in item["content"]:
                published_date = item["content"]["published_date"]
                if isinstance(published_date, str):
                    normalized_date, confidence = date_normalizer.normalize(published_date)
                    item["content"]["published_date"] = normalized_date
                    item["provenance"]["date_confidence"] = confidence

            # Check freshness
            if settings.FILTER_FRESHNESS:
                is_fresh, confidence, date_source = freshness_filter.is_fresh(item)
                if not is_fresh:
                    logger.debug(f"Skipping stale item: {item.get('source', {}).get('url')}")
                    return

            # Extract entities based on record type
            record_type = item.get("record_type", "UNKNOWN")

            if record_type == "STARTUP":
                await self._store_startup(item, source_name)
            elif record_type == "PRODUCT":
                await self._store_product(item, source_name)
            elif record_type == "RESEARCH_PAPER":
                await self._store_paper(item, source_name)
            elif record_type == "JOB":
                await self._store_job(item, source_name)
            elif record_type == "NEWS":
                await self._store_news(item, source_name)
            else:
                logger.warning(f"Unknown record type: {record_type}")

        except Exception as e:
            logger.error(f"Error processing item: {e}")

    async def _store_startup(self, item: Dict[str, Any], source_name: str) -> None:
        """Store a startup."""
        from ..storage import Startup

        # Resolve entity
        resolved = entity_resolver.resolve(
            item["content"].get("name", ""),
            "startup",
        )

        startup_data = {
            "id": hasher.hash_text(f"startup:{item['source']['url']}"),
            "canonical_name": resolved.canonical_name,
            "description": item["content"].get("description"),
            "employee_count": item["content"].get("employee_count"),
            "website": item["content"].get("website"),
            "founded_year": item["content"].get("founded_year"),
            "location": item["content"].get("location"),
            "batch": item["content"].get("batch"),
            "source_url": item["source"]["url"],
            "source_name": source_name,
            "provenance": {
                **item.get("provenance", {}),
                "entity_resolution": {
                    "method": resolved.method,
                    "confidence": resolved.confidence,
                },
            },
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        await storage.save_record(startup_data, Startup)
        logger.debug(f"Stored startup: {resolved.canonical_name}")

    async def _store_product(self, item: Dict[str, Any], source_name: str) -> None:
        """Store a product."""
        from ..storage import Product

        product_data = {
            "id": hasher.hash_text(f"product:{item['source']['url']}"),
            "product_name": item["content"].get("name", ""),
            "startup_id": None,  # TODO: Link to startup
            "pricing_model": item["content"].get("pricing_model"),
            "website": item["content"].get("website"),
            "description": item["content"].get("description"),
            "tagline": item["content"].get("tagline"),
            "source_url": item["source"]["url"],
            "provenance": item.get("provenance", {}),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        await storage.save_record(product_data, Product)
        logger.debug(f"Stored product: {product_data['product_name']}")

    async def _store_paper(self, item: Dict[str, Any], source_name: str) -> None:
        """Store a research paper."""
        from ..storage import ResearchPaper

        paper_data = {
            "id": hasher.hash_text(f"paper:{item['source']['url']}"),
            "external_id": item["content"].get("external_id"),
            "title": item["content"].get("title", ""),
            "authors": item["content"].get("authors", []),
            "paper_url": item["source"]["url"],
            "github_url": item["content"].get("github_url"),
            "github_stars": item["content"].get("github_stars"),
            "github_match_confidence": item["content"].get("github_match_confidence"),
            "published_date": item["content"].get("published_date"),
            "abstract": item["content"].get("abstract"),
            "category": item["content"].get("category"),
            "provenance": item.get("provenance", {}),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        await storage.save_record(paper_data, ResearchPaper)
        logger.debug(f"Stored paper: {paper_data['title']}")

    async def _store_job(self, item: Dict[str, Any], source_name: str) -> None:
        """Store a job."""
        from ..storage import Job

        content = item["content"]

        job_data = {
            "id": hasher.hash_text(f"job:{item['source']['url']}"),
            "source_url": item["source"]["url"],
            "company": content.get("company", ""),
            "role": content.get("role", ""),
            "published_at": content.get("published_date") or content.get("date"),
            "is_remote": content.get("is_remote"),
            "role_family": content.get("role_family"),
            "location": content.get("location"),
            "description": content.get("description"),
            "application_url": content.get("application_url"),
            "date_source": item.get("provenance", {}).get("date_source"),
            "date_confidence": item.get("provenance", {}).get("date_confidence", 0.0),
            "content_hash": hasher.hash_text(content.get("description", "")),
            "provenance": item.get("provenance", {}),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        await storage.save_record(job_data, Job)
        logger.debug(f"Stored job: {job_data['role']} at {job_data['company']}")

    async def _store_news(self, item: Dict[str, Any], source_name: str) -> None:
        """Store a news article."""
        from ..storage import News

        content = item["content"]

        news_data = {
            "id": hasher.hash_text(f"news:{item['source']['url']}"),
            "source_url": item["source"]["url"],
            "title": content.get("title", ""),
            "body": content.get("body", ""),
            "published_at": content.get("published_date") or content.get("date"),
            "author": content.get("author"),
            "date_source": item.get("provenance", {}).get("date_source"),
            "date_confidence": item.get("provenance", {}).get("date_confidence", 0.0),
            "content_hash": hasher.hash_text(content.get("body", "")),
            "provenance": item.get("provenance", {}),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        await storage.save_record(news_data, News)
        logger.debug(f"Stored news: {news_data['title']}")
