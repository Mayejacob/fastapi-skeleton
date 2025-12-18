import importlib
import pkgutil
from pathlib import Path
from typing import Type, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seeders.base import BaseSeeder
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger()


class SeederRunner:
    """Auto-discovers and runs database seeders"""

    def __init__(self, db: AsyncSession, environment: str = None):
        """
        Initialize seeder runner

        Args:
            db: Database session
            environment: Environment name (development, test, production)
                        If None, uses ENVIRONMENT from settings or defaults to 'development'
        """
        self.db = db
        self.environment = environment or getattr(
            settings, "ENVIRONMENT", "development"
        )
        self.seeders: List[Type[BaseSeeder]] = []

    def discover_seeders(self) -> None:
        """
        Auto-discover all seeder classes in the seeders directory

        Scans the seeders directory for Python modules and finds
        all classes that inherit from BaseSeeder
        """
        seeders_path = Path(__file__).parent
        discovered_count = 0

        # Iterate through all modules in the seeders directory
        for _, module_name, _ in pkgutil.iter_modules([str(seeders_path)]):
            # Skip base, runner, and __init__ modules
            if module_name in ["base", "runner", "__init__"]:
                continue

            try:
                # Import the module
                module = importlib.import_module(f"app.db.seeders.{module_name}")

                # Find all seeder classes in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # Check if it's a seeder class (subclass of BaseSeeder but not BaseSeeder itself)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSeeder)
                        and attr is not BaseSeeder
                    ):
                        self.seeders.append(attr)
                        discovered_count += 1

            except Exception as e:
                logger.error(f"Error importing seeder module {module_name}: {e}")

        # Sort seeders by order
        self.seeders.sort(key=lambda s: s.order)

        logger.info(
            f"Discovered {discovered_count} seeder(s) for environment: {self.environment}"
        )

    async def run_all(self) -> None:
        """
        Run all discovered seeders in order

        Raises:
            Exception: If any seeder fails
        """
        # Discover seeders if not already done
        if not self.seeders:
            self.discover_seeders()

        if not self.seeders:
            logger.warning("No seeders found")
            return

        logger.info(f"Running {len(self.seeders)} seeder(s)...")

        for seeder_class in self.seeders:
            seeder = seeder_class(self.db)

            # Check if seeder should run in current environment
            if not seeder.should_run(self.environment):
                logger.info(
                    f"⊘ Skipping {seeder.get_name()} (not for {self.environment} environment)"
                )
                continue

            # Run the seeder
            logger.info(f"→ Running {seeder.get_name()}...")
            try:
                await seeder.run()
                logger.info(f"✓ {seeder.get_name()} completed successfully")
            except Exception as e:
                logger.error(f"✗ {seeder.get_name()} failed: {e}")
                raise

        logger.info("All seeders completed!")

    async def run_specific(self, seeder_name: str) -> None:
        """
        Run a specific seeder by name

        Args:
            seeder_name: Name of the seeder class to run

        Raises:
            ValueError: If seeder not found
            Exception: If seeder fails
        """
        # Discover seeders if not already done
        if not self.seeders:
            self.discover_seeders()

        # Find the specific seeder
        for seeder_class in self.seeders:
            if seeder_class.get_name() == seeder_name:
                seeder = seeder_class(self.db)

                logger.info(f"→ Running {seeder.get_name()}...")
                try:
                    await seeder.run()
                    logger.info(f"✓ {seeder.get_name()} completed successfully")
                except Exception as e:
                    logger.error(f"✗ {seeder.get_name()} failed: {e}")
                    raise

                return

        # Seeder not found - log warning instead of raising
        available_seeders = [s.get_name() for s in self.seeders]
        logger.warning(
            f"Seeder '{seeder_name}' not found. Available seeders: {', '.join(available_seeders)}"
        )
