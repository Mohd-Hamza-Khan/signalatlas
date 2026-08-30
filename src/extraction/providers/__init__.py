"""
SignalAtlas LLM Providers Package

Provides LLM provider implementations.
"""

from .base import (
    LLMProvider,
    LLMError,
    RateLimitError,
    PayloadTooLargeError,
    InvalidJSONError,
    ProviderUnavailableError,
    ExtractionError,
)
from .openrouter import (
    OpenRouterProvider,
    OPENROUTER_MODELS,
    mistral_provider,
    deepseek_provider,
    qwen_provider,
    PROVIDER_CHAIN,
)

__all__ = [
    # Base
    "LLMProvider",
    "LLMError",
    "RateLimitError",
    "PayloadTooLargeError",
    "InvalidJSONError",
    "ProviderUnavailableError",
    "ExtractionError",
    # OpenRouter
    "OpenRouterProvider",
    "OPENROUTER_MODELS",
    "mistral_provider",
    "deepseek_provider",
    "qwen_provider",
    "PROVIDER_CHAIN",
]
