"""
SignalAtlas Fuzzy Matching

Provides fuzzy matching for entity resolution using RapidFuzz.
"""

from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process
from structlog import get_logger

from ..extraction.schemas import EntityType, ResolutionMethod
from ..resolution.canonicalizer import canonicalizer

logger = get_logger(__name__)


class FuzzyMatcher:
    """
    Fuzzy matching for entity resolution.

    Uses RapidFuzz for fast fuzzy string matching.
    """

    def __init__(
        self,
        min_score: float = 80.0,
        max_candidates: int = 10,
    ):
        self.min_score = min_score
        self.max_candidates = max_candidates

    def match(
        self,
        query: str,
        candidates: List[str],
    ) -> Tuple[Optional[str], float]:
        """
        Find the best fuzzy match.

        Args:
            query: Query string
            candidates: List of candidate strings

        Returns:
            Tuple of (best_match, score) or (None, 0.0)
        """
        if not query or not candidates:
            return None, 0.0

        # Normalize query
        norm_query = canonicalizer.normalize(query)

        # Normalize candidates
        norm_candidates = [canonicalizer.normalize(c) for c in candidates]

        # Use RapidFuzz to find best match
        result = process.extractOne(
            norm_query,
            norm_candidates,
            scorer=fuzz.token_set_ratio,
            score_cutoff=self.min_score,
        )

        if result:
            match, score, index = result
            # Normalize score to 0-1 range
            normalized_score = score / 100.0
            return candidates[index], normalized_score

        return None, 0.0

    def match_all(
        self,
        query: str,
        candidates: List[str],
        limit: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Find all matches above threshold.

        Args:
            query: Query string
            candidates: List of candidate strings
            limit: Maximum number of results

        Returns:
            List of (match, score) tuples
        """
        if not query or not candidates:
            return []

        norm_query = canonicalizer.normalize(query)
        norm_candidates = [canonicalizer.normalize(c) for c in candidates]

        results = process.extract(
            norm_query,
            norm_candidates,
            scorer=fuzz.token_set_ratio,
            score_cutoff=self.min_score,
            limit=limit,
        )

        return [
            (candidates[i], score / 100.0) for
            (match, score, i) in results
        ]

    def resolve(
        self,
        raw_name: str,
        candidates: List[str],
        entity_type: Optional[EntityType] = None,
    ) -> Tuple[Optional[str], ResolutionMethod, float]:
        """
        Resolve a raw name to canonical using fuzzy matching.

        Args:
            raw_name: Raw name to resolve
            candidates: List of candidate canonical names
            entity_type: Optional entity type

        Returns:
            Tuple of (canonical_name, method, confidence)
        """
        if not raw_name or not candidates:
            return None, ResolutionMethod.FUZZY, 0.0

        # First try exact match
        norm_raw = canonicalizer.normalize(raw_name)
        for candidate in candidates:
            if canonicalizer.normalize(candidate) == norm_raw:
                return candidate, ResolutionMethod.EXACT, 1.0

        # Try fuzzy match
        match, score = self.match(raw_name, candidates)

        if match and score >= 0.95:
            return match, ResolutionMethod.FUZZY, score
        elif match and score >= 0.80:
            return match, ResolutionMethod.FUZZY, score

        return None, ResolutionMethod.FUZZY, 0.0


# Singleton instance
fuzzy_matcher = FuzzyMatcher()
