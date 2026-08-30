"""
SignalAtlas Job Crawlers

Provides crawlers for job sources:
1. Wellfound
2. AIJobs.net
3. LinkedIn AI Jobs
4. AngelList AI Jobs
5. RemoteOK AI Jobs
"""

from typing import Any, Dict, List, Optional

from structlog import get_logger

from ..crawlers import BaseCrawler, CrawlRequest, CrawlResponse
from ..normalization.text import normalizer
from ..normalization.dates import date_normalizer

logger = get_logger(__name__)


class BaseJobCrawler(BaseCrawler):
    """Base class for job crawlers."""

    source_type = "job"
    max_depth = 2

    async def parse(self, response: CrawlResponse) -> List[Dict[str, Any]]:
        """Parse job posting from response."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.body, "lxml")

        # Extract metadata
        metadata = normalizer.extract_metadata(response.body)

        # Extract title (use h1 or first heading)
        title = normalizer.extract_title(response.body)

        # Extract main content
        content = normalizer.extract_main_content(response.body)

        # Extract date
        dates = date_normalizer.extract_from_html(response.body)
        published_date = None
        date_confidence = 0.0
        date_source = None

        if dates:
            dates.sort(key=lambda x: x[1], reverse=True)
            published_date_str, date_confidence = dates[0]
            published_date, _ = date_normalizer.normalize(published_date_str)
            date_source = "html_metadata"

        # Extract company
        company = self._extract_company(soup, metadata)

        # Extract location
        location = self._extract_location(soup, metadata)

        # Extract remote status
        is_remote = self._extract_remote(soup, content)

        # Extract role family
        role_family = self._extract_role_family(title, content)

        # Extract application URL
        application_url = self._extract_application_url(soup)

        # Build result
        result = {
            "record_type": "JOB",
            "source": {
                "name": self.source_name,
                "url": response.url,
            },
            "content": {
                "company": company or "Unknown",
                "role": title,
                "date": published_date,
                "is_remote": is_remote,
                "role_family": role_family,
                "location": location,
                "description": content,
                "application_url": application_url,
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

    def _extract_company(self, soup, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract company name from page."""
        # Try JSON-LD
        json_ld = metadata.get("json_ld")
        if json_ld and isinstance(json_ld, dict):
            company = json_ld.get("hiringOrganization", {}).get("name")
            if company:
                return company

        # Try meta tags
        company_meta = soup.find("meta", attrs={"name": "company"})
        if company_meta and company_meta.get("content"):
            return company_meta["content"]

        # Try common selectors
        for selector in [".company", ".employer", ".job-company", ".posting-company"]:
            company_el = soup.select_one(selector)
            if company_el:
                return company_el.get_text().strip()

        return None

    def _extract_location(self, soup, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract location from page."""
        # Try JSON-LD
        json_ld = metadata.get("json_ld")
        if json_ld and isinstance(json_ld, dict):
            location = json_ld.get("jobLocation", {}).get("address", {}).get("addressLocality")
            if location:
                return location

        # Try meta tags
        location_meta = soup.find("meta", attrs={"name": "location"})
        if location_meta and location_meta.get("content"):
            return location_meta["content"]

        # Try common selectors
        for selector in [".location", ".job-location", ".posting-location"]:
            location_el = soup.select_one(selector)
            if location_el:
                return location_el.get_text().strip()

        return None

    def _extract_remote(self, soup, content: str) -> Optional[bool]:
        """Extract remote status from page."""
        # Check for remote indicators in text
        remote_indicators = [
            "remote",
            "work from home",
            "wfh",
            "telecommute",
            "virtual",
            "distributed",
        ]

        content_lower = content.lower()
        for indicator in remote_indicators:
            if indicator in content_lower:
                return True

        # Check for non-remote indicators
        non_remote_indicators = [
            "onsite",
            "in-office",
            "office",
        ]

        for indicator in non_remote_indicators:
            if indicator in content_lower:
                return False

        return None

    def _extract_role_family(self, title: str, content: str) -> Optional[str]:
        """Extract role family from title and content."""
        from ..extraction.schemas import RoleFamily

        title_lower = title.lower()
        content_lower = content.lower()

        # Engineering
        engineering_keywords = [
            "engineer",
            "developer",
            "software",
            "backend",
            "frontend",
            "full stack",
            "full-stack",
            "devops",
            "ml engineer",
            "machine learning",
        ]

        for keyword in engineering_keywords:
            if keyword in title_lower or keyword in content_lower:
                return RoleFamily.ENGINEERING.value

        # Research
        research_keywords = [
            "research",
            "scientist",
            "phd",
            "postdoc",
        ]

        for keyword in research_keywords:
            if keyword in title_lower or keyword in content_lower:
                return RoleFamily.RESEARCH.value

        # Design
        design_keywords = [
            "design",
            "ui",
            "ux",
            "product designer",
        ]

        for keyword in design_keywords:
            if keyword in title_lower or keyword in content_lower:
                return RoleFamily.DESIGN.value

        # Product
        product_keywords = [
            "product manager",
            "product owner",
            "pm",
        ]

        for keyword in product_keywords:
            if keyword in title_lower or keyword in content_lower:
                return RoleFamily.PRODUCT.value

        return RoleFamily.OTHER.value

    def _extract_application_url(self, soup) -> Optional[str]:
        """Extract application URL from page."""
        # Try to find apply button/link
        for selector in [
            "a[href*='apply']",
            "a[href*='application']",
            ".apply-button",
            ".application-button",
        ]:
            apply_el = soup.select_one(selector)
            if apply_el and apply_el.get("href"):
                return apply_el["href"]

        return None

    def _hash_content(self, content: str) -> str:
        """Generate content hash."""
        from ..utils.hashing import hasher
        return hasher.hash_text(content)

    def _now(self) -> str:
        """Get current UTC timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


class WellfoundCrawler(BaseJobCrawler):
    """Crawler for Wellfound (formerly AngelList Talent)."""

    source_name = "wellfound"
    base_url = "https://wellfound.com"
    allowed_domains = ["wellfound.com", "angel.co"]

    async def discover(self) -> List[str]:
        """Discover AI job URLs from Wellfound."""
        urls = [
            "https://wellfound.com/jobs?tags=Artificial%20Intelligence",
            "https://wellfound.com/jobs?tags=Machine%20Learning",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch Wellfound page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class AIJobsNetCrawler(BaseJobCrawler):
    """Crawler for AIJobs.net."""

    source_name = "aijobs_net"
    base_url = "https://aijobs.net"
    allowed_domains = ["aijobs.net"]

    async def discover(self) -> List[str]:
        """Discover AI job URLs from AIJobs.net."""
        urls = [
            "https://aijobs.net/jobs/",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch AIJobs.net page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class LinkedInCrawler(BaseJobCrawler):
    """Crawler for LinkedIn AI Jobs."""

    source_name = "linkedin"
    base_url = "https://www.linkedin.com"
    allowed_domains = ["linkedin.com"]

    async def discover(self) -> List[str]:
        """Discover AI job URLs from LinkedIn."""
        urls = [
            "https://www.linkedin.com/jobs/search/?keywords=artificial%20intelligence",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch LinkedIn page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class AngelListCrawler(BaseJobCrawler):
    """Crawler for AngelList AI Jobs."""

    source_name = "angellist"
    base_url = "https://angel.co"
    allowed_domains = ["angel.co"]

    async def discover(self) -> List[str]:
        """Discover AI job URLs from AngelList."""
        urls = [
            "https://angel.co/jobs?query=artificial%20intelligence",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch AngelList page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


class RemoteOKCrawler(BaseJobCrawler):
    """Crawler for RemoteOK AI Jobs."""

    source_name = "remoteok"
    base_url = "https://remoteok.com"
    allowed_domains = ["remoteok.com"]

    async def discover(self) -> List[str]:
        """Discover AI job URLs from RemoteOK."""
        urls = [
            "https://remoteok.com/remote-ai-jobs",
        ]
        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch RemoteOK page."""
        from ..crawlers.base import AsyncHttpClient
        async with AsyncHttpClient() as client:
            return await client.fetch(request)


# Job crawler registry
JOB_CRAWLERS = {
    "wellfound": WellfoundCrawler(),
    "aijobs_net": AIJobsNetCrawler(),
    "linkedin": LinkedInCrawler(),
    "angellist": AngelListCrawler(),
    "remoteok": RemoteOKCrawler(),
}
