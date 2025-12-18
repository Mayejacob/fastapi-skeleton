#!/usr/bin/env python3
"""
Database Seeder CLI

Usage:
    python seed.py                  # Run all seeders
    python seed.py UserSeeder       # Run specific seeder
    python seed.py --env production # Run in production environment (if allowed)
"""

import asyncio
import sys

from app.db.session import SessionLocal
from app.db.seeders.runner import SeederRunner
from app.utils.logging import get_logger

logger = get_logger()


async def main():
    """Main seeder function"""

    # Parse arguments
    environment = None
    seeder_name = None

    for arg in sys.argv[1:]:
        if arg.startswith("--env="):
            environment = arg.split("=")[1]
        elif arg == "--help" or arg == "-h":
            print(__doc__)
            return
        else:
            seeder_name = arg

    # Create database session
    async with SessionLocal() as db:
        # Create seeder runner
        runner = SeederRunner(db, environment=environment)

        try:
            if seeder_name:
                # Run specific seeder
                logger.info(f"Running specific seeder: {seeder_name}")
                await runner.run_specific(seeder_name)
            else:
                # Run all seeders
                logger.info("Running all seeders...")
                await runner.run_all()

            logger.info("Seeding completed successfully!")

        except ValueError as e:
            logger.error(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
