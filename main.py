#!/usr/bin/env python3
"""
SignalAtlas Main Entry Point

Run the FrontierAtlas Intelligence Ingestion Engine.

Usage:
    python -m signalatlas.main [command] [options]

Commands:
    crawl        Run all crawlers
    extract      Run extraction on stored documents
    resolve      Run entity resolution
    serve        Start the API server
    test         Run tests
    init-db      Initialize database
    drop-db      Drop database tables
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from structlog import get_logger

from src.config import settings
from src.storage import db, init_db, drop_db
from src.pipeline.runner import PipelineRunner

logger = get_logger(__name__)


async def run_crawl() -> None:
    """Run all crawlers."""
    logger.info("Starting crawl...")
    runner = PipelineRunner()
    await runner.run_crawlers()
    logger.info("Crawl completed")


async def run_extraction() -> None:
    """Run extraction on stored documents."""
    logger.info("Starting extraction...")
    runner = PipelineRunner()
    await runner.run_extraction()
    logger.info("Extraction completed")


async def run_resolution() -> None:
    """Run entity resolution."""
    logger.info("Starting entity resolution...")
    runner = PipelineRunner()
    await runner.run_resolution()
    logger.info("Entity resolution completed")


async def run_full_pipeline() -> None:
    """Run the full pipeline."""
    logger.info("Starting full pipeline...")
    runner = PipelineRunner()
    await runner.run()
    logger.info("Full pipeline completed")


async def run_tests() -> None:
    """Run tests."""
    logger.info("Running tests...")
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=os.path.dirname(__file__),
    )
    sys.exit(result.returncode)


async def run_init_db() -> None:
    """Initialize database."""
    logger.info("Initializing database...")
    await db.init()
    await init_db()
    logger.info("Database initialized")


async def run_drop_db() -> None:
    """Drop database tables."""
    logger.info("Dropping database tables...")
    await db.init()
    await drop_db()
    logger.info("Database tables dropped")


async def run_serve() -> None:
    """Start the API server."""
    logger.info("Starting API server...")
    from signalatlas.src.api import app

    import uvicorn

    await uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="FrontierAtlas Intelligence Ingestion Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m signalatlas.main crawl
    python -m signalatlas.main extract
    python -m signalatlas.main full
    python -m signalatlas.main init-db
    python -m signalatlas.main serve
        """,
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=["crawl", "extract", "resolve", "full", "test", "init-db", "drop-db", "serve"],
        default="full",
        help="Command to run (default: full)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file",
    )

    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Configure logging
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logger.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    logger.info("SignalAtlas starting...")
    logger.info(f"Command: {args.command}")

    # Load config if specified
    if args.config:
        logger.info(f"Loading config from: {args.config}")

    # Route command
    commands = {
        "crawl": run_crawl,
        "extract": run_extraction,
        "resolve": run_resolution,
        "full": run_full_pipeline,
        "test": run_tests,
        "init-db": run_init_db,
        "drop-db": run_drop_db,
        "serve": run_serve,
    }

    command_fn = commands.get(args.command)
    if command_fn:
        await command_fn()
    else:
        logger.error(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
