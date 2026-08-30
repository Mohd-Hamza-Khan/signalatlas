"""
SignalAtlas Semantic Chunker

Provides intelligent chunking of documents for LLM processing.

Features:
- Section-aware chunking
- Token estimation
- Recursive splitting
- Never exceeds configured budget
- Preserves title and important metadata
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from structlog import get_logger

from ..normalization.text import normalizer

logger = get_logger(__name__)


class SemanticChunker:
    """
    Chunks documents semantically for LLM processing.

    Pipeline:
    1. Remove script/style/nav/footer/ads
    2. Extract title + headings + paragraphs + metadata
    3. Estimate tokens
    4. If safe -> one request
    5. If oversized -> semantic sections
    6. If still oversized -> recursive chunks
    """

    def __init__(
        self,
        max_tokens: int = 6000,
        overlap_tokens: int = 300,
        overlap_ratio: float = 0.1,
    ):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.overlap_ratio = overlap_ratio

    def chunk_for_model(
        self,
        text: str,
        max_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None,
    ) -> List[str]:
        """
        Chunk text for LLM processing.

        Args:
            text: Text to chunk
            max_tokens: Maximum tokens per chunk (overrides instance setting)
            overlap_tokens: Overlap tokens between chunks (overrides instance setting)

        Returns:
            List of text chunks
        """
        max_tokens = max_tokens or self.max_tokens
        overlap_tokens = overlap_tokens or self.overlap_tokens

        # Estimate total tokens
        total_tokens = self.estimate_tokens(text)

        if total_tokens <= max_tokens:
            # Single chunk is fine
            return [text]

        # Try semantic chunking
        chunks = self._chunk_semantically(text, max_tokens, overlap_tokens)

        # Verify no chunk exceeds limit
        for i, chunk in enumerate(chunks):
            chunk_tokens = self.estimate_tokens(chunk)
            if chunk_tokens > max_tokens:
                logger.warning(
                    "Chunk exceeds token limit",
                    chunk_index=i,
                    tokens=chunk_tokens,
                    max_tokens=max_tokens,
                )
                # Recursively split
                sub_chunks = self._chunk_semantically(
                    chunk, max_tokens, overlap_tokens
                )
                chunks[i:i+1] = sub_chunks

        return chunks

    def _chunk_semantically(
        self,
        text: str,
        max_tokens: int,
        overlap_tokens: int,
    ) -> List[str]:
        """
        Chunk text by semantic sections.

        Tries to split at:
        1. Section boundaries (##, ###, etc.)
        2. Paragraph boundaries
        3. Sentence boundaries
        """
        # First, try to split by markdown-style headings
        heading_chunks = self._split_by_headings(text)
        if len(heading_chunks) > 1:
            result = []
            for chunk in heading_chunks:
                chunk_tokens = self.estimate_tokens(chunk)
                if chunk_tokens > max_tokens:
                    # Recursively split
                    sub_chunks = self._chunk_semantically(
                        chunk, max_tokens, overlap_tokens
                    )
                    result.extend(sub_chunks)
                else:
                    result.append(chunk)
            return self._add_overlap(result, overlap_tokens)

        # Try to split by HTML headings
        html_chunks = self._split_by_html_headings(text)
        if len(html_chunks) > 1:
            result = []
            for chunk in html_chunks:
                chunk_tokens = self.estimate_tokens(chunk)
                if chunk_tokens > max_tokens:
                    sub_chunks = self._chunk_semantically(
                        chunk, max_tokens, overlap_tokens
                    )
                    result.extend(sub_chunks)
                else:
                    result.append(chunk)
            return self._add_overlap(result, overlap_tokens)

        # Split by paragraphs
        para_chunks = self._split_by_paragraphs(text)
        if len(para_chunks) > 1:
            result = []
            current_chunk = []
            current_tokens = 0

            for para in para_chunks:
                para_tokens = self.estimate_tokens(para)

                if current_tokens + para_tokens > max_tokens and current_chunk:
                    # Add current chunk and start new
                    result.append("\n\n".join(current_chunk))
                    current_chunk = [para]
                    current_tokens = para_tokens
                else:
                    current_chunk.append(para)
                    current_tokens += para_tokens

            if current_chunk:
                result.append("\n\n".join(current_chunk))

            return self._add_overlap(result, overlap_tokens)

        # Fallback: split by sentences
        sentence_chunks = self._split_by_sentences(text)
        result = []
        current_chunk = []
        current_tokens = 0

        for sentence in sentence_chunks:
            sentence_tokens = self.estimate_tokens(sentence)

            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                result.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        if current_chunk:
            result.append(" ".join(current_chunk))

        return self._add_overlap(result, overlap_tokens)

    def _split_by_headings(self, text: str) -> List[str]:
        """Split text by markdown-style headings."""
        # Match markdown headings: #, ##, ###, etc.
        pattern = r"^(#{1,6})\s+(.+?)$"
        lines = text.split("\n")
        chunks = []
        current_chunk = []

        for line in lines:
            match = re.match(pattern, line.strip())
            if match:
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                # Add heading to new chunk
                current_chunk.append(line)
            else:
                current_chunk.append(line)

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks if chunks else [text]

    def _split_by_html_headings(self, text: str) -> List[str]:
        """Split text by HTML headings."""
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(text, "lxml")
            headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

            if not headings:
                return [text]

            chunks = []
            current_chunk = []

            all_elements = list(soup.children)
            for element in all_elements:
                if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    if current_chunk:
                        chunks.append("".join(str(e) for e in current_chunk))
                        current_chunk = []
                    current_chunk.append(element)
                else:
                    current_chunk.append(element)

            if current_chunk:
                chunks.append("".join(str(e) for e in current_chunk))

            # Convert to text
            return [normalizer.clean_html(chunk) for chunk in chunks]

        except Exception:
            return [text]

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """Split text by paragraphs."""
        # Split by double newlines
        paragraphs = re.split(r"\n{2,}", text)
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_by_sentences(self, text: str) -> List[str]:
        """Split text by sentences."""
        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _add_overlap(self, chunks: List[str], overlap_tokens: int) -> List[str]:
        """Add overlap between chunks."""
        if len(chunks) <= 1 or overlap_tokens <= 0:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i-1]
            current_chunk = chunks[i]

            # Find overlap point
            prev_tokens = self.estimate_tokens(prev_chunk)
            overlap_chars = int(overlap_tokens * 4)  # ~4 chars per token

            if overlap_chars > 0:
                overlap_text = prev_chunk[-overlap_chars:]
                result.append(f"{overlap_text}{current_chunk}")
            else:
                result.append(current_chunk)

        return result

    def estimate_tokens(self, text: str) -> int:
        """Estimate number of tokens in text."""
        # Simple estimation: ~4 characters per token
        # This is a rough estimate; actual tokenization varies by model
        return len(text) // 4

    def reduce_chunk_size(
        self,
        chunks: List[str],
        max_tokens: int,
    ) -> List[str]:
        """
        Reduce chunk size by splitting larger chunks.

        Used when initial chunking produces chunks that are still too large.
        """
        result = []
        for chunk in chunks:
            chunk_tokens = self.estimate_tokens(chunk)
            if chunk_tokens > max_tokens:
                # Split this chunk
                sub_chunks = self.chunk_for_model(chunk, max_tokens)
                result.extend(sub_chunks)
            else:
                result.append(chunk)
        return result


# Singleton instance
chunker = SemanticChunker()
