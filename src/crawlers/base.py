"""
SignalAtlas Async HTTP Client

Provides a production-ready async HTTP client with:
- Timeout configuration
- Bounded concurrency
- Per-domain rate limiting
- Retry policy with exponential backoff + jitter
- Response size guard
- Structured logging
- Content hashing
"""

import asyncio
import hashlib
import random
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientResponse, ClientSession, ClientTimeout, TCPConnector
from structlog import get_logger

from ..config import settings

logger = get_logger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class HTTPConfig:
    """HTTP client configuration."""
    timeout_seconds: int = 30
    max_concurrent_connections: int = 100
    max_per_domain: int = 5
    retry_attempts: int = 3
    max_response_size: int = 10 * 1024 * 1024  # 10MB
    user_agent: str = "SignalAtlas/1.0 (+https://github.com/frontieratlas/signal-atlas)"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class CrawlRequest:
    """Request to fetch a URL."""
    url: str
    source_name: str
    headers: Optional[Dict[str, str]] = None
    method: str = "GET"
    data: Optional[Any] = None
    params: Optional[Dict[str, Any]] = None


@dataclass
class CrawlResponse:
    """Response from a crawl request."""
    url: str
    status_code: int
    content_type: str
    body: bytes
    headers: Dict[str, str] = field(default_factory=dict)
    source_name: str = ""
    fetch_duration: float = 0.0
    attempt: int = 0


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a domain."""
    max_requests: int
    window_seconds: float
    current_requests: int = 0
    window_start: float = 0.0


# ============================================================================
# Exceptions
# ============================================================================

class HTTPError(Exception):
    """Base HTTP error."""
    pass


class TimeoutError(HTTPError):
    """Request timeout."""
    pass


class RateLimitError(HTTPError):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class PayloadTooLargeError(HTTPError):
    """Response payload too large."""
    pass


class TooManyRedirectsError(HTTPError):
    """Too many redirects."""
    pass


# ============================================================================
# Domain Rate Limiter
# ============================================================================

class DomainRateLimiter:
    """
    Per-domain rate limiter using token bucket algorithm.

    Usage:
        limiter = DomainRateLimiter(max_per_domain=5, window_seconds=1.0)
        await limiter.wait("example.com")
    """

    def __init__(
        self,
        max_per_domain: int = 5,
        window_seconds: float = 1.0,
    ):
        self.max_per_domain = max_per_domain
        self.window_seconds = window_seconds
        self._lock = asyncio.Lock()
        self._domains: Dict[str, RateLimitConfig] = {}

    async def wait(self, domain: str) -> None:
        """Wait if rate limit is exceeded for domain."""
        async with self._lock:
            now = time.time()
            config = self._domains.get(domain)

            if config is None:
                config = RateLimitConfig(
                    max_requests=self.max_per_domain,
                    window_seconds=self.window_seconds,
                    current_requests=0,
                    window_start=now,
                )
                self._domains[domain] = config

            # Reset window if expired
            if now - config.window_start > config.window_seconds:
                config.current_requests = 0
                config.window_start = now

            # Check if we can make request
            if config.current_requests >= config.max_requests:
                wait_time = config.window_start + config.window_seconds - now
                if wait_time > 0:
                    logger.debug(
                        "Rate limit wait",
                        domain=domain,
                        wait_seconds=f"{wait_time:.2f}",
                        requests=config.current_requests,
                        max_requests=config.max_requests,
                    )
                    await asyncio.sleep(wait_time)
                    # Reset after waiting
                    config.current_requests = 0
                    config.window_start = time.time()

            config.current_requests += 1

    def get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split("/")[0] or "unknown"


# ============================================================================
# Retry Policy
# ============================================================================

class RetryPolicy:
    """
    Exponential backoff with jitter retry policy.

    Retries on:
    - 408 (Request Timeout)
    - 429 (Too Many Requests)
    - 5xx (Server Errors)
    - Connection errors
    - Timeout errors

    Does NOT retry on:
    - 400 (Bad Request)
    - 401 (Unauthorized)
    - 403 (Forbidden)
    - 404 (Not Found)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def should_retry(self, status_code: Optional[int], exception: Optional[Exception]) -> bool:
        """Determine if request should be retried."""
        if exception is not None:
            # Retry on connection/timeout errors
            if isinstance(exception, (aiohttp.ClientError, asyncio.TimeoutError)):
                return True
            return False

        if status_code is None:
            return False

        # Retry on these status codes
        if status_code in {408, 429, 500, 502, 503, 504}:
            return True

        return False

    def get_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate delay before next retry."""
        if retry_after is not None:
            return min(retry_after, self.max_delay)

        # Exponential backoff: base_delay * 2^attempt
        delay = self.base_delay * (2 ** attempt)

        # Add jitter (random value between 0 and 1 second)
        if self.jitter:
            delay += random.uniform(0, 1)

        return min(delay, self.max_delay)


# ============================================================================
# Content Hasher
# ============================================================================

class ContentHasher:
    """Generate SHA-256 hashes for content."""

    @staticmethod
    def hash_bytes(content: bytes) -> str:
        """Generate SHA-256 hash of bytes."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def hash_text(text: str, encoding: str = "utf-8") -> str:
        """Generate SHA-256 hash of text."""
        return hashlib.sha256(text.encode(encoding)).hexdigest()


# ============================================================================
# Async HTTP Client
# ============================================================================

