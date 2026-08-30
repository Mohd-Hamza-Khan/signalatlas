"""
SignalAtlas LLM Provider Base Class

Defines the interface for LLM providers.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError
from structlog import get_logger

from ..schemas import (
    BaseRecord,
    StartupRecord,
    ProductRecord,
    ResearchPaperRecord,
    JobRecord,
    NewsRecord,
)

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseRecord)


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class RateLimitError(LLMError):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class PayloadTooLargeError(LLMError):
    """Payload exceeds model limits."""
    pass


class InvalidJSONError(LLMError):
    """LLM returned invalid JSON."""
    pass


class ProviderUnavailableError(LLMError):
    """Provider is unavailable."""
    pass


class ExtractionError(LLMError):
    """Extraction failed."""
    pass


class LLMProvider(ABC, Generic[T]):
    """
    Abstract base class for LLM providers.

    All providers must implement:
    - extract(): Extract structured data from text
    - validate(): Validate extracted data against schema
    """

    provider_name: str = "base"
    model_name: str = "unknown"
    max_tokens: int = 8192
    max_input_tokens: int = 6000

    @abstractmethod
    async def extract(
        self,
        text: str,
        schema: Type[T],
        prompt: Optional[str] = None,
    ) -> T:
        """
        Extract structured data from text.

        Args:
            text: Input text to extract from
            schema: Pydantic model class to extract into
            prompt: Optional custom prompt

        Returns:
            Instance of the schema class

        Raises:
            RateLimitError: If rate limited
            PayloadTooLargeError: If text is too large
            InvalidJSONError: If LLM returns invalid JSON
            ProviderUnavailableError: If provider is down
            ExtractionError: If extraction fails
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list,
        temperature: float = 0.0,
    ) -> str:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts (role, content)
            temperature: Sampling temperature

        Returns:
            Generated text
        """
        pass

    def validate_schema(
        self,
        data: Dict[str, Any],
        schema: Type[T],
    ) -> T:
        """
        Validate extracted data against schema.

        Args:
            data: Extracted data dictionary
            schema: Pydantic model class

        Returns:
            Validated instance of the schema

        Raises:
            ValidationError: If data doesn't match schema
        """
        try:
            return schema.model_validate(data)
        except ValidationError as e:
            logger.error(
                "Schema validation failed",
                error=str(e),
                schema=schema.__name__,
                data=str(data)[:500],
            )
            raise

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response.

        Handles common JSON formatting issues.
        """
        response = response.strip()

        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()

        # Try to parse JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON response", error=str(e))
            # Try to fix common issues
            fixed = self._fix_json(response)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                raise InvalidJSONError(f"Invalid JSON: {response[:200]}")

    def _fix_json(self, json_str: str) -> str:
        """Attempt to fix common JSON issues."""
        import re

        # Fix trailing commas
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)

        # Fix single quotes
        json_str = json_str.replace("'", '"')

        # Fix unquoted keys
        json_str = re.sub(r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1 "\2":', json_str)

        return json_str

    def estimate_tokens(self, text: str) -> int:
        """Estimate number of tokens in text."""
        # Simple estimation: ~4 characters per token
        return len(text) // 4

    def is_too_large(self, text: str) -> bool:
        """Check if text is too large for this provider."""
        return self.estimate_tokens(text) > self.max_input_tokens
