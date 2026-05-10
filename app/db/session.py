from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base


def _make_engine() -> AsyncEngine:
    url = settings.DATABASE_URL

    # SQLite doesn't support connection pool options
    if url.startswith("sqlite"):
        return create_async_engine(url)

    return create_async_engine(
        url,
        pool_size=10,        # persistent connections kept open
        max_overflow=20,     # extra connections allowed above pool_size
        pool_timeout=30,     # seconds to wait for a free connection
        pool_recycle=1800,   # recycle connections after 30 minutes
        pool_pre_ping=True,  # test connection liveness before using it
    )


engine: AsyncEngine = _make_engine()
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
