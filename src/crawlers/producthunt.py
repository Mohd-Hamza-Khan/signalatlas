"""
Product Hunt Crawler

Crawls Product Hunt for product data using their API or HTML.
"""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from structlog import get_logger

from ..crawlers import BaseCrawler, CrawlRequest, CrawlResponse
from ..crawlers.base import AsyncHttpClient
from ..utils.hashing import hasher

logger = get_logger(__name__)


class ProductHuntCrawler(BaseCrawler):
    """
    Crawler for Product Hunt.

    Source: https://www.producthunt.com
    """

    source_name = "producthunt"
    base_url = "https://www.producthunt.com"
    allowed_domains = ["www.producthunt.com", "producthunt.com"]

    def __init__(self, http_client: Optional[AsyncHttpClient] = None):
        self.http_client = http_client

    async def discover(self) -> List[str]:
        """
        Discover product URLs from Product Hunt.

        Uses the /newest page to find recent products.
        """
        logger.info("Discovering Product Hunt products")

        # Try API first, fall back to HTML
        urls = await self._discover_from_api()
        if urls:
            return urls

        return await self._discover_from_html()

    async def _discover_from_api(self) -> List[str]:
        """Discover products using Product Hunt API."""
        # Product Hunt has a GraphQL API
        api_url = "https://api.producthunt.com/v2/api/graphql"
        query = """
        query {
            posts(first: 100, order: NEWEST) {
                edges {
                    node {
                        id
                        name
                        url
                        slug
                    }
                }
            }
        }
        """

        try:
            async with AsyncHttpClient() as client:
                request = CrawlRequest(
                    url=api_url,
                    source_name=self.source_name,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    method="POST",
                    data=json.dumps({"query": query}),
                )
                response = await client.fetch(request)

                if response.status_code == 200:
                    data = json.loads(response.body)
                    urls = []
                    for edge in data.get("data", {}).get("posts", {}).get("edges", []):
                        node = edge.get("node", {})
                        if node.get("url"):
                            urls.append(node["url"])
                        elif node.get("slug"):
                            urls.append(urljoin(self.base_url, f"/posts/{node['slug']}"))
                    logger.info(f"Discovered {len(urls)} products from API")
                    return urls

        except Exception as e:
            logger.debug("API discovery failed", error=str(e))

        return []

    async def _discover_from_html(self) -> List[str]:
        """Discover products by scraping HTML."""
        urls = []
        try:
            async with AsyncHttpClient() as client:
                # Try newest page
                newest_url = urljoin(self.base_url, "/newest")
                request = CrawlRequest(url=newest_url, source_name=self.source_name)
                response = await client.fetch(request)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.body, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        if "/posts/" in href:
                            full_url = urljoin(self.base_url, href)
                            urls.append(full_url)

                    logger.info(f"Discovered {len(urls)} products from HTML")

        except Exception as e:
            logger.error("HTML discovery failed", error=str(e))

        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch a Product Hunt product page."""
        if self.http_client is None:
            async with AsyncHttpClient() as client:
                return await client.fetch(request)
        return await self.http_client.fetch(request)

    async def parse(self, response: CrawlResponse) -> List[Dict[str, Any]]:
        """
        Parse Product Hunt product page into structured data.

        Returns:
            List of product data dictionaries
        """
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.body, "html.parser")

        # Try to extract JSON-LD data first
        product_data = self._extract_json_ld(soup)
        if not product_data:
            product_data = self._extract_html_data(soup, response.url)

        if product_data:
            product_data["provenance"] = {
                "content_hash": hasher.hash_bytes(response.body),
                "source_url": response.url,
                "source_name": self.source_name,
            }

        return [product_data] if product_data else []

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract product data from JSON-LD."""
        script = soup.find("script", type="application/ld+json")
        if script:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            return self._normalize_product_data(item)
            except (json.JSONDecodeError, AttributeError):
                pass
        return None

    def _extract_html_data(self, soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
        """Extract product data from HTML."""
        try:
            # Extract product name
            name_elem = soup.find("h1") or soup.find(class_=re.compile("title|name"))
            name = name_elem.get_text(strip=True) if name_elem else None

            if not name:
                return None

            # Extract description
            desc_elem = soup.find(class_=re.compile("description|tagline"))
            description = desc_elem.get_text(strip=True) if desc_elem else None

            # Extract website
            website_elem = soup.find("a", href=True, string=re.compile("Visit|Website"))
            website = website_elem["href"] if website_elem else None

            # Extract pricing
            pricing_elem = soup.find(string=re.compile("[Pp]ricing|[Cc]ost|[Ff]ree"))
            pricing = pricing_elem.strip() if pricing_elem else None

            # Extract votes/upvotes
            votes_elem = soup.find(class_=re.compile("votes|upvotes"))
            upvotes = None
            if votes_elem:
                votes_text = votes_elem.get_text(strip=True)
                upvotes = self._extract_number(votes_text)

            # Extract category/tags
            tags = []
            for tag_elem in soup.find_all(class_=re.compile("tag|category")):
                tag_text = tag_elem.get_text(strip=True)
                if tag_text and len(tag_text) < 50:
                    tags.append(tag_text)

            return {
                "product_name": name,
                "description": description,
                "website": website,
                "pricing_model": self._normalize_pricing(pricing),
                "upvotes": upvotes,
                "tags": tags,
                "source_url": url,
                "source_name": self.source_name,
            }
        except Exception as e:
            logger.warning("Failed to extract Product Hunt data", error=str(e), url=url)
            return None

    def _normalize_product_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize JSON-LD data to our schema."""
        return {
            "product_name": data.get("name"),
            "description": data.get("description"),
            "website": data.get("url"),
            "pricing_model": self._normalize_pricing(data.get("offers", {}).get("price")),
            "source_url": data.get("url") or data.get("@id"),
            "source_name": self.source_name,
        }

    def _normalize_pricing(self, pricing: Optional[str]) -> Optional[str]:
        """Normalize pricing to our enum values."""
        if not pricing:
            return None
        pricing_lower = pricing.lower()
        if "free" in pricing_lower:
            return "FREE"
        if "freemium" in pricing_lower:
            return "FREEMIUM"
        if "paid" in pricing_lower or "premium" in pricing_lower:
            return "PAID"
        return None

    def _extract_number(self, text: str) -> Optional[int]:
        """Extract first number from text."""
        match = re.search(r"\d+", text)
        if match:
            return int(match.group())
        return None
