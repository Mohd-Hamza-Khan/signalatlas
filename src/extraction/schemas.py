"""
SignalAtlas Pydantic Schemas

Defines the data models for all entity types using Pydantic v2.
These schemas are used for:
- LLM extraction output validation
- API request/response validation
- Data serialization
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ============================================================================
# Common Models
# ============================================================================

class Source(BaseModel):
    """Source of the data."""
    name: str = Field(..., description="Name of the source")
    url: HttpUrl = Field(..., description="URL of the source page")


class Provenance(BaseModel):
    """Provenance information for tracking data origin."""
    content_hash: str = Field(..., description="SHA-256 hash of the source content")
    extraction_provider: Optional[str] = Field(
        default=None,
        description="LLM provider used for extraction (e.g., 'openrouter-mistral')"
    )
    extraction_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score of the extraction"
    )
    date_source: Optional[str] = Field(
        default=None,
        description="Source of the date (e.g., 'json_ld', 'meta', 'visible_text')"
    )
    date_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score of the date extraction"
    )


# ============================================================================
# Enums
# ============================================================================

class RecordType(str, Enum):
    """Types of records in the system."""
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    RESEARCH_PAPER = "RESEARCH_PAPER"
    JOB = "JOB"
    NEWS = "NEWS"


class PricingModel(str, Enum):
    """Pricing models for products."""
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class RoleFamily(str, Enum):
    """Job role families."""
    ENGINEERING = "Engineering"
    RESEARCH = "Research"
    DESIGN = "Design"
    PRODUCT = "Product"
    MARKETING = "Marketing"
    SALES = "Sales"
    OPERATIONS = "Operations"
    OTHER = "Other"


class EntityType(str, Enum):
    """Entity types for resolution."""
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"
    PERSON = "PERSON"
    RESEARCH_PAPER = "RESEARCH_PAPER"


class ResolutionMethod(str, Enum):
    """Methods used for entity resolution."""
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    EMBEDDING = "embedding"
    LLM = "llm"


# ============================================================================
# Content Models
# ============================================================================

class StartupContent(BaseModel):
    """Content for a startup record."""
    entity_name: str = Field(..., description="Canonical name of the startup")
    description: Optional[str] = Field(
        default=None,
        description="Description of the startup"
    )
    employee_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of employees"
    )
    website: Optional[HttpUrl] = Field(
        default=None,
        description="Startup website URL"
    )
    founded_year: Optional[int] = Field(
        default=None,
        ge=1900,
        le=2100,
        description="Year the startup was founded"
    )
    location: Optional[str] = Field(
        default=None,
        description="Physical location of the startup"
    )
    batch: Optional[str] = Field(
        default=None,
        description="YC batch (e.g., 'W23', 'S24')"
    )


class ProductContent(BaseModel):
    """Content for a product record."""
    product_name: str = Field(..., description="Name of the product")
    startup_name: Optional[str] = Field(
        default=None,
        description="Name of the startup that created the product"
    )
    pricing_model: Optional[PricingModel] = Field(
        default=None,
        description="Pricing model of the product"
    )
    website: Optional[HttpUrl] = Field(
        default=None,
        description="Product website URL"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the product"
    )
    tagline: Optional[str] = Field(
        default=None,
        description="Product tagline or slogan"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="List of tags/categories for the product"
    )
    upvotes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of upvotes (e.g., on Product Hunt)"
    )


class ResearchPaperContent(BaseModel):
    """Content for a research paper record."""
    title: str = Field(..., description="Title of the paper")
    authors: List[str] = Field(
        default_factory=list,
        description="List of author names"
    )
    paper_url: HttpUrl = Field(..., description="URL of the paper")
    github_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL of the GitHub repository"
    )
    github_stars: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of stars on GitHub"
    )
    published_date: Optional[datetime] = Field(
        default=None,
        description="Date the paper was published"
    )
    abstract: Optional[str] = Field(
        default=None,
        description="Abstract of the paper"
    )
    external_id: Optional[str] = Field(
        default=None,
        description="External ID (e.g., arXiv ID)"
    )
    category: Optional[str] = Field(
        default=None,
        description="Primary category of the paper"
    )
    pdf_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL of the PDF version"
    )


class JobContent(BaseModel):
    """Content for a job record."""
    company: str = Field(..., description="Name of the company")
    role: str = Field(..., description="Job role/title")
    date: Optional[datetime] = Field(
        default=None,
        description="Publication date of the job posting"
    )
    is_remote: Optional[bool] = Field(
        default=None,
        description="Whether the job is remote"
    )
    role_family: Optional[RoleFamily] = Field(
        default=None,
        description="Family/category of the role"
    )
    location: Optional[str] = Field(
        default=None,
        description="Location of the job"
    )
    description: Optional[str] = Field(
        default=None,
        description="Job description"
    )
    application_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL to apply for the job"
    )
    salary_min: Optional[float] = Field(
        default=None,
        ge=0,
        description="Minimum salary"
    )
    salary_max: Optional[float] = Field(
        default=None,
        ge=0,
        description="Maximum salary"
    )
    salary_currency: Optional[str] = Field(
        default=None,
        description="Currency of the salary"
    )


class NewsContent(BaseModel):
    """Content for a news record."""
    title: str = Field(..., description="Title of the news article")
    body: str = Field(..., description="Body content of the article")
    published_date: Optional[datetime] = Field(
        default=None,
        description="Date the article was published"
    )
    author: Optional[str] = Field(
        default=None,
        description="Author of the article"
    )
    summary: Optional[str] = Field(
        default=None,
        description="Short summary of the article"
    )
    image_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL of the featured image"
    )


# ============================================================================
# Record Models
# ============================================================================

class BaseRecord(BaseModel):
    """Base class for all records."""
    schema_version: str = Field(
        default="1.0",
        description="Version of the schema"
    )


class StartupRecord(BaseRecord):
    """Complete startup record."""
    record_type: RecordType = Field(
        default=RecordType.STARTUP,
        description="Type of the record"
    )
    source: Source = Field(..., description="Source of the data")
    content: StartupContent = Field(..., description="Startup content")
    provenance: Provenance = Field(..., description="Provenance information")
    collected_at: datetime = Field(
        ..., description="When the record was collected"
    )


class ProductRecord(BaseRecord):
    """Complete product record."""
    record_type: RecordType = Field(
        default=RecordType.PRODUCT,
        description="Type of the record"
    )
    source: Source = Field(..., description="Source of the data")
    content: ProductContent = Field(..., description="Product content")
    provenance: Provenance = Field(..., description="Provenance information")
    collected_at: datetime = Field(
        ..., description="When the record was collected"
    )


class ResearchPaperRecord(BaseRecord):
    """Complete research paper record."""
    record_type: RecordType = Field(
        default=RecordType.RESEARCH_PAPER,
        description="Type of the record"
    )
    source: Source = Field(..., description="Source of the data")
    content: ResearchPaperContent = Field(..., description="Paper content")
    provenance: Provenance = Field(..., description="Provenance information")
    collected_at: datetime = Field(
        ..., description="When the record was collected"
    )


class JobRecord(BaseRecord):
    """Complete job record."""
    record_type: RecordType = Field(
        default=RecordType.JOB,
        description="Type of the record"
    )
    source: Source = Field(..., description="Source of the data")
    content: JobContent = Field(..., description="Job content")
    provenance: Provenance = Field(..., description="Provenance information")
    collected_at: datetime = Field(
        ..., description="When the record was collected"
    )


class NewsRecord(BaseRecord):
    """Complete news record."""
    record_type: RecordType = RecordType.NEWS
    source: Source = Field(..., description="Source of the data")
    content: NewsContent = Field(..., description="News content")
    provenance: Provenance = Field(..., description="Provenance information")
    collected_at: datetime = Field(
        ..., description="When the record was collected"
    )


# ============================================================================
# Entity Resolution Models
# ============================================================================

class EntityAlias(BaseModel):
    """Entity alias mapping."""
    raw_name: str = Field(..., description="Raw name as found in source")
    normalized_name: str = Field(..., description="Normalized name")
    canonical_name: str = Field(..., description="Canonical name")
    entity_type: EntityType = Field(..., description="Type of entity")
    method: ResolutionMethod = Field(..., description="Method used for resolution")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score"
    )


class EntityMappingLog(BaseModel):
    """Log entry for entity mapping."""
    raw_name: str = Field(..., description="Raw name as found")
    canonical_name: Optional[str] = Field(
        default=None,
        description="Resolved canonical name"
    )
    entity_type: EntityType = Field(..., description="Type of entity")
    method: ResolutionMethod = Field(..., description="Method used")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    source_url: Optional[str] = Field(
        default=None,
        description="URL where the name was found"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the log entry was created"
    )


# ============================================================================
# Extraction Models (for LLM output)
# ============================================================================

class ExtractionResult(BaseModel):
    """Result from LLM extraction."""
    record: Union[StartupRecord, ProductRecord, ResearchPaperRecord, JobRecord, NewsRecord] = Field(
        ..., description="Extracted record"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence"
    )
    provider: str = Field(..., description="LLM provider used")
    model: str = Field(..., description="Model used for extraction")
    chunks_used: int = Field(
        default=1,
        ge=1,
        description="Number of chunks used"
    )


# ============================================================================
# Validation
# ============================================================================

class SchemaValidator:
    """Validates records against their schemas."""

    @staticmethod
    def validate(record: BaseRecord) -> bool:
        """Validate a record."""
        try:
            # This will raise ValidationError if invalid
            record.model_validate(record.model_dump())
            return True
        except Exception:
            return False

    @staticmethod
    def validate_dict(data: Dict[str, Any], model: type[BaseModel]) -> bool:
        """Validate a dictionary against a model."""
        try:
            model.model_validate(data)
            return True
        except Exception:
            return False
