"""
Tests for the seeder system

Tests seeder auto-discovery, execution order, and idempotency
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seeders.runner import SeederRunner
from app.db.seeders.user_seeder import UserSeeder
from app.db.models.user import User


class TestSeederDiscovery:
    """Test seeder auto-discovery"""

    @pytest.mark.asyncio
    async def test_discover_seeders(self, db_session: AsyncSession):
        """Test that seeder runner discovers seeders"""
        runner = SeederRunner(db_session, environment="test")
        runner.discover_seeders()

        assert len(runner.seeders) > 0
        # Check that UserSeeder is discovered
        seeder_names = [s.__name__ for s in runner.seeders]
        assert "UserSeeder" in seeder_names

    @pytest.mark.asyncio
    async def test_seeder_execution_order(self, db_session: AsyncSession):
        """Test that seeders are sorted by order attribute"""
        runner = SeederRunner(db_session, environment="test")
        runner.discover_seeders()

        # Check that seeders are sorted by order
        orders = [seeder.order for seeder in runner.seeders]
        assert orders == sorted(orders)


class TestUserSeeder:
    """Test UserSeeder specifically"""

    @pytest.mark.asyncio
    async def test_user_seeder_creates_users(self, db_session: AsyncSession):
        """Test that UserSeeder creates users"""
        # Run seeder
        seeder = UserSeeder(db_session)
        await seeder.run()

        # Check users were created
        result = await db_session.execute(select(User))
        users = result.scalars().all()

        assert len(users) == 3  # admin, test, john
        emails = [u.email for u in users]
        assert "admin@example.com" in emails
        assert "test@example.com" in emails
        assert "john@example.com" in emails

    @pytest.mark.asyncio
    async def test_user_seeder_idempotent(self, db_session: AsyncSession):
        """Test that UserSeeder is idempotent (can run multiple times)"""
        seeder = UserSeeder(db_session)

        # Run first time
        await seeder.run()
        result = await db_session.execute(select(User))
        count_first = len(result.scalars().all())

        # Run second time
        await seeder.run()
        result = await db_session.execute(select(User))
        count_second = len(result.scalars().all())

        # Should have same count (no duplicates)
        assert count_first == count_second == 3

    @pytest.mark.asyncio
    async def test_user_seeder_verifies_users(self, db_session: AsyncSession):
        """Test that UserSeeder creates verified users"""
        seeder = UserSeeder(db_session)
        await seeder.run()

        result = await db_session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        admin = result.scalar_one()

        assert admin.is_active is True
        assert admin.email_verified_at is not None

    @pytest.mark.asyncio
    async def test_user_seeder_hashes_passwords(self, db_session: AsyncSession):
        """Test that UserSeeder hashes passwords"""
        seeder = UserSeeder(db_session)
        await seeder.run()

        result = await db_session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        admin = result.scalar_one()

        # Password should be hashed (not plain text)
        assert admin.hashed_password != "admin123"
        assert admin.hashed_password.startswith("$2b$")  # Bcrypt hash


class TestSeederRunner:
    """Test SeederRunner execution"""

    @pytest.mark.asyncio
    async def test_run_all_seeders(self, db_session: AsyncSession):
        """Test running all seeders"""
        runner = SeederRunner(db_session, environment="test")
        await runner.run_all()

        # Check that users were created
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) >= 3

    @pytest.mark.asyncio
    async def test_run_specific_seeder(self, db_session: AsyncSession):
        """Test running a specific seeder by name"""
        runner = SeederRunner(db_session, environment="test")
        await runner.run_specific("UserSeeder")

        # Check that users were created
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 3

    @pytest.mark.asyncio
    async def test_run_nonexistent_seeder(self, db_session: AsyncSession):
        """Test running a seeder that doesn't exist"""
        runner = SeederRunner(db_session, environment="test")

        # Should not raise exception, just log warning
        await runner.run_specific("NonExistentSeeder")

        # No users should be created
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 0


class TestSeederEnvironmentFiltering:
    """Test environment-based seeder filtering"""

    @pytest.mark.asyncio
    async def test_seeder_runs_in_test_environment(self, db_session: AsyncSession):
        """Test that seeder runs in test environment"""
        seeder = UserSeeder(db_session)
        assert seeder.should_run("test") is True

    @pytest.mark.asyncio
    async def test_seeder_runs_in_development_environment(
        self, db_session: AsyncSession
    ):
        """Test that seeder runs in development environment"""
        seeder = UserSeeder(db_session)
        assert seeder.should_run("development") is True

    @pytest.mark.asyncio
    async def test_seeder_skips_production_environment(self, db_session: AsyncSession):
        """Test that seeder doesn't run in production by default"""
        seeder = UserSeeder(db_session)
        # UserSeeder only runs in dev and test
        assert seeder.should_run("production") is False

    @pytest.mark.asyncio
    async def test_runner_filters_by_environment(self, db_session: AsyncSession):
        """Test that runner filters seeders by environment"""
        # Run in production (UserSeeder should be skipped)
        runner = SeederRunner(db_session, environment="production")
        runner.discover_seeders()

        # UserSeeder should not run in production
        await runner.run_all()

        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 0  # No users created


class TestSeederErrorHandling:
    """Test seeder error handling"""

    @pytest.mark.asyncio
    async def test_seeder_commits_on_success(self, db_session: AsyncSession):
        """Test that seeder commits changes on success"""
        seeder = UserSeeder(db_session)
        await seeder.run()

        # Changes should be committed
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) > 0

    @pytest.mark.asyncio
    async def test_multiple_seeder_runs_safe(self, db_session: AsyncSession):
        """Test that running seeders multiple times is safe"""
        runner = SeederRunner(db_session, environment="test")

        # Run multiple times
        await runner.run_all()
        await runner.run_all()
        await runner.run_all()

        # Should still have same number of users (idempotent)
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        assert len(users) == 3  # Not 9


class TestSeederAttributes:
    """Test seeder class attributes"""

    def test_user_seeder_has_order(self):
        """Test that UserSeeder has order attribute"""
        assert hasattr(UserSeeder, "order")
        assert isinstance(UserSeeder.order, int)
        assert UserSeeder.order == 10

    def test_user_seeder_has_environments(self):
        """Test that UserSeeder has environments attribute"""
        assert hasattr(UserSeeder, "environments")
        assert isinstance(UserSeeder.environments, list)
        assert "development" in UserSeeder.environments
        assert "test" in UserSeeder.environments

    def test_user_seeder_has_seed_method(self):
        """Test that UserSeeder has seed method"""
        assert hasattr(UserSeeder, "seed")
        assert callable(UserSeeder.seed)
