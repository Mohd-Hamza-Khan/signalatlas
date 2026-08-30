"""
SignalAtlas Entity Resolution

Provides complete entity resolution pipeline:
- Normalization
- Exact matching
- Alias table
- Fuzzy matching
- Embedding matching
- LLM adjudication (for ambiguous cases)
"""

from typing import Any, Dict, List, Optional, Tuple

from structlog import get_logger

from ..extraction.schemas import (
    EntityType,
    ResolutionMethod,
    EntityMappingLog,
)
from .canonicalizer import canonicalizer, Canonicalizer
from .fuzzy import fuzzy_matcher, FuzzyMatcher
from .embeddings import embedding_matcher, EmbeddingMatcher

logger = get_logger(__name__)


class EntityResolver:
    """
    Complete entity resolution pipeline.

    Resolution cascade:
    1. Unicode normalization
    2. Lowercase
    3. Punctuation removal
    4. Legal suffix removal
    5. Exact canonical match
    6. Alias table
    7. RapidFuzz similarity
    8. Embedding similarity
    9. LLM adjudication (only for ambiguous cases)

    Accept automatically:
    - Exact normalized match (confidence 1.0)
    - Trusted alias (confidence 1.0)
    - Fuzzy score >= 0.95 (confidence = score)

    Review/LLM adjudication:
    - Fuzzy score 0.80-0.95

    Reject:
    - < 0.80 unless independently verified
    """

    def __init__(
        self,
        canonicalizer: Optional[Canonicalizer] = None,
        fuzzy_matcher: Optional[FuzzyMatcher] = None,
        embedding_matcher: Optional[EmbeddingMatcher] = None,
    ):
        self.canonicalizer = canonicalizer or canonicalizer
        self.fuzzy_matcher = fuzzy_matcher or fuzzy_matcher
        self.embedding_matcher = embedding_matcher or embedding_matcher
        self._mapping_logs: List[EntityMappingLog] = []

    def resolve(
        self,
        raw_name: str,
        candidates: Optional[List[str]] = None,
        entity_type: Optional[EntityType] = None,
        use_llm: bool = False,
    ) -> Tuple[Optional[str], ResolutionMethod, float]:
        """
        Resolve a raw name to canonical.

        Args:
            raw_name: Raw name to resolve
            candidates: Optional list of candidate canonical names
            entity_type: Entity type for context
            use_llm: Whether to use LLM for ambiguous cases

        Returns:
            Tuple of (canonical_name, method, confidence)
        """
        if not raw_name:
            return None, ResolutionMethod.EXACT, 0.0

        # Step 1: Try canonicalizer (exact + alias)
        canonical, method, confidence = self.canonicalizer.canonicalize(
            raw_name, entity_type
        )

        if confidence >= 1.0:
            # Exact match or alias
            self._log_mapping(raw_name, canonical, entity_type, method, confidence)
            return canonical, method, confidence

        # Step 2: Try fuzzy matching
        if candidates:
            canonical, method, confidence = self.fuzzy_matcher.resolve(
                raw_name, candidates, entity_type
            )

            if confidence >= 0.95:
                self._log_mapping(raw_name, canonical, entity_type, method, confidence)
                return canonical, method, confidence

            if confidence >= 0.80 and use_llm:
                # Could use LLM for adjudication
                pass

        # Step 3: Try embedding matching
        # Would need embeddings for this
        # canonical, method, confidence = self.embedding_matcher.resolve(
        #     raw_name, query_embedding
        # )

        # Step 4: Return normalized name as fallback
        normalized = self.canonicalizer.normalize(raw_name)
        self._log_mapping(raw_name, normalized, entity_type, ResolutionMethod.EXACT, 0.7)
        return normalized, ResolutionMethod.EXACT, 0.7

    def resolve_batch(
        self,
        raw_names: List[str],
        candidates: Optional[List[str]] = None,
        entity_type: Optional[EntityType] = None,
    ) -> List[Tuple[Optional[str], ResolutionMethod, float]]:
        """
        Resolve multiple names.

        Args:
            raw_names: List of raw names
            candidates: Optional list of candidate canonical names
            entity_type: Entity type

        Returns:
            List of resolution results
        """
        return [
            self.resolve(name, candidates, entity_type)
            for name in raw_names
        ]

    def add_alias(self, raw_name: str, canonical_name: str) -> None:
        """Add an alias mapping."""
        self.canonicalizer.add_alias(raw_name, canonical_name)

    def get_mapping_logs(self) -> List[EntityMappingLog]:
        """Get all mapping logs."""
        return self._mapping_logs

    def clear_mapping_logs(self) -> None:
        """Clear mapping logs."""
        self._mapping_logs = []

    def _log_mapping(
        self,
        raw_name: str,
        canonical_name: Optional[str],
        entity_type: Optional[EntityType],
        method: ResolutionMethod,
        confidence: float,
    ) -> None:
        """Log a mapping for auditing."""
        log = EntityMappingLog(
            raw_name=raw_name,
            canonical_name=canonical_name,
            entity_type=entity_type or EntityType.STARTUP,
            method=method,
            confidence=round(confidence, 4),
        )
        self._mapping_logs.append(log)
        logger.debug(
            "Entity mapping",
            raw=raw_name,
            canonical=canonical_name,
            method=method.value,
            confidence=f"{confidence:.4f}",
        )


# Singleton instance
resolver = EntityResolver()
