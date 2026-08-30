"""
SignalAtlas Configuration Module

Centralized configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/signalatlas",
        description="PostgreSQL connection URL"
    )

    # GitHub
    GITHUB_TOKEN: Optional[str] = Field(
        default=None,
        description="GitHub personal access token"
    )

    # OpenRouter (LLM Provider)
    OPENROUTER_API_KEY: str = Field(
        default="",
        description="OpenRouter API key for LLM access"
    )
    OPENROUTER_APP_NAME: str = Field(
        default="SignalAtlas",
        description="Application name for OpenRouter tracking"
    )
    OPENROUTER_APP_VERSION: str = Field(
        default="1.0",
        description="Application version for OpenRouter tracking"
    )

    # Google Sheets
    GOOGLE_SHEETS_CREDENTIALS: Optional[str] = Field(
        default=None,
        description="Google Sheets service account credentials JSON"
    )

    # Optional: Redis (for Phase 2)
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis connection URL (optional for Phase 1)"
    )

    # Application
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
