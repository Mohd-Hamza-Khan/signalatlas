"""
arXiv Crawler

Crawls arXiv for research paper metadata.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from structlog import get_logger

from ..crawlers import BaseCrawler, CrawlRequest, CrawlResponse
from ..crawlers.base import AsyncHttpClient
from ..utils.hashing import hasher

logger = get_logger(__name__)


class ArXivCrawler(BaseCrawler):
    """
    Crawler for arXiv research papers.

    Source: https://arxiv.org
    Uses: arXiv API (preferred) and HTML scraping (fallback)
    """

    source_name = "arxiv"
    base_url = "https://arxiv.org"
    api_url = "http://export.arxiv.org/api/query"
    allowed_domains = ["arxiv.org", "export.arxiv.org"]

    def __init__(self, http_client: Optional[AsyncHttpClient] = None):
        self.http_client = http_client

    async def discover(self) -> List[str]:
        """
        Discover recent arXiv papers.

        Uses arXiv API to find recent papers in AI/ML categories.
        """
        logger.info("Discovering arXiv papers")

        # Use arXiv API for structured data
        urls = await self._discover_from_api()
        if urls:
            return urls

        # Fallback to HTML scraping
        return await self._discover_from_html()

    async def _discover_from_api(self) -> List[str]:
        """Discover papers using arXiv API."""
        # Query for recent AI/ML papers
        # Categories: cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, stat.ML
        params = {
            "search_query": "cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV OR cat:cs.NE OR cat:stat.ML",
            "start": 0,
            "max_results": 100,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            async with AsyncHttpClient() as client:
                request = CrawlRequest(
                    url=self.api_url,
                    source_name=self.source_name,
                    params=params,
                )
                response = await client.fetch(request)

                if response.status_code == 200:
                    return self._parse_api_response(response.body)

        except Exception as e:
            logger.debug("arXiv API discovery failed", error=str(e))

        return []

    def _parse_api_response(self, body: bytes) -> List[str]:
        """Parse arXiv API XML response."""
        urls = []
        try:
            root = ET.fromstring(body)
            # Find all entry elements
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                # Extract ID
                id_elem = entry.find("{http://www.w3.org/2005/Atom}id")
                if id_elem is not None and id_elem.text:
                    # arXiv ID format: http://arxiv.org/abs/1234.5678
                    arxiv_id = id_elem.text.replace("http://arxiv.org/abs/", "")
                    url = urljoin(self.base_url, f"/abs/{arxiv_id}")
                    urls.append(url)

            logger.info(f"Discovered {len(urls)} papers from arXiv API")
        except Exception as e:
            logger.error("Failed to parse arXiv API response", error=str(e))

        return urls

    async def _discover_from_html(self) -> List[str]:
        """Discover papers by scraping arXiv HTML."""
        urls = []
        try:
            async with AsyncHttpClient() as client:
                # Try recent papers page
                recent_url = urljoin(self.base_url, "/list/cs/new")
                request = CrawlRequest(url=recent_url, source_name=self.source_name)
                response = await client.fetch(request)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.body, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        if "/abs/" in href or "/pdf/" in href:
                            full_url = urljoin(self.base_url, href)
                            urls.append(full_url)

                    logger.info(f"Discovered {len(urls)} papers from HTML")

        except Exception as e:
            logger.error("HTML discovery failed", error=str(e))

        return urls

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch an arXiv paper page."""
        if self.http_client is None:
            async with AsyncHttpClient() as client:
                return await client.fetch(request)
        return await self.http_client.fetch(request)

    async def parse(self, response: CrawlResponse) -> List[Dict[str, Any]]:
        """
        Parse arXiv paper page into structured data.

        Returns:
            List of paper data dictionaries
        """
        if response.status_code != 200:
            return []

        # Try to extract from HTML
        paper_data = self._extract_html_data(response.body, response.url)

        if paper_data:
            paper_data["provenance"] = {
                "content_hash": hasher.hash_bytes(response.body),
                "source_url": response.url,
                "source_name": self.source_name,
            }

        return [paper_data] if paper_data else []

    def _extract_html_data(self, body: bytes, url: str) -> Optional[Dict[str, Any]]:
        """Extract paper data from HTML."""
        soup = BeautifulSoup(body, "html.parser")

        try:
            # Extract title
            title_elem = soup.find("h1", class_=re.compile("title|paper-title"))
            title = title_elem.get_text(strip=True) if title_elem else None

            if not title:
                return None

            # Extract arXiv ID from URL
            arxiv_id = self._extract_arxiv_id(url)

            # Extract authors
            authors = self._extract_authors(soup)

            # Extract abstract
            abstract_elem = soup.find(class_=re.compile("abstract|mathjax"))
            abstract = abstract_elem.get_text(strip=True) if abstract_elem else None

            # Extract published date
            date_elem = soup.find(class_=re.compile("date|submitted"))
            published_date = self._parse_date(date_elem) if date_elem else None

            # Extract PDF URL
            pdf_elem = soup.find("a", href=True, string=re.compile("[Pp]DF|pdf"))
            pdf_url = pdf_elem["href"] if pdf_elem else None
            if pdf_url and not pdf_url.startswith("http"):
                pdf_url = urljoin(self.base_url, pdf_url)

            # Extract primary category
            category_elem = soup.find(class_=re.compile("category|subject"))
            category = category_elem.get_text(strip=True) if category_elem else None

            return {
                "title": title,
                "authors": authors,
                "paper_url": url,
                "external_id": arxiv_id,
                "abstract": abstract,
                "published_date": published_date,
                "pdf_url": pdf_url,
                "category": category,
                "source_url": url,
                "source_name": self.source_name,
            }
        except Exception as e:
            logger.warning("Failed to extract arXiv data", error=str(e), url=url)
            return None

    def _extract_arxiv_id(self, url: str) -> Optional[str]:
        """Extract arXiv ID from URL."""
        # URL formats: https://arxiv.org/abs/1234.5678 or https://arxiv.org/pdf/1234.5678
        match = re.search(r"/(abs|pdf)/([0-9]+\.[0-9]+)", url)
        if match:
            return match.group(2)
        return None

    def _extract_authors(self, soup: BeautifulSoup) -> List[str]:
        """Extract author names from page."""
        authors = []
        author_elems = soup.find_all(class_=re.compile("authors|author"))
        for elem in author_elems:
            author_text = elem.get_text(strip=True)
            # Split by common separators
            for part in re.split(r"[;,]", author_text):
                part = part.strip()
                if part and len(part) < 100:
                    authors.append(part)
        return authors

    def _parse_date(self, elem) -> Optional[str]:
        """Parse date from element."""
        if not elem:
            return None

        date_text = elem.get_text(strip=True)
        if not date_text:
            return None

        # Try to parse various date formats
        # "Submitted on 15 Aug 2026"
        # "15 Aug 2026"
        # "Aug 15, 2026"
        for fmt in ["%d %b %Y", "%b %d, %Y", "%Y-%m-%d", "%d-%b-%Y"]:
            try:
                dt = datetime.strptime(date_text, fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue

        return None