class AsyncHttpClient:
    """
    Production-ready async HTTP client.

    Features:
    - Connection pooling
    - Per-domain rate limiting
    - Exponential backoff retries
    - Response size limits
    - Structured logging
    - Content hashing

    Usage:
        async with AsyncHttpClient() as client:
            response = await client.fetch(CrawlRequest(url="https://example.com"))
    """

    def __init__(
        self,
        config: Optional[HTTPConfig] = None,
        rate_limiter: Optional[DomainRateLimiter] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self.config = config or HTTPConfig()
        self.rate_limiter = rate_limiter or DomainRateLimiter(
            max_per_domain=self.config.max_per_domain,
            window_seconds=1.0,
        )
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=self.config.retry_attempts,
        )
        self.hasher = ContentHasher()
        self._session: Optional[ClientSession] = None
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_connections)

    async def __aenter__(self) -> "AsyncHttpClient":
        self._session = ClientSession(
            timeout=ClientTimeout(total=self.config.timeout_seconds),
            connector=TCPConnector(
                limit=self.config.max_concurrent_connections,
                limit_per_host=self.config.max_per_domain,
                force_close=True,
            ),
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session:
            await self._session.close()

    async def fetch(self, request: CrawlRequest) -> CrawlResponse:
        """
        Fetch a URL with retry logic and rate limiting.

        Args:
            request: CrawlRequest with URL and optional headers

        Returns:
            CrawlResponse with status, body, headers, etc.

        Raises:
            HTTPError: On unrecoverable errors
        """
        domain = self.rate_limiter.get_domain(request.url)
        start_time = time.time()

        last_exception: Optional[Exception] = None
        retry_after: Optional[float] = None

        for attempt in range(self.config.retry_attempts):
            try:
                # Wait for rate limit
                await self.rate_limiter.wait(domain)

                # Wait for semaphore (bounded concurrency)
                async with self._semaphore:
                    # Rate limit again (in case we waited)
                    await self.rate_limiter.wait(domain)

                    response = await self._do_request(request, attempt)
                    return response

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                logger.warning(
                    "HTTP request failed",
                    url=request.url,
                    attempt=attempt + 1,
                    error=str(e),
                    source=request.source_name,
                )

                if not self.retry_policy.should_retry(None, e):
                    raise HTTPError(f"Request failed: {e}") from e

                retry_after = self._get_retry_after(e)
                delay = self.retry_policy.get_delay(attempt, retry_after)
                logger.info(
                    "Retrying after delay",
                    url=request.url,
                    attempt=attempt + 1,
                    delay=f"{delay:.2f}s",
                    source=request.source_name,
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        raise HTTPError(f"Max retries exceeded for {request.url}: {last_exception}")

    async def _do_request(self, request: CrawlRequest, attempt: int) -> CrawlResponse:
        """Execute a single HTTP request."""
        start_time = time.time()

        # Build request headers
        headers = {
            "User-Agent": self.config.user_agent,
        }
        if request.headers:
            headers.update(request.headers)

        try:
            async with self._session.request(
                method=request.method,
                url=request.url,
                headers=headers,
                data=request.data,
                params=request.params,
                allow_redirects=True,
                max_redirects=10,
            ) as response:
                # Check for too many redirects
                if response.history and len(response.history) >= 10:
                    raise TooManyRedirectsError(f"Too many redirects for {request.url}")

                # Check status code
                if response.status == 429:
                    retry_after = self._parse_retry_after(response)
                    raise RateLimitError(
                        f"Rate limited: {request.url}",
                        retry_after=retry_after,
                    )

                # Read response body with size limit
                body = await self._read_body(response)

                # Check response size
                if len(body) > self.config.max_response_size:
                    raise PayloadTooLargeError(
                        f"Response too large: {len(body)} bytes > {self.config.max_response_size}"
                    )

                fetch_duration = time.time() - start_time

                logger.debug(
                    "HTTP request completed",
                    url=request.url,
                    status=response.status,
                    size=len(body),
                    duration=f"{fetch_duration:.2f}s",
                    attempt=attempt + 1,
                    source=request.source_name,
                )

                return CrawlResponse(
                    url=str(response.url),
                    status_code=response.status,
                    content_type=response.content_type or "",
                    body=body,
                    headers=dict(response.headers),
                    source_name=request.source_name,
                    fetch_duration=fetch_duration,
                    attempt=attempt + 1,
                )

        except asyncio.TimeoutError:
            raise TimeoutError(f"Request timeout for {request.url}")

    async def _read_body(self, response: ClientResponse) -> bytes:
        """Read response body with size checking."""
        body = bytearray()
        async for chunk in response.content.iter_chunked(8192):
            body.extend(chunk)
            if len(body) > self.config.max_response_size:
                break
        return bytes(body)

    def _parse_retry_after(self, response: ClientResponse) -> Optional[float]:
        """Parse Retry-After header from response."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return None

    def _get_retry_after(self, exception: Exception) -> Optional[float]:
        """Extract retry_after from exception if available."""
        if isinstance(exception, RateLimitError):
            return exception.retry_after
        return None


# ============================================================================
# Singleton Client
# ============================================================================

_http_client: Optional[AsyncHttpClient] = None


async def get_http_client() -> AsyncHttpClient:
    """Get or create singleton HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = AsyncHttpClient()
        await _http_client.__aenter__()
    return _http_client


async def close_http_client() -> None:
    """Close singleton HTTP client."""
    global _http_client
    if _http_client is not None:
        await _http_client.__aexit__(None, None, None)
        _http_client = None
