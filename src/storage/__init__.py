"""
SignalAtlas PostgreSQL Storage

Provides database models and storage utilities using SQLAlchemy.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Type, TypeVar

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
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func as sql_func
from structlog import get_logger

from ..config import settings

logger = get_logger(__name__)

# SQLAlchemy base
Base = declarative_base()


# ============================================================================
# Database Models
# ============================================================================

class Source(Base):
    """Data source."""
    __tablename__ = "sources"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    base_url = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=sql_func.now(),
        nullable=False,
    )


class RawDocument(Base):
    """Raw document storage."""
    __tablename__ = "raw_documents"

    id = Column(String(36), primary_key=True)
    source_id = Column(BigInteger, ForeignKey("sources.id"))
    url = Column(Text, nullable=False)
    normalized_url = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    http_status = Column(Integer)
    content_type = Column(String(100))
    raw_html = Column(Text)
    clean_text = Column(Text)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    first_seen_at = Column(
        DateTime(timezone=True),
        server_default=sql_func.now(),
        nullable=False,
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        server_default=sql_func.now(),
        nullable=False,
    )
    extra_metadata = Column(JSON, default={}, nullable=False)

    __table_args__ = (
        Index("idx_raw_documents_url", "normalized_url"),
        Index("idx_raw_documents_hash", "content_hash"),
    )


class Startup(Base):
    """Startup entity."""
    __tablename__ = "startups"

    id = Column(String(36), primary_key=True)
    canonical_name = Column(String(500), nullable=False, unique=True)
    description = Column(Text)
    employee_count = Column(Integer)
    website = Column(String(500))
    founded_year = Column(Integer)
    location = Column(String(500))
    batch = Column(String(50))
    source_url = Column(Text, nullable=False)
    source_name = Column(String(255), nullable=False)
    provenance = Column(JSON, default={}, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)


class Product(Base):
    """Product entity."""
    __tablename__ = "products"

    id = Column(String(36), primary_key=True)
    product_name = Column(String(500), nullable=False)
    startup_id = Column(String(36), ForeignKey("startups.id"))
    pricing_model = Column(String(50))
    website = Column(String(500))
    description = Column(Text)
    tagline = Column(String(500))
    source_url = Column(Text, nullable=False)
    provenance = Column(JSON, default={}, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)


class ResearchPaper(Base):
    """Research paper entity."""
    __tablename__ = "research_papers"

    id = Column(String(36), primary_key=True)
    external_id = Column(String(255), unique=True)
    title = Column(Text, nullable=False)
    authors = Column(JSON, default=[], nullable=False)
    paper_url = Column(Text, nullable=False, unique=True)
    github_url = Column(String(500))
    github_stars = Column(Integer)
    github_match_confidence = Column(Float)
    published_date = Column(DateTime(timezone=True))
    abstract = Column(Text)
    category = Column(String(255))
    provenance = Column(JSON, default={}, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)


class Job(Base):
    """Job posting entity."""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    source_url = Column(Text, nullable=False, unique=True)
    company = Column(String(500), nullable=False)
    role = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True))
    is_remote = Column(Boolean)
    role_family = Column(String(50))
    location = Column(String(500))
    description = Column(Text)
    application_url = Column(String(500))
    date_source = Column(String(50))
    date_confidence = Column(Float)
    content_hash = Column(String(64))
    provenance = Column(JSON, default={}, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)


class News(Base):
    """News article entity."""
    __tablename__ = "news"

    id = Column(String(36), primary_key=True)
    source_url = Column(Text, nullable=False, unique=True)
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True))
    author = Column(String(500))
    date_source = Column(String(50))
    date_confidence = Column(Float)
    content_hash = Column(String(64))
    provenance = Column(JSON, default={}, nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)


class EntityAlias(Base):
    """Entity alias mapping."""
    __tablename__ = "entity_aliases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    raw_name = Column(String(500), nullable=False)
    normalized_name = Column(String(500), nullable=False)
    canonical_name = Column(String(500), nullable=False)
    entity_type = Column(String(50), nullable=False)
    method = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)


class EntityMappingLog(Base):
    """Entity mapping log."""
    __tablename__ = "entity_mapping_logs"

    id = Column(String(36), primary_key=True)
    raw_name = Column(String(500), nullable=False)
    canonical_name = Column(String(500))
    entity_type = Column(String(50), nullable=False)
    method = Column(String(50), nullable=False)
    confidence = Column(Float)
    source_url = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        server_default=sql_func.now(),
        nullable=False,
    )


class GitHubRepository(Base):
    """GitHub repository data."""
    __tablename__ = "github_repositories"

    id = Column(String(36), primary_key=True)
    repository_url = Column(Text, nullable=False, unique=True)
    owner = Column(String(255), nullable=False)
    repo = Column(String(255), nullable=False)
    stars = Column(Integer)
    description = Column(Text)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    raw_response = Column(JSON)


# ============================================================================
# Database Engine
# ============================================================================

class Database:
    """
    Database connection manager.
    """

    def __init__(self):
        self.engine = None
        self.async_session = None

    async def init(self) -> None:
        """Initialize database connection."""
        if self.engine is None:
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                future=True,
            )
            self.async_session = sessionmaker(
                self.engine,
                expire_on_commit=False,
                class_=AsyncSession,
            )
            logger.info("Database initialized")

    async def close(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.async_session = None
            logger.info("Database closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session.

        Usage:
            async with db.get_session() as session:
                # use session
        """
        if self.async_session is None:
            await self.init()

        session = self.async_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Global database instance
db = Database()


# ============================================================================
# Initialization
# ============================================================================

async def init_db() -> None:
    """
    Initialize database tables.
    """
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")


async def drop_db() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    """
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        logger.warning("Database tables dropped")


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session context manager.

    Usage:
        async with get_db_context() as session:
            # use session
    """
    await db.init()
    async with db.get_session() as session:
        yield session


# ============================================================================
# Storage Utilities
# ============================================================================

class Storage:
    """
    High-level storage utilities.
    """

    @staticmethod
    async def save_record(record: Dict[str, Any], model: Type[Base]) -> Base:
        """Save a record to the database."""
        async with get_db_context() as session:
            # Check for existing record
            existing = await session.execute(
                select(model).where(
                    getattr(model, "source_url") == record.get("source", {}).get("url")
                )
            )
            existing = existing.scalar_one_or_none()

            if existing:
                # Update existing
                for key, value in record.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                return existing

            # Create new
            db_record = model(**record)
            session.add(db_record)
            await session.commit()
            await session.refresh(db_record)
            return db_record

    @staticmethod
    async def get_record(model: Type[Base], record_id: str) -> Optional[Base]:
        """Get a record by ID."""
        async with get_db_context() as session:
            result = await session.execute(
                select(model).where(model.id == record_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def list_records(
        model: Type[Base],
        limit: int = 100,
        offset: int = 0,
    ) -> List[Base]:
        """List records with pagination."""
        async with get_db_context() as session:
            result = await session.execute(
                select(model).order_by(model.collected_at.desc()).limit(limit).offset(offset)
            )
            return result.scalars().all()

    @staticmethod
    async def count_records(model: Type[Base]) -> int:
        """Count records of a type."""
        async with get_db_context() as session:
            result = await session.execute(select(func.count()).select_from(model))
            return result.scalar()


# Singleton storage instance
storage = Storage()
