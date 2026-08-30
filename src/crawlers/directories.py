"""
Y Combinator Directory Crawler

Crawls the Y Combinator startup directory for startup data.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from structlog import get_logger

from ..crawlers import BaseCrawler, CrawlRequest, CrawlResponse, CrawlResult, DiscoveredURL
from ..crawlers.base import AsyncHttpClient
from ..utils.hashing import hasher

logger = get_logger(__name__)


class YCombinatorCrawler(BaseCrawler):
    """
    Crawler for Y Combinator Directory.

    Source: https://www.ycombinator.com/companies
    """

    source_name = "ycombinator"
    base_url = "https://www.ycombinator.com"
    allowed_domains = ["www.ycombinator.com", "ycombinator.com"]

    def __init__(self, http_client: Optional[AsyncHttpClient] = None):
        self.http_client = http_client
        self._soup: Optional[BeautifulSoup] = None

    async def discover(self) -> List[str]:
        """
        Discover startup URLs from YC Directory.

        Returns:
            List of startup detail page URLs
        """
        logger.info("Discovering YC Directory startups")

        # Main directory page
        start_url = urljoin(self.base_url, "/companies")

        try:
            async with AsyncHttpClient() as client:
                request = CrawlRequest(
                    url=start_url,
                    source_name=self.source_name,
                )
                response = await client.fetch(request)

                if response.status_code != 200:
                    logger.error(
                        "Failed to fetch YC Directory",
                        status=response.status_code,
                        url=start_url,
                    )
                    return []

                soup = BeautifulSoup(response.body, "html.parser")
                self._soup = soup

                # Find all company links
                # YC Directory has links like: /companies?company=123-company-name
                urls = []
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if "/companies?company=" in href:
                        full_url = urljoin(self.base_url, href)
                        urls.append(full_url)

                logger.info(f"Discovered {len(urls)} YC startup URLs")
                return urls

        except Exception as e:
            logger.error("YC discovery failed", error=str(e))
            return []

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch a YC company page."""
        if self.http_client is None:
            async with AsyncHttpClient() as client:
                return await client.fetch(request)
        return await self.http_client.fetch(request)

    async def parse(self, response: CrawlResponse) -> List[Dict[str, Any]]:
        """
        Parse YC company page into structured data.

        Returns:
            List of startup data dictionaries
        """
        if response.status_code != 200:
            logger.warning(
                "Non-200 status",
                url=response.url,
                status=response.status_code,
            )
            return []

        soup = BeautifulSoup(response.body, "html.parser")

        # Extract company data from the page
        company_data = self._extract_company_data(soup, response.url)

        if company_data:
            # Add provenance
            company_data["provenance"] = {
                "content_hash": hasher.hash_bytes(response.body),
                "source_url": response.url,
                "source_name": self.source_name,
            }

        return [company_data] if company_data else []

    def _extract_company_data(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extract company data from YC company page."""
        try:
            # Extract company name
            name_elem = soup.find("h1") or soup.find(class_=re.compile("company-name"))
            name = name_elem.get_text(strip=True) if name_elem else None

            if not name:
                return None

            # Extract description
            desc_elem = soup.find(class_=re.compile("description|about|bio"))
            description = desc_elem.get_text(strip=True) if desc_elem else None

            # Extract website
            website_elem = soup.find("a", href=True, string=re.compile("www\.|http"))
            website = website_elem["href"] if website_elem else None

            # Extract employee count (if available)
            employee_elem = soup.find(string=re.compile("employees?|team size"))
            employee_count = None

            # Extract batch (season)
            batch_elem = soup.find(string=re.compile("[Ss]ummer|[Ww]inter\s+\d{4}"))
            batch = batch_elem.strip() if batch_elem else None

            # Extract location
            location_elem = soup.find(string=re.compile("[Ll]ocation"))
            location = None

            return {
                "entity_name": name,
                "description": description,
                "website": website,
                "employee_count": employee_count,
                "batch": batch,
                "location": location,
                "source_url": url,
                "source_name": self.source_name,
            }
        except Exception as e:
            logger.warning("Failed to extract YC company data", error=str(e), url=url)
            return None
