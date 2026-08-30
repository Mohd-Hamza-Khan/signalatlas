"""
SignalAtlas Crawler Interface

Base classes and interfaces for all crawlers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import CrawlRequest, CrawlResponse


@dataclass
class DiscoveredURL:
    """A URL discovered during crawling."""
    url: str
    source_name: str
    source_url: Optional[str] = None
    depth: int = 0
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlResult:
    """Result of crawling a single URL."""
    url: str
    source_name: str
    status: str  # success, failed, skipped
    response: Optional[CrawlResponse] = None
    error: Optional[str] = None
    discovered_urls: List[DiscoveredURL] = field(default_factory=list)
    parsed_data: Optional[Dict[str, Any]] = None
    crawl_duration: float = 0.0


class BaseCrawler(ABC):
    """
    Abstract base class for all crawlers.

    Every crawler must implement:
    - discover(): Find URLs to crawl
    - fetch(): Fetch a single URL
    - parse(): Parse response into structured data
    """

    source_name: str = "base"
    base_url: Optional[str] = None
    source_type: str = "unknown"
    max_depth: int = 3
    allowed_domains: Optional[List[str]] = None

    @abstractmethod
    async def discover(self) -> List[str]:
        """
        Discover URLs to crawl.

        Returns:
            List of URLs to crawl
        """
        pass

    @abstractmethod
    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """
        Fetch a single URL.

        Args:
            request: CrawlRequest with URL and headers

        Returns:
            CrawlResponse with status, body, headers
        """
        pass

    @abstractmethod
    async def parse(self, response: CrawlResponse) -> List[Dict[str, Any]]:
        """
        Parse response into structured data.

        Args:
            response: CrawlResponse from fetch

        Returns:
            List of parsed data dictionaries
        """
        pass

    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed for this crawler."""
        if self.allowed_domains is None:
            return True

        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        return domain in self.allowed_domains

    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        # Remove fragment
        parsed = parsed._replace(fragment="")
        # Normalize scheme and netloc to lowercase
        parsed = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
        )
        # Remove trailing slash from path (except root)
        if parsed.path and parsed.path != "/" and parsed.path.endswith("/"):
            parsed = parsed._replace(path=parsed.path.rstrip("/"))

        return urlunparse(parsed)


# Import specific crawlers
from ..crawlers.github import GitHubCrawler, github_crawler
from ..crawlers.news import (
    BaseNewsCrawler,
    TechCrunchCrawler,
    VentureBeatCrawler,
    TheDecoderCrawler,
    AINewsCrawler,
    MITTechReviewCrawler,
    NEWS_CRAWLERS,
)
from ..crawlers.jobs import (
    BaseJobCrawler,
    WellfoundCrawler,
    AIJobsNetCrawler,
    LinkedInCrawler,
    AngelListCrawler,
    RemoteOKCrawler,
    JOB_CRAWLERS,
)

__all__ = [
    # Base classes
    "BaseCrawler",
    "CrawlRequest",
    "CrawlResponse",
    "DiscoveredURL",
    "CrawlResult",
    # GitHub
    "GitHubCrawler",
    "github_crawler",
    # News
    "BaseNewsCrawler",
    "TechCrunchCrawler",
    "VentureBeatCrawler",
    "TheDecoderCrawler",
    "AINewsCrawler",
    "MITTechReviewCrawler",
    "NEWS_CRAWLERS",
    # Jobs
    "BaseJobCrawler",
    "WellfoundCrawler",
    "AIJobsNetCrawler",
    "LinkedInCrawler",
    "AngelListCrawler",
    "RemoteOKCrawler",
    "JOB_CRAWLERS",
]
