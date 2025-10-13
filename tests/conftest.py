import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.base import Base
from main import app
from app.core.dependencies import get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create async engine for testing
test_engine = create_async_engine(TEST_DATABASE_URL, future=True)
TestSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables before tests and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="module")
def client():
    """Create a TestClient that uses the test DB"""

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# ---- Mock email sending ----
# @pytest.fixture(autouse=True)
# def mock_send_email(monkeypatch):
#     async def fake_send_email(to, subject, template, context):
#         # Simulate successful email send without network call
#         return True

#     monkeypatch.setattr(email, "send_email", fake_send_email)


# # ---- Async HTTP client ----
# @pytest.fixture
# async def client():
#     async with AsyncClient(app=app, base_url="http://test") as c:
#         yield c
