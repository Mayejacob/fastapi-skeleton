from abc import ABC, abstractmethod
from typing import ClassVar
from sqlalchemy.ext.asyncio import AsyncSession


class BaseSeeder(ABC):
    """Base class for all seeders"""

    # Execution order (lower number runs first)
    order: ClassVar[int] = 100

    # Environments where this seeder should run
    environments: ClassVar[list] = ["development", "test"]

    def __init__(self, db: AsyncSession):
        self.db = db

    @abstractmethod
    async def seed(self) -> None:
        """
        Implement seeding logic in subclasses

        This method should create/insert the necessary data
        """
        pass

    async def run(self) -> None:
        """
        Run the seeder

        Calls seed() and commits the transaction
        """
        await self.seed()
        await self.db.commit()

    def should_run(self, environment: str) -> bool:
        """
        Check if seeder should run in the current environment

        Args:
            environment: Current environment (development, test, production, etc.)

        Returns:
            True if seeder should run, False otherwise
        """
        return environment in self.environments

    @classmethod
    def get_name(cls) -> str:
        """
        Get seeder name

        Returns:
            Class name
        """
        return cls.__name__
