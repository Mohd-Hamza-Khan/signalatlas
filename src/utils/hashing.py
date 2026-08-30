"""
SignalAtlas Hashing Utilities

Provides content hashing for deduplication and idempotency.
"""

import hashlib
from typing import Any, Dict, Optional


class ContentHasher:
    """
    Generate consistent hashes for content deduplication.

    Uses SHA-256 for content hashing.
    """

    @staticmethod
    def hash_bytes(content: bytes) -> str:
        """Generate SHA-256 hash of bytes."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def hash_text(text: str, encoding: str = "utf-8") -> str:
        """Generate SHA-256 hash of text."""
        return hashlib.sha256(text.encode(encoding)).hexdigest()

    @staticmethod
    def hash_dict(data: Dict[str, Any], sort_keys: bool = True) -> str:
        """
        Generate hash of a dictionary.

        Useful for hashing structured data like parsed entities.
        """
        import json
        text = json.dumps(data, sort_keys=sort_keys, default=str)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_url(url: str) -> str:
        """
        Generate hash of a URL.

        Normalizes URL before hashing for consistent deduplication.
        """
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        # Normalize
        parsed = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            fragment="",
        )
        if parsed.path and parsed.path != "/" and parsed.path.endswith("/"):
            parsed = parsed._replace(path=parsed.path.rstrip("/"))

        normalized = urlunparse(parsed)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# Singleton instance
hasher = ContentHasher()
