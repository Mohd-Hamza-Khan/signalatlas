"""
SignalAtlas URL Normalization

Provides utilities for normalizing URLs for deduplication.
"""

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse, ParseResult

from structlog import get_logger

logger = get_logger(__name__)


class URLNormalizer:
    """
    Normalizes URLs for consistent comparison and deduplication.
    """

    @staticmethod
    def normalize(url: str) -> str:
        """
        Normalize a URL for comparison.

        Normalizations applied:
        - Lowercase scheme and netloc
        - Remove fragment
        - Remove trailing slash (except for root)
        - Remove default port
        - Sort query parameters
        - Remove empty query parameters
        - Remove www. prefix
        """
        if not url or not url.strip():
            return ""

        try:
            parsed = urlparse(url)

            # Lowercase scheme and netloc
            parsed = parsed._replace(
                scheme=parsed.scheme.lower(),
                netloc=parsed.netloc.lower(),
            )

            # Remove fragment
            parsed = parsed._replace(fragment="")

            # Remove www. prefix
            netloc = parsed.netloc
            if netloc.startswith("www."):
                netloc = netloc[4:]
            parsed = parsed._replace(netloc=netloc)

            # Remove default ports
            if parsed.scheme == "http" and parsed.port == 80:
                parsed = parsed._replace(port=None)
            elif parsed.scheme == "https" and parsed.port == 443:
                parsed = parsed._replace(port=None)

            # Normalize path
            path = parsed.path
            if path and path != "/" and path.endswith("/"):
                path = path.rstrip("/")
            parsed = parsed._replace(path=path)

            # Sort and clean query parameters
            if parsed.query:
                query = URLNormalizer._normalize_query(parsed.query)
                parsed = parsed._replace(query=query)

            # Rebuild URL
            normalized = urlunparse(parsed)

            return normalized

        except Exception as e:
            logger.warning("Failed to normalize URL", url=url, error=str(e))
            return url.lower()

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize query string."""
        from urllib.parse import parse_qs, urlencode

        # Parse query string
        params = parse_qs(query, keep_blank_values=True)

        # Remove empty values
        params = {k: v for k, v in params.items() if v}

        # Sort parameters alphabetically
        sorted_params = sorted(params.items())

        # Rebuild query string
        return urlencode(sorted_params, doseq=True)

    @staticmethod
    def get_domain(url: str) -> str:
        """Extract domain from URL."""
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]

            return domain
        except Exception:
            return ""

    @staticmethod
    def is_valid(url: str) -> bool:
        """Check if URL is valid."""
        if not url or not url.strip():
            return False

        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def fix_url(url: str) -> str:
        """Attempt to fix a malformed URL."""
        if not url:
            return ""

        # Add https:// if missing scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)

            # Ensure scheme
            if not parsed.scheme:
                parsed = parsed._replace(scheme="https")

            # Ensure netloc
            if not parsed.netloc:
                # Try to extract from path
                path_parts = parsed.path.split("/")
                if path_parts and path_parts[0]:
                    parsed = parsed._replace(
                        netloc=path_parts[0],
                        path="/".join(path_parts[1:]),
                    )

            return urlunparse(parsed)

        except Exception:
            return url

    @staticmethod
    def get_base_url(url: str) -> str:
        """Get base URL (scheme + netloc)."""
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return ""

    @staticmethod
    def get_path(url: str) -> str:
        """Get path from URL."""
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            return parsed.path
        except Exception:
            return ""


# Singleton instance
url_normalizer = URLNormalizer()
