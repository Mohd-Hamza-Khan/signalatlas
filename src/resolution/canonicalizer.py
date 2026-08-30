"""
SignalAtlas Entity Canonicalizer

Provides deterministic entity resolution using:
- Unicode normalization
- Lowercase
- Punctuation removal
- Legal suffix removal
- Exact canonical match
- Alias table
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from structlog import get_logger

from ..extraction.schemas import EntityType, ResolutionMethod
from ..normalization.text import normalizer

logger = get_logger(__name__)


class Canonicalizer:
    """
    Canonicalizes entity names for matching.

    Resolution order:
    1. Unicode normalization
    2. Lowercase
    3. Punctuation removal
    4. Legal suffix removal
    5. Exact canonical match
    6. Alias table
    """

    def __init__(self):
        # Alias table: raw_name -> canonical_name
        self._aliases: Dict[str, str] = {}
        # Reverse lookup: canonical_name -> set of raw_names
        self._canonical_to_raw: Dict[str, Set[str]] = {}

    def add_alias(self, raw_name: str, canonical_name: str) -> None:
        """Add an alias mapping."""
        norm_raw = self.normalize(raw_name)
        norm_canonical = self.normalize(canonical_name)

        self._aliases[norm_raw] = norm_canonical

        if norm_canonical not in self._canonical_to_raw:
            self._canonical_to_raw[norm_canonical] = set()
        self._canonical_to_raw[norm_canonical].add(norm_raw)

    def normalize(self, name: str) -> str:
        """
        Normalize a name for comparison.

        Steps:
        1. Unicode normalization (NFC)
        2. Lowercase
        3. Remove punctuation (except apostrophes and hyphens)
        4. Remove legal suffixes
        5. Normalize whitespace
        """
        if not name:
            return ""

        import unicodedata

        # Unicode normalization
        name = unicodedata.normalize("NFC", name)

        # Lowercase
        name = name.lower()

        # Remove punctuation (keep apostrophes and hyphens)
        name = re.sub(r"[^\w\s\-']", "", name)

        # Remove legal suffixes
        suffixes = [
            r"\binc\b",
            r"\bincorporated\b",
            r"\bcorp\b",
            r"\bcorporation\b",
            r"\bllc\b",
            r"\blimited\b",
            r"\bltd\b",
            r"\bco\b",
            r"\bcompany\b",
            r"\bthe\b",
            r"\bgroup\b",
            r"\bholdings\b",
            r"\bllp\b",
            r"\bplc\b",
            r"\bgmbh\b",
            r"\bsa\b",
            r"\bas\b",
        ]
        for suffix in suffixes:
            name = re.sub(suffix, "", name)

        # Normalize whitespace
        name = normalizer.normalize_whitespace(name)

        # Strip
        name = name.strip()

        return name

    def canonicalize(
        self,
        raw_name: str,
        entity_type: Optional[EntityType] = None,
    ) -> Tuple[str, ResolutionMethod, float]:
        """
        Canonicalize a raw name.

        Args:
            raw_name: Raw name to canonicalize
            entity_type: Optional entity type for context

        Returns:
            Tuple of (canonical_name, method, confidence)
        """
        if not raw_name:
            return "", ResolutionMethod.EXACT, 0.0

        norm_name = self.normalize(raw_name)

        # Check alias table
        if norm_name in self._aliases:
            return (
                self._aliases[norm_name],
                ResolutionMethod.ALIAS,
                1.0,
            )

        # For now, return the normalized name as canonical
        # In production, this would check against a database of known entities
        return norm_name, ResolutionMethod.EXACT, 1.0

    def is_known(self, name: str) -> bool:
        """Check if a name is in the alias table."""
        norm_name = self.normalize(name)
        return norm_name in self._aliases

    def get_aliases(self, canonical_name: str) -> List[str]:
        """Get all aliases for a canonical name."""
        norm_canonical = self.normalize(canonical_name)
        return list(self._canonical_to_raw.get(norm_canonical, set()))


# Singleton instance
canonicalizer = Canonicalizer()
