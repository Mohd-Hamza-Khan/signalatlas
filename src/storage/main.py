"""
SignalAtlas Database Initialization Script

Run this script to initialize the database schema.

Usage:
    python -m signalatlas.src.storage
"""

import asyncio
from ..storage import init_db, drop_db


async def main() -> None:
    """Main entry point for database initialization."""
    import argparse

    parser = argparse.ArgumentParser(description="SignalAtlas Database Management")
    parser.add_argument("--init", action="store_true", help="Initialize database tables")
    parser.add_argument("--drop", action="store_true", help="Drop all database tables")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate all tables")

    args = parser.parse_args()

    if args.recreate:
        print("Dropping existing tables...")
        await drop_db()
        print("Creating new tables...")
        await init_db()
    elif args.drop:
        print("Dropping all tables...")
        await drop_db()
    elif args.init:
        print("Creating tables...")
        await init_db()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
