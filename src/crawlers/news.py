"""
SignalAtlas News Crawlers

Provides crawlers for news sources:
1. TechCrunch AI
2. VentureBeat AI
3. The Decoder
4. AI News
5. MIT Technology Review AI
"""

from typing import Any, Dict, List, Optional

from structlog import get_logger

from ..crawlers import BaseCrawler, CrawlRequest, CrawlResponse
from ..normalization.text import normalizer
from ..normalization.dates import date_normalizer

logger = get_logger(__name__)


class BaseNewsCrawler(BaseCrawler):
    """Base class for news crawlers."""

    source_type = "news"
    max_depth = 2

    async def parse(self, response: CrawlResponse) -> List[Dict[str, Any]]:
        """Parse news article from response."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.body, "lxml")

        # Extract metadata
        metadata = normalizer.extract_metadata(response.body)

        # Extract title
        title = normalizer.extract_title(response.body)

        # Extract main content
        content = normalizer.extract_main_content(response.body)

        # Extract date
        dates = date_normalizer.extract_from_html(response.body)
        published_date = None
        date_confidence = 0.0
        date_source = None

        if dates:
            # Use highest confidence date
            dates.sort(key=lambda x: x[1], reverse=True)
            published_date_str, date_confidence = dates[0]
            published_date, _ = date_normalizer.normalize(published_date_str)
            date_source = "html_metadata"

        # Extract author
        author = self._extract_author(soup)

        # Extract image URL
        image_url = self._extract_image_url(soup, metadata)

        # Build result
        result = {
            "record_type": "NEWS",
            "source": {
                "name": self.source_name,
                "url": response.url,
            },
            "content": {
                "title": title,
                "body": content,
                "published_date": published_date,
                "author": author,
                "image_url": image_url,
            },
            "provenance": {
                "content_hash": self._hash_content(content),
                "date_source": date_source,
                "date_confidence": date_confidence,
                "extraction_provider": None,
            },
            "collected_at": self._now(),
        }

        return [result]

    def _extract_author(self, soup) -> Optional[str]:
        """Extract author from page."""
        # Try meta tags
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            return author_meta["content"]

        # Try common class names
        for selector in [".author", ".byline", ".post-author", ".article-author"]:
            author_el = soup.select_one(selector)
            if author_el:
                return author_el.get_text().strip()

        return None

    def _extract_image_url(self, soup, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract featured image URL."""
        # Try OpenGraph image
        if "og_image" in metadata:
            return metadata["og_image"]

        # Try meta tags
        image_meta = soup.find("meta", property="og:image")
        if image_meta and image_meta.get("content"):
            return image_meta["content"]

        # Try img tags
        img = soup.find("img")
        if img and img.get("src"):
            return img["src"]

        return None

    def _hash_content(self, content: str) -> str:
        """Generate content hash."""
        from ..utils.hashing import hasher
        return hasher.hash_text(content)

    def _now(self) -> str:
        """Get current UTC timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


class TechCrunchCrawler(BaseNewsCrawler):
    """Crawler for TechCrunch AI news."""

    source_name = "techcrunch"
    base_url = "https://techcrunch.com"
    allowed_domains = ["techcrunch.com"]

    async def discover(self) -> List[str]:
        """Discover AI news URLs from TechCrunch."""
        urls = [
            "https://techcrunch.com/tag/artificial-intelligence/",
            "https://techcrunch.com/category/ai/",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch TechCrunch page."""
        # Use base implementation
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class VentureBeatCrawler(BaseNewsCrawler):
    """Crawler for VentureBeat AI news."""

    source_name = "venturebeat"
    base_url = "https://venturebeat.com"
    allowed_domains = ["venturebeat.com"]

    async def discover(self) -> List[str]:
        """Discover AI news URLs from VentureBeat."""
        urls = [
            "https://venturebeat.com/category/ai/",
            "https://venturebeat.com/tag/artificial-intelligence/",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch VentureBeat page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class TheDecoderCrawler(BaseNewsCrawler):
    """Crawler for The Decoder AI news."""

    source_name = "thedecoder"
    base_url = "https://thedecoder.com"
    allowed_domains = ["thedecoder.com"]

    async def discover(self) -> List[str]:
        """Discover AI news URLs from The Decoder."""
        urls = [
            "https://thedecoder.com/",
            "https://thedecoder.com/category/ai-news/",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch The Decoder page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class AINewsCrawler(BaseNewsCrawler):
    """Crawler for AI News."""

    source_name = "ainews"
    base_url = "https://ai-news.com"
    allowed_domains = ["ai-news.com"]

    async def discover(self) -> List[str]:
        """Discover AI news URLs."""
        urls = [
            "https://ai-news.com/",
            "https://ai-news.com/news/",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch AI News page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class MITTechReviewCrawler(BaseNewsCrawler):
    """Crawler for MIT Technology Review AI news."""

    source_name = "mit_tech_review"
    base_url = "https://www.technologyreview.com"
    allowed_domains = ["technologyreview.com"]

    async def discover(self) -> List[str]:
        """Discover AI news URLs from MIT Tech Review."""
        urls = [
            "https://www.technologyreview.com/topic/artificial-intelligence/",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch MIT Tech Review page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


# News crawler registry
NEWS_CRAWLERS = {
    "techcrunch": TechCrunchCrawler(),
    "venturebeat": VentureBeatCrawler(),
    "thedecoder": TheDecoderCrawler(),
    "ainews": AINewsCrawler(),
    "mit_tech_review": MITTechReviewCrawler(),
}
