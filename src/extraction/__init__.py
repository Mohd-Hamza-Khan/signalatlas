"""
SignalAtlas Extraction Module

Provides LLM-based extraction capabilities.
"""

from .schemas import (
    BaseRecord,
    StartupRecord,
    ProductRecord,
    ResearchPaperRecord,
    JobRecord,
    NewsRecord,
    Source,
    Provenance,
    StartupContent,
    ProductContent,
    ResearchPaperContent,
    JobContent,
    NewsContent,
    PricingModel,
    RecordType,
    RoleFamily,
    EntityType,
    ResolutionMethod,
    EntityAlias,
    EntityMappingLog,
    ExtractionResult,
    SchemaValidator,
)
from .prompts import (
    BASE_PROMPT_TEMPLATE,
    STARTUP_EXTRACTION_PROMPT,
    PRODUCT_EXTRACTION_PROMPT,
    PAPER_EXTRACTION_PROMPT,
    JOB_EXTRACTION_PROMPT,
    NEWS_EXTRACTION_PROMPT,
    ENTITY_RESOLUTION_PROMPT,
    CHUNK_EXTRACTION_PROMPT,
    PromptBuilder,
)
from .chunker import SemanticChunker, chunker
from .orchestrator import LLMExtractor, extractor
from .providers import (
    LLMProvider,
    LLMError,
    RateLimitError,
    PayloadTooLargeError,
    InvalidJSONError,
    ProviderUnavailableError,
    ExtractionError,
    OpenRouterProvider,
    OPENROUTER_MODELS,
    mistral_provider,
    deepseek_provider,
    qwen_provider,
    PROVIDER_CHAIN,
)

__all__ = [
    # Schemas
    "BaseRecord",
    "StartupRecord",
    "ProductRecord",
    "ResearchPaperRecord",
    "JobRecord",
    "NewsRecord",
    "Source",
    "Provenance",
    "StartupContent",
    "ProductContent",
    "ResearchPaperContent",
    "JobContent",
    "NewsContent",
    # Enums
    "PricingModel",
    "RecordType",
    "RoleFamily",
    "EntityType",
    "ResolutionMethod",
    # Entity
    "EntityAlias",
    "EntityMappingLog",
    # Extraction
    "ExtractionResult",
    "SchemaValidator",
    # Prompts
    "BASE_PROMPT_TEMPLATE",
    "STARTUP_EXTRACTION_PROMPT",
    "PRODUCT_EXTRACTION_PROMPT",
    "PAPER_EXTRACTION_PROMPT",
    "JOB_EXTRACTION_PROMPT",
    "NEWS_EXTRACTION_PROMPT",
    "ENTITY_RESOLUTION_PROMPT",
    "CHUNK_EXTRACTION_PROMPT",
    "PromptBuilder",
    # Chunker
    "SemanticChunker",
    "chunker",
    # Orchestrator
    "LLMExtractor",
    "extractor",
    # Providers
    "LLMProvider",
    "LLMError",
    "RateLimitError",
    "PayloadTooLargeError",
    "InvalidJSONError",
    "ProviderUnavailableError",
    "ExtractionError",
    "OpenRouterProvider",
    "OPENROUTER_MODELS",
    "mistral_provider",
    "deepseek_provider",
    "qwen_provider",
    "PROVIDER_CHAIN",
]
