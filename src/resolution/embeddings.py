"""
SignalAtlas Embedding Matching

Provides embedding-based entity resolution using pgvector.
"""

from typing import Any, Dict, List, Optional, Tuple

from structlog import get_logger

from ..extraction.schemas import EntityType, ResolutionMethod

logger = get_logger(__name__)


class EmbeddingMatcher:
    """
    Embedding-based matching for entity resolution.

    Uses pgvector for vector similarity search.
    """

    def __init__(self):
        self._embeddings: Dict[str, List[float]] = {}

    def add_embedding(
        self,
        name: str,
        embedding: List[float],
    ) -> None:
        """Add an embedding for a name."""
        self._embeddings[name] = embedding

    def match(
        self,
        query_embedding: List[float],
        k: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Find nearest neighbors.

        Args:
            query_embedding: Query embedding vector
            k: Number of results

        Returns:
            List of (name, similarity) tuples
        """
        import numpy as np

        if not query_embedding or not self._embeddings:
            return []

        query = np.array(query_embedding)
        results = []

        for name, embedding in self._embeddings.items():
            emb = np.array(embedding)
            # Cosine similarity
            similarity = np.dot(query, emb) / (
                np.linalg.norm(query) * np.linalg.norm(emb)
            )
            results.append((name, float(similarity)))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:k]

    def resolve(
        self,
        raw_name: str,
        query_embedding: List[float],
        threshold: float = 0.85,
    ) -> Tuple[Optional[str], ResolutionMethod, float]:
        """
        Resolve a raw name using embeddings.

        Args:
            raw_name: Raw name
            query_embedding: Embedding of the raw name
            threshold: Minimum similarity threshold

        Returns:
            Tuple of (canonical_name, method, confidence)
        """
        if not query_embedding:
            return None, ResolutionMethod.EMBEDDING, 0.0

        matches = self.match(query_embedding, k=1)

        if matches:
            name, similarity = matches[0]
            if similarity >= threshold:
                return name, ResolutionMethod.EMBEDDING, similarity

        return None, ResolutionMethod.EMBEDDING, 0.0


# Singleton instance
embedding_matcher = EmbeddingMatcher()
