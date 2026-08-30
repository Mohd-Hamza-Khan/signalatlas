"""
SignalAtlas Database Models and Migrations

This module contains:
- SQLAlchemy models for PostgreSQL
- Alembic migration configuration
- Database connection management
"""

from typing import Optional
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import uuid

Base = declarative_base()


# ============================================================================
# Core Tables
# ============================================================================

class Source(Base):
    """Data source configuration."""
    __tablename__ = "sources"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    base_url = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)  # startup, product, paper, news, job
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CrawlRun(Base):
    """Crawl run metadata."""
    __tablename__ = "crawl_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(BigInteger, ForeignKey("sources.id"))
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(50), nullable=False)  # pending, running, completed, failed
    discovered_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    source = relationship("Source", backref="crawl_runs")


# ============================================================================
# Raw Documents
# ============================================================================

class RawDocument(Base):
    """Raw crawled documents."""
    __tablename__ = "raw_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(BigInteger, ForeignKey("sources.id"))
    url = Column(Text, nullable=False)
    normalized_url = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA-256
    http_status = Column(Integer)
    content_type = Column(String(100))
    raw_html = Column(Text)
    clean_text = Column(Text)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    metadata = Column(JSON, default={})

    source = relationship("Source", backref="raw_documents")

    __table_args__ = (
        Index("idx_raw_documents_url", "normalized_url"),
        Index("idx_raw_documents_hash", "content_hash"),
    )


# ============================================================================
# Entity Tables
# ============================================================================

class Startup(Base):
    """Startup entities."""
    __tablename__ = "startups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    employee_count = Column(Integer)
    website = Column(String(500))
    source_url = Column(Text, nullable=False)
    source_name = Column(String(255), nullable=False)
    provenance = Column(JSON, default={})
    collected_at = Column(DateTime(timezone=True), nullable=False)


class Product(Base):
    """Product entities."""
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_name = Column(String(255), nullable=False)
    startup_id = Column(UUID(as_uuid=True), ForeignKey("startups.id"))
    pricing_model = Column(String(20))  # FREE, FREEMIUM, PAID, ENTERPRISE
    website = Column(String(500))
    description = Column(Text)
    source_url = Column(Text, nullable=False)
    provenance = Column(JSON, default={})
    collected_at = Column(DateTime(timezone=True), nullable=False)

    startup = relationship("Startup", backref="products")


class ResearchPaper(Base):
    """Research paper entities."""
    __tablename__ = "research_papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(100), unique=True)  # arXiv ID, etc.
    title = Column(Text, nullable=False)
    authors = Column(JSON, default=[])
    paper_url = Column(Text, nullable=False, unique=True)
    github_url = Column(Text)
    github_stars = Column(Integer)
    published_date = Column(DateTime(timezone=True))
    github_match_confidence = Column(Float(precision=5, decimal_return_scale=4))
    provenance = Column(JSON, default={})
    collected_at = Column(DateTime(timezone=True), nullable=False)


class Job(Base):
    """Job posting entities."""
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(Text, nullable=False, unique=True)
    company = Column(String(255), nullable=False)
    role = Column(String(255), nullable=False)
    published_at = Column(DateTime(timezone=True))
    is_remote = Column(Boolean)
    role_family = Column(String(100))
    date_source = Column(String(50))
    date_confidence = Column(Float(precision=5, decimal_return_scale=4))
    content_hash = Column(String(64))
    provenance = Column(JSON, default={})
    collected_at = Column(DateTime(timezone=True), nullable=False)


class News(Base):
    """News article entities."""
    __tablename__ = "news"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(Text, nullable=False, unique=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True))
    date_source = Column(String(50))
    date_confidence = Column(Float(precision=5, decimal_return_scale=4))
    content_hash = Column(String(64))
    provenance = Column(JSON, default={})
    collected_at = Column(DateTime(timezone=True), nullable=False)


# ============================================================================
# Entity Resolution
# ============================================================================

class EntityAlias(Base):
    """Entity alias mappings."""
    __tablename__ = "entity_aliases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    raw_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False)
    canonical_name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)  # STARTUP, PRODUCT, etc.
    method = Column(String(50), nullable=False)  # exact, alias, fuzzy, embedding, llm
    confidence = Column(Float(precision=5, decimal_return_scale=4), nullable=False)


class EntityMappingLog(Base):
    """Entity mapping audit log."""
    __tablename__ = "entity_mapping_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_name = Column(String(255), nullable=False)
    canonical_name = Column(String(255))
    entity_type = Column(String(50), nullable=False)
    method = Column(String(50), nullable=False)
    confidence = Column(Float(precision=5, decimal_return_scale=4))
    source_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ============================================================================
# GitHub
# ============================================================================

class GitHubRepository(Base):
    """GitHub repository data."""
    __tablename__ = "github_repositories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_url = Column(Text, nullable=False, unique=True)
    owner = Column(String(255), nullable=False)
    repo = Column(String(255), nullable=False)
    stars = Column(Integer)
    description = Column(Text)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    raw_response = Column(JSON)
