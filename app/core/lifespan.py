from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import init_db
from app.utils.caching import cache
from app.utils.logging import get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await cache.init_redis()
    logger = get_logger()
    logger.info(f"Startup: {app.title} v{app.version} starting...")
    yield
    # Shutdown
    await cache.close()
    logger.info("Shutdown: App shutting down...")
