"""
SignalAtlas Logging Configuration

Structured logging using structlog.
"""

import logging
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.processors import JSONRenderer, KeyValueRenderer, TimeStamper
from structlog.stdlib import LoggerFactory

from ..config import settings


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    Uses structlog for structured, context-aware logging.
    Outputs JSON in production, console format in development.
    """
    # Shared processors for all loggers
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso"),
    ]

    # Choose renderer based on environment
    if settings.DEBUG:
        # Development: console-friendly format
        renderer = KeyValueRenderer(
            key_order=["event", "logger", "level", "timestamp"],
            drop_missing=True,
        )
    else:
        # Production: JSON format
        renderer = JSONRenderer()

    # Add renderer to processors
    shared_processors.append(renderer)

    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(message)s",
    )

    # Set level for root logger
    logging.getLogger().setLevel(
        getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    )

    # Reduce noise from third-party libraries
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        structlog.BoundLogger instance
    """
    return structlog.get_logger(name)


# Configure logging on import
configure_logging()
