"""
SignalAtlas Date Normalization

Provides utilities for parsing and normalizing dates from various formats.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from dateutil import parser as dateutil_parser
from structlog import get_logger

logger = get_logger(__name__)


class DateNormalizer:
    """
    Normalizes dates from various formats to UTC datetime.

    Priority order:
    1. JSON-LD
    2. OpenGraph/meta tags
    3. <time datetime> elements
    4. Visible date text
    5. Relative date parser
    6. Content-change heuristic
    """

    @staticmethod
    def normalize(
        date_str: Optional[str],
        source: Optional[str] = None,
    ) -> Tuple[Optional[datetime], float]:
        """
        Normalize a date string to UTC datetime.

        Args:
            date_str: Date string to parse
            source: Source of the date (for confidence calculation)

        Returns:
            Tuple of (normalized_datetime, confidence)
        """
        if not date_str:
            return None, 0.0

        date_str = date_str.strip()

        # Try ISO 8601 first
        try:
            dt = DateNormalizer._parse_iso8601(date_str)
            if dt:
                return dt, 0.99
        except Exception:
            pass

        # Try common formats
        try:
            dt = DateNormalizer._parse_common_formats(date_str)
            if dt:
                return dt, 0.95
        except Exception:
            pass

        # Try relative dates
        try:
            dt = DateNormalizer._parse_relative(date_str)
            if dt:
                return dt, 0.85
        except Exception:
            pass

        # Try dateutil as fallback
        try:
            dt = dateutil_parser.parse(date_str, fuzzy=True)
            return DateNormalizer._to_utc(dt), 0.7
        except Exception:
            pass

        return None, 0.0

    @staticmethod
    def _parse_iso8601(date_str: str) -> Optional[datetime]:
        """Parse ISO 8601 date string."""
        from dateutil.parser import isoparse

        try:
            dt = isoparse(date_str)
            return DateNormalizer._to_utc(dt)
        except Exception:
            return None

    @staticmethod
    def _parse_common_formats(date_str: str) -> Optional[datetime]:
        """Parse common date formats."""
        formats = [
            # Full ISO with timezone
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            # ISO without timezone
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            # Date only
            "%Y-%m-%d",
            # US format
            "%m/%d/%Y",
            "%m-%d-%Y",
            # European format
            "%d/%m/%Y",
            "%d-%m-%Y",
            # With time
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            # Month names
            "%B %d, %Y",
            "%b %d, %Y",
            "%B %d %Y",
            "%b %d %Y",
            # With time
            "%B %d, %Y %H:%M:%S",
            "%b %d, %Y %H:%M:%S",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return DateNormalizer._to_utc(dt)
            except ValueError:
                continue

        return None

    @staticmethod
    def _parse_relative(date_str: str) -> Optional[datetime]:
        """Parse relative date strings."""
        now = datetime.now(timezone.utc)
        date_str = date_str.lower().strip()

        # Match patterns like "2 hours ago", "3 days ago", etc.
        match = re.match(
            r"^(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago$",
            date_str,
        )
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            if unit == "second":
                return now - timedelta(seconds=value)
            elif unit == "minute":
                return now - timedelta(minutes=value)
            elif unit == "hour":
                return now - timedelta(hours=value)
            elif unit == "day":
                return now - timedelta(days=value)
            elif unit == "week":
                return now - timedelta(weeks=value)
            elif unit == "month":
                return now - timedelta(days=value * 30)
            elif unit == "year":
                return now - timedelta(days=value * 365)

        # Match patterns like "yesterday", "today", "tomorrow"
        if date_str == "yesterday":
            return now - timedelta(days=1)
        elif date_str == "today":
            return now
        elif date_str == "tomorrow":
            return now + timedelta(days=1)

        # Match patterns like "2h ago", "3d ago"
        match = re.match(r"^(\d+)([hmdwy])\s+ago$", date_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            if unit == "h":
                return now - timedelta(hours=value)
            elif unit == "d":
                return now - timedelta(days=value)
            elif unit == "w":
                return now - timedelta(weeks=value)
            elif unit == "m":
                return now - timedelta(days=value * 30)
            elif unit == "y":
                return now - timedelta(days=value * 365)

        return None

    @staticmethod
    def _to_utc(dt: datetime) -> datetime:
        """Convert datetime to UTC."""
        if dt.tzinfo is None:
            # Assume UTC if no timezone
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def extract_from_html(html: str) -> List[Tuple[str, float]]:
        """
        Extract potential dates from HTML.

        Returns list of (date_string, confidence) tuples.
        """
        dates = []

        if not html:
            return dates

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")

        # Extract from <time datetime> elements
        time_elements = soup.find_all("time", datetime=True)
        for time_el in time_elements:
            datetime_str = time_el["datetime"]
            dt, confidence = DateNormalizer.normalize(datetime_str, "time_element")
            if dt:
                dates.append((datetime_str, confidence))

        # Extract from JSON-LD
        json_ld = soup.find_all(type="application/ld+json")
        for script in json_ld:
            if script.string:
                try:
                    import json
                    data = json.loads(script.string)
                    date_fields = ["datePublished", "dateCreated", "dateModified"]
                    for field in date_fields:
                        if field in data:
                            dt, confidence = DateNormalizer.normalize(
                                data[field], "json_ld"
                            )
                            if dt:
                                dates.append((data[field], confidence))
                except Exception:
                    pass

        # Extract from meta tags
        meta_tags = soup.find_all("meta")
        date_meta = [
            "published",
            "date",
            "pubdate",
            "published_time",
            "article:published_time",
        ]
        for tag in meta_tags:
            name = (tag.get("name") or tag.get("property") or "").lower()
            if name in date_meta and tag.get("content"):
                dt, confidence = DateNormalizer.normalize(
                    tag["content"], "meta_tag"
                )
                if dt:
                    dates.append((tag["content"], confidence))

        return dates

    @staticmethod
    def extract_from_text(text: str) -> List[Tuple[str, float]]:
        """
        Extract potential dates from plain text.

        Returns list of (date_string, confidence) tuples.
        """
        dates = []

        if not text:
            return dates

        # Look for ISO 8601 dates
        iso_dates = re.findall(
            r"\b\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?(\.\d+)?(Z|[+-]\d{2}:\d{2})?\b",
            text,
        )
        for date_str in iso_dates:
            full_date = "".join(date_str)
            dt, confidence = DateNormalizer.normalize(full_date, "iso_text")
            if dt:
                dates.append((full_date, confidence))

        # Look for common date formats
        common_dates = re.findall(
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b",
            text,
        )
        for date_str in common_dates:
            dt, confidence = DateNormalizer.normalize(date_str, "common_text")
            if dt:
                dates.append((date_str, confidence))

        # Look for numeric dates
        numeric_dates = re.findall(
            r"\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}/\d{1,2}/\d{1,2}\b",
            text,
        )
        for date_str in numeric_dates:
            dt, confidence = DateNormalizer.normalize(date_str, "numeric_text")
            if dt:
                dates.append((date_str, confidence))

        return dates

    @staticmethod
    def get_freshness(date: datetime) -> bool:
        """
        Check if a date is within the 24-hour freshness window.

        Args:
            date: Datetime to check

        Returns:
            True if date is within 24 hours of now
        """
        now = datetime.now(timezone.utc)
        return (now - date) <= timedelta(hours=24)


# Singleton instance
date_normalizer = DateNormalizer()
