"""
SignalAtlas Freshness Filter

Filters records to ensure only fresh (within 24 hours) content is processed.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from structlog import get_logger

from .dates import date_normalizer

logger = get_logger(__name__)


class FreshnessFilter:
    """
    Filters records based on freshness (24-hour window).

    A record is fresh if:
        now_utc - published_at <= timedelta(hours=24)

    For records without a reliable date:
    1. Try JSON-LD
    2. Try OpenGraph/meta tags
    3. Try <time datetime>
    4. Try visible date text
    5. Parse relative dates
    6. Compare normalized content hash against previous observations
    7. Mark heuristic records with lower confidence
    8. Never claim guaranteed freshness when evidence is insufficient
    """

    def __init__(self, max_age_hours: int = 24):
        self.max_age_hours = max_age_hours
        self._content_hashes: set = set()  # For duplicate detection

    def is_fresh(
        self,
        record: Dict[str, Any],
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Check if a record is fresh.

        Args:
            record: Record dictionary with content and provenance

        Returns:
            Tuple of (is_fresh, confidence, date_source)
        """
        # Get published date from content
        published_date = self._get_published_date(record)

        if published_date is None:
            # No date found - use heuristic
            return self._heuristic_check(record)

        # Check freshness
        now = datetime.now(timezone.utc)
        age = now - published_date

        is_fresh = age <= timedelta(hours=self.max_age_hours)
        confidence = self._calculate_confidence(record, published_date)
        date_source = record.get("provenance", {}).get("date_source", "unknown")

        return is_fresh, confidence, date_source

    def _get_published_date(self, record: Dict[str, Any]) -> Optional[datetime]:
        """Extract published date from record."""
        # Check content.published_date
        content = record.get("content", {})
        published_date = content.get("published_date")
        if published_date:
            if isinstance(published_date, str):
                dt, _ = date_normalizer.normalize(published_date)
                return dt
            elif isinstance(published_date, datetime):
                return published_date

        # Check provenance
        provenance = record.get("provenance", {})
        date_str = provenance.get("published_date")
        if date_str:
            dt, _ = date_normalizer.normalize(date_str)
            return dt

        return None

    def _heuristic_check(
        self,
        record: Dict[str, Any],
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Use heuristics to determine freshness when no date is available.

        Uses:
        - Content hash comparison against previous observations
        - Lower confidence for heuristic records
        """
        content = record.get("content", {})
        body = content.get("body", "") or content.get("description", "")

        # Generate content hash
        from ..utils.hashing import hasher
        content_hash = hasher.hash_text(body)

        # Check if we've seen this content before
        if content_hash in self._content_hashes:
            # Duplicate content - not fresh
            return False, 0.5, "content_hash_duplicate"

        # Mark as seen
        self._content_hashes.add(content_hash)

        # Heuristic: assume it's fresh but with low confidence
        # In production, this would use more sophisticated heuristics
        return True, 0.3, "heuristic"

    def _calculate_confidence(
        self,
        record: Dict[str, Any],
        published_date: datetime,
    ) -> float:
        """Calculate confidence in the freshness determination."""
        provenance = record.get("provenance", {})
        date_confidence = provenance.get("date_confidence", 0.0)

        # Base confidence from date extraction
        confidence = date_confidence

        # Boost confidence if date source is reliable
        date_source = provenance.get("date_source", "")
        reliable_sources = ["json_ld", "meta", "time_element"]
        if date_source in reliable_sources:
            confidence = min(confidence + 0.1, 1.0)

        return round(confidence, 4)

    def filter_records(
        self,
        records: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter a list of records, separating fresh from stale.

        Args:
            records: List of record dictionaries

        Returns:
            Tuple of (fresh_records, stale_records)
        """
        fresh = []
        stale = []

        for record in records:
            is_fresh, confidence, date_source = self.is_fresh(record)

            if is_fresh:
                # Update provenance with freshness info
                if "provenance" not in record:
                    record["provenance"] = {}
                record["provenance"]["is_fresh"] = True
                record["provenance"]["freshness_confidence"] = confidence
                record["provenance"]["freshness_date_source"] = date_source
                fresh.append(record)
            else:
                if "provenance" not in record:
                    record["provenance"] = {}
                record["provenance"]["is_fresh"] = False
                record["provenance"]["freshness_confidence"] = confidence
                record["provenance"]["freshness_date_source"] = date_source
                stale.append(record)

        logger.info(
            "Freshness filter",
            fresh_count=len(fresh),
            stale_count=len(stale),
            total=len(records),
        )

        return fresh, stale

    def filter_jobs(
        self,
        jobs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter job records to fresh ones only."""
        fresh, _ = self.filter_records(jobs)
        return fresh

    def filter_news(
        self,
        news: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter news records to fresh ones only."""
        fresh, _ = self.filter_records(news)
        return fresh

    def clear_content_hashes(self) -> None:
        """Clear the content hash cache."""
        self._content_hashes.clear()


# Singleton instance
freshness_filter = FreshnessFilter()
