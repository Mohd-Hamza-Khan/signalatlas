"""
SignalAtlas LLM Orchestrator

Provides orchestration for LLM extraction with:
- Provider fallback (Mistral -> DeepSeek -> Qwen)
- Automatic retry on rate limits
- Chunking for large documents
- Schema validation
- Error handling
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from structlog import get_logger

from .providers import (
    PROVIDER_CHAIN,
    LLMError,
    RateLimitError,
    PayloadTooLargeError,
    InvalidJSONError,
    ProviderUnavailableError,
    ExtractionError,
)
from ..extraction.schemas import BaseRecord
from ..extraction.chunker import chunker
from ..utils.retry import retry_async, HTTP_RETRY

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseRecord)


class LLMExtractor:
    """
    Orchestrates LLM extraction with fallback and retry logic.

    Usage:
        extractor = LLMExtractor()
        record = await extractor.extract(text, StartupRecord)
    """

    def __init__(
        self,
        providers: Optional[List] = None,
        max_tokens: int = 6000,
    ):
        self.providers = providers or PROVIDER_CHAIN
        self.max_tokens = max_tokens

    async def extract(
        self,
        text: str,
        schema: Type[T],
        prompt: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> T:
        """
        Extract structured data from text using LLM.

        Args:
            text: Text to extract from
            schema: Pydantic model class to extract into
            prompt: Optional custom prompt
            source_name: Optional source name for logging

        Returns:
            Instance of the schema class

        Raises:
            ExtractionError: If all providers fail
        """
        last_error: Optional[Exception] = None

        for provider in self.providers:
            try:
                result = await self._extract_with_provider(
                    provider, text, schema, prompt, source_name
                )
                logger.info(
                    "Extraction successful",
                    provider=provider.provider_name,
                    model=provider.model_name,
                    schema=schema.__name__,
                    source=source_name,
                )
                return result

            except PayloadTooLargeError as e:
                # Try with smaller chunks
                logger.warning(
                    "Payload too large, reducing chunk size",
                    provider=provider.provider_name,
                    error=str(e),
                )
                last_error = e

            except RateLimitError as e:
                logger.warning(
                    "Rate limited",
                    provider=provider.provider_name,
                    retry_after=e.retry_after,
                )
                last_error = e
                # Continue to next provider

            except (InvalidJSONError, ProviderUnavailableError) as e:
                logger.warning(
                    "Provider error",
                    provider=provider.provider_name,
                    error=str(e),
                )
                last_error = e
                # Continue to next provider

        # All providers failed
        raise ExtractionError(f"All providers failed: {last_error}")

    async def _extract_with_provider(
        self,
        provider,
        text: str,
        schema: Type[T],
        prompt: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> T:
        """Extract using a specific provider."""
        # Check if text is too large
        if provider.is_too_large(text):
            # Chunk the text
            chunks = chunker.chunk_for_model(text, max_tokens=self.max_tokens)
            logger.info(
                "Chunking text",
                num_chunks=len(chunks),
                provider=provider.provider_name,
            )

            # Extract from each chunk and merge
            results = []
            for i, chunk in enumerate(chunks):
                result = await provider.extract(chunk, schema, prompt)
                results.append(result)

            # Merge results
            return self._merge_results(results, schema)

        # Single chunk extraction
        return await provider.extract(text, schema, prompt)

    def _merge_results(
        self,
        results: List[T],
        schema: Type[T],
    ) -> T:
        """
        Merge results from multiple chunks.

        Uses deterministic conflict rules:
        - Non-null values override null values
        - Longer text values override shorter ones
        - Later values override earlier ones for simple fields
        """
        if not results:
            raise ExtractionError("No results to merge")

        if len(results) == 1:
            return results[0]

        # Create a merged dictionary
        merged: Dict[str, Any] = {}

        for result in results:
            data = result.model_dump()
            for key, value in data.items():
                if value is not None:
                    # If we don't have this key yet, or the new value is "better"
                    if key not in merged or merged[key] is None:
                        merged[key] = value
                    elif isinstance(value, str) and isinstance(merged[key], str):
                        # Prefer longer strings
                        if len(value) > len(merged[key]):
                            merged[key] = value
                    # For other types, later values override
                    else:
                        merged[key] = value

        # Create instance from merged data
        return schema.model_validate(merged)

    async def extract_batch(
        self,
        texts: List[str],
        schema: Type[T],
        prompt: Optional[str] = None,
    ) -> List[T]:
        """
        Extract from multiple texts.

        Args:
            texts: List of texts to extract from
            schema: Pydantic model class
            prompt: Optional custom prompt

        Returns:
            List of extracted records
        """
        results = []
        for i, text in enumerate(texts):
            try:
                result = await self.extract(text, schema, prompt)
                results.append(result)
                logger.info(
                    "Batch extraction",
                    progress=f"{i+1}/{len(texts)}",
                    schema=schema.__name__,
                )
            except Exception as e:
                logger.error(
                    "Batch extraction failed",
                    index=i,
                    error=str(e),
                )
                results.append(None)

        return [r for r in results if r is not None]


# Singleton instance
extractor = LLMExtractor()
