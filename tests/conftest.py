"""
Pytest configuration and fixtures for testing

Uses SQLite in-memory database for fast, isolated tests
"""
import asyncio
import pytest
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.config import Settings
from main import app
from app.core.dependencies import get_db
from app.core.security import get_password_hash
from app.db.models.user import User


# Test database URL (SQLite in-memory)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Test settings
test_settings = Settings(
    DATABASE_URL=TEST_DATABASE_URL,
    SECRET_KEY="test-secret-key-for-testing-only-1234567890",
    ALGORITHM="HS256",
    ACCESS_TOKEN_EXPIRE_MINUTES=30,
    ENVIRONMENT="test",
    EMAIL_HOST="smtp.test.com",
    EMAIL_PORT=587,
    EMAIL_USERNAME="test@test.com",
    EMAIL_PASSWORD="test123",
    EMAIL_FROM="noreply@test.com",
    SUPPRESS_SEND=1,  # Mock email sending
)

# Override settings for tests
from app.core import config
config.settings = test_settings


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Database engine fixture
@pytest.fixture(scope="function")
async def engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Required for in-memory SQLite
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# Database session fixture
@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


# Test client fixture
@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# Test user fixtures
@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create a verified test user"""
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def unverified_user(db_session: AsyncSession) -> User:
    """Create an unverified test user"""
    user = User(
        id=uuid.uuid4(),
        username="unverified",
        email="unverified@example.com",
        hashed_password=get_password_hash("testpassword123"),
        is_active=False,
        email_verified_at=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user"""
    user = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword123"),
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# Authentication token fixture
@pytest.fixture(scope="function")
async def auth_token(test_user: User, db_session: AsyncSession) -> str:
    """Create valid access token for test user"""
    from app.services.token import TokenService

    token_service = TokenService()
    access_token, _ = await token_service.create_access_token(
        user_id=test_user.id,
        email=test_user.email,
        db=db_session,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    await db_session.commit()
    return access_token


@pytest.fixture(scope="function")
async def admin_token(admin_user: User, db_session: AsyncSession) -> str:
    """Create valid access token for admin user"""
    from app.services.token import TokenService

    token_service = TokenService()
    access_token, _ = await token_service.create_access_token(
        user_id=admin_user.id,
        email=admin_user.email,
        db=db_session,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    await db_session.commit()
    return access_token


