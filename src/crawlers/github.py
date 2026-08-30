"""
SignalAtlas GitHub Crawler

Provides GitHub API integration for:
- Repository verification
- Star count fetching
- Repository search
- Rate limit handling
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from structlog import get_logger

from ..config import settings
from ..crawlers import BaseCrawler, CrawlRequest, CrawlResponse
from ..utils.retry import retry_async, HTTP_RETRY
from ..utils.hashing import hasher

logger = get_logger(__name__)


class GitHubCrawler(BaseCrawler):
    """
    Crawler for GitHub API.

    Features:
    - Repository verification
    - Star count fetching
    - Rate limit handling
    - Caching
    """

    source_name = "github"
    base_url = "https://api.github.com"
    max_depth = 1

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._rate_limit_remaining: int = 5000
        self._rate_limit_reset: Optional[datetime] = None

    async def __aenter__(self) -> "GitHubCrawler":
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

        self._session = aiohttp.ClientSession(
            base_url=self.base_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session:
            await self._session.close()

    async def discover(self) -> List[str]:
        """
        Discover is not applicable for GitHub crawler.
        GitHub URLs are extracted from paper content.
        """
        return []

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """Fetch a GitHub API URL."""
        if not self._session:
            await self.__aenter__()

        # Check rate limit
        await self._check_rate_limit()

        try:
            async with self._session.get(request.url) as response:
                # Update rate limit info
                self._update_rate_limit(response)

                if response.status == 403:
                    # Check if it's rate limit
                    reset_time = response.headers.get("X-RateLimit-Reset")
                    if reset_time:
                        raise RateLimitError(
                            "GitHub rate limit exceeded",
                            retry_after=float(reset_time),
                        )

                response.raise_for_status()
                body = await response.read()

                return CrawlResponse(
                    url=str(response.url),
                    status_code=response.status,
                    content_type=response.content_type or "",
                    body=body,
                    headers=dict(response.headers),
                )

        except aiohttp.ClientError as e:
            raise Exception(f"GitHub API error: {e}")

    async def parse(self, response: CrawlResponse) -> List[Dict[str, Any]]:
        """Parse GitHub API response."""
        try:
            data = json.loads(response.body)
            return [data]
        except json.JSONDecodeError:
            return []

    async def _check_rate_limit(self) -> None:
        """Check and wait for rate limit if needed."""
        if self._rate_limit_remaining <= 10:
            if self._rate_limit_reset:
                wait_time = (self._rate_limit_reset - datetime.now()).total_seconds()
                if wait_time > 0:
                    logger.warning(
                        "GitHub rate limit approaching, waiting",
                        wait_seconds=f"{wait_time:.1f}",
                    )
                    await asyncio.sleep(wait_time + 1)
                    self._rate_limit_remaining = 5000

    def _update_rate_limit(self, response: aiohttp.ClientResponse) -> None:
        """Update rate limit info from response headers."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")

        if remaining:
            self._rate_limit_remaining = int(remaining)
        if reset:
            self._rate_limit_reset = datetime.fromtimestamp(int(reset))

    async def get_repository(self, repo_url: str) -> Optional[Dict[str, Any]]:
        """
        Get repository information.

        Args:
            repo_url: GitHub repository URL

        Returns:
            Repository data or None if not found
        """
        # Normalize URL
        repo_url = self.normalize_repo_url(repo_url)

        # Check cache
        if repo_url in self._cache:
            return self._cache[repo_url]

        # Build API URL
        api_url = self._build_api_url(repo_url)

        try:
            request = CrawlRequest(url=api_url, source_name=self.source_name)
            response = await self.fetch(request)
            repos = await self.parse(response)

            if repos:
                repo = repos[0]
                self._cache[repo_url] = repo
                return repo

        except Exception as e:
            logger.warning(
                "Failed to get repository",
                url=repo_url,
                error=str(e),
            )

        return None

    async def verify_repository(self, repo_url: str) -> bool:
        """
        Verify that a repository exists.

        Args:
            repo_url: GitHub repository URL

        Returns:
            True if repository exists
        """
        repo = await self.get_repository(repo_url)
        return repo is not None

    async def get_star_count(self, repo_url: str) -> Optional[int]:
        """
        Get the star count for a repository.

        Args:
            repo_url: GitHub repository URL

        Returns:
            Number of stars or None
        """
        repo = await self.get_repository(repo_url)
        if repo:
            return repo.get("stargazers_count")
        return None

    async def search_repositories(
        self,
        query: str,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search GitHub repositories.

        Args:
            query: Search query
            per_page: Results per page

        Returns:
            List of repository data
        """
        api_url = f"{self.base_url}/search/repositories"
        params = {
            "q": query,
            "per_page": per_page,
        }

        try:
            if not self._session:
                await self.__aenter__()

            await self._check_rate_limit()

            async with self._session.get(api_url, params=params) as response:
                self._update_rate_limit(response)
                response.raise_for_status()
                data = json.loads(await response.read())
                return data.get("items", [])

        except Exception as e:
            logger.warning(
                "GitHub search failed",
                query=query,
                error=str(e),
            )
            return []

    def normalize_repo_url(self, url: str) -> str:
        """
        Normalize a GitHub repository URL.

        Converts various formats to: https://github.com/owner/repo
        """
        url = url.strip()

        # Remove .git suffix
        if url.endswith(".git"):
            url = url[:-4]

        # Add https:// if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Parse URL
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)

        # Normalize netloc
        netloc = parsed.netloc.lower()
        if netloc == "www.github.com":
            netloc = "github.com"
        parsed = parsed._replace(netloc=netloc)

        # Normalize path
        path = parsed.path.strip("/")
        parsed = parsed._replace(path=path)

        # Rebuild
        return urlunparse(parsed)

    def _build_api_url(self, repo_url: str) -> str:
        """Build GitHub API URL from repository URL."""
        from urllib.parse import urlparse

        parsed = urlparse(repo_url)
        if parsed.netloc == "github.com":
            path = parsed.path.strip("/")
            return f"{self.base_url}/repos/{path}"
        return repo_url

    def extract_repo_urls(self, text: str) -> List[str]:
        """
        Extract potential GitHub repository URLs from text.

        Args:
            text: Text to search

        Returns:
            List of potential repository URLs
        """
        # Pattern for GitHub URLs
        patterns = [
            # Full URL
            r"https?://(?:www\.)?github\.com/([a-zA-Z0-9-]+/[a-zA-Z0-9_.-]+)(?:\.git)?",
            # Without scheme
            r"github\.com/([a-zA-Z0-9-]+/[a-zA-Z0-9_.-]+)(?:\.git)?",
            # Short form
            r"([a-zA-Z0-9-]+/[a-zA-Z0-9_.-]+)",
        ]

        urls = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                url = match[0] if isinstance(match, tuple) else match
                # Skip if it's just a domain
                if "/" not in url:
                    continue
                urls.append(f"https://github.com/{url}")

        # Deduplicate
        return list(set(urls))


# Singleton instance
github_crawler = GitHubCrawler()
