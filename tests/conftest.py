"""
Pytest configuration and fixtures for testing

Uses SQLite in-memory database for fast, isolated tests
"""
import asyncio
import pytest
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from pathlib import Path

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
    UPLOAD_DIR="test_uploads",
    MAX_UPLOAD_SIZE_MB=5,
    ALLOWED_UPLOAD_TYPES="image/jpeg,image/png,application/pdf",
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


# File upload fixtures
@pytest.fixture(scope="function")
def temp_upload_dir(tmp_path):
    """Create temporary upload directory"""
    upload_dir = tmp_path / "test_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    yield upload_dir
    # Cleanup handled by tmp_path


@pytest.fixture(scope="function")
def sample_image_file(tmp_path):
    """Create a sample image file for testing"""
    file_path = tmp_path / "test_image.jpg"
    # Create a minimal JPEG file (1x1 pixel)
    jpeg_data = (
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
        b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
        b'\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00'
        b'\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10'
        b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\x00\xff\xd9'
    )
    file_path.write_bytes(jpeg_data)
    return file_path


@pytest.fixture(scope="function")
def sample_pdf_file(tmp_path):
    """Create a sample PDF file for testing"""
    file_path = tmp_path / "test_document.pdf"
    # Create a minimal PDF file
    pdf_data = (
        b'%PDF-1.4\n'
        b'1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
        b'2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n'
        b'3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n'
        b'xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n'
        b'0000000056 00000 n\n0000000115 00000 n\n'
        b'trailer<</Size 4/Root 1 0 R>>\nstartxref\n198\n%%EOF'
    )
    file_path.write_bytes(pdf_data)
    return file_path


# Cleanup fixture
@pytest.fixture(scope="function", autouse=True)
def cleanup():
    """Cleanup after each test"""
    yield
    # Clean up test upload directory
    upload_dir = Path("test_uploads")
    if upload_dir.exists():
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)
