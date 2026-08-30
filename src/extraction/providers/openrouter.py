"""
SignalAtlas OpenRouter Provider

LLM provider implementation using OpenRouter API.
Supports Mistral, DeepSeek, Qwen, and other models.
"""

import json
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import httpx
from pydantic import BaseModel
from structlog import get_logger

from ...config import settings
from .base import (
    LLMProvider,
    RateLimitError,
    PayloadTooLargeError,
    InvalidJSONError,
    ProviderUnavailableError,
    ExtractionError,
)

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseModel)


# Model configuration
OPENROUTER_MODELS = {
    "mistral": "openrouter/mistralai/mistral-7b-instruct",
    "mistral-large": "openrouter/mistralai/mixtral-8x7b-instruct",
    "deepseek": "openrouter/deepseek-ai/deepseek-chat",
    "qwen": "openrouter/qwen/qwen-72b-chat",
    "qwen-plus": "openrouter/qwen/qwen-plus",
}


class OpenRouterProvider(LLMProvider[T]):
    """
    OpenRouter LLM provider.

    Uses OpenRouter API to access multiple LLM providers.
    Supports automatic fallback between models.
    """

    def __init__(
        self,
        model_name: str = "mistral",
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.model_name = model_name
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.timeout = timeout
        self.base_url = "https://openrouter.ai/api/v1"
        self.provider_name = "openrouter"
        self.model_id = OPENROUTER_MODELS.get(model_name, model_name)

        # Don't require API key for testing - it will fail at call time
        # if not self.api_key:
        #     raise ValueError("OPENROUTER_API_KEY is required")

        # Model-specific settings
        self.max_tokens = 4096
        self.max_input_tokens = 32000  # OpenRouter's max

    async def extract(
        self,
        text: str,
        schema: Type[T],
        prompt: Optional[str] = None,
    ) -> T:
        """Extract structured data from text."""
        if self.is_too_large(text):
            raise PayloadTooLargeError(
                f"Text is too large ({len(text)} chars, max {self.max_input_tokens * 4})"
            )

        # Build prompt
        if prompt is None:
            from ..extraction.prompts import PromptBuilder
            record_type = self._get_record_type(schema)
            prompt = PromptBuilder.get_prompt_for_record_type(record_type)

        full_prompt = prompt.format(text=text)

        # Call LLM
        response = await self._call_llm(full_prompt)

        # Parse JSON
        data = self.parse_json_response(response)

        # Validate and return
        return self.validate_schema(data, schema)

    async def chat(
        self,
        messages: list,
        temperature: float = 0.0,
    ) -> str:
        """Send a chat completion request."""
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
        }

        response = await self._call_api("/chat/completions", payload)
        return response["choices"][0]["message"]["content"]

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM with a single prompt."""
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,  # Always 0 for extraction
            "max_tokens": self.max_tokens,
        }

        response = await self._call_api("/chat/completions", payload)
        return response["choices"][0]["message"]["content"]

    async def _call_api(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Call OpenRouter API with retry logic."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/frontieratlas/signal-atlas",
            "X-Title": settings.OPENROUTER_APP_NAME,
        }

        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )

                    # Check for rate limiting
                    if response.status_code == 429:
                        retry_after = float(response.headers.get("Retry-After", 60))
                        raise RateLimitError(
                            f"Rate limited by OpenRouter",
                            retry_after=retry_after,
                        )

                    # Check for payload too large
                    if response.status_code == 413:
                        raise PayloadTooLargeError(
                            f"Payload too large for {self.model_id}"
                        )

                    # Check for other errors
                    if response.status_code != 200:
                        raise ProviderUnavailableError(
                            f"OpenRouter error: {response.status_code} - {response.text}"
                        )

                    return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "OpenRouter timeout",
                    attempt=attempt + 1,
                    model=self.model_id,
                )
                await self._backoff(attempt)

            except Exception as e:
                last_error = e
                logger.warning(
                    "OpenRouter error",
                    attempt=attempt + 1,
                    error=str(e),
                    model=self.model_id,
                )
                await self._backoff(attempt)

        raise ProviderUnavailableError(f"OpenRouter unavailable: {last_error}")

    async def _backoff(self, attempt: int) -> None:
        """Exponential backoff with jitter."""
        import random
        delay = min(60, 2 ** attempt) + random.uniform(0, 1)
        await asyncio.sleep(delay)

    def _get_record_type(self, schema: Type) -> str:
        """Get record type from schema."""
        schema_name = schema.__name__.lower()
        if "startup" in schema_name:
            return "startup"
        elif "product" in schema_name:
            return "product"
        elif "paper" in schema_name or "research" in schema_name:
            return "paper"
        elif "job" in schema_name:
            return "job"
        elif "news" in schema_name:
            return "news"
        return "unknown"


# Pre-configured provider instances
mistral_provider = OpenRouterProvider("mistral")
deepseek_provider = OpenRouterProvider("deepseek")
qwen_provider = OpenRouterProvider("qwen")

# Provider chain for fallback
PROVIDER_CHAIN = [
    mistral_provider,
    deepseek_provider,
    qwen_provider,
]
