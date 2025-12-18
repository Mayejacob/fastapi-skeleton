from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.session import init_db
from app.utils.caching import cache
from app.utils.logging import get_logger
from app.core.tasks import setup_scheduled_tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger = get_logger()
    logger.info(f"Startup: {app.title} v{app.version} starting...")

    # Initialize database
    await init_db()

    # Initialize cache (Redis if configured)
    await cache.init_redis()

    # Initialize scheduled tasks
    scheduler = setup_scheduled_tasks()

    logger.info("✓ Application startup complete")

    yield

    # Shutdown
    logger.info("Shutdown: App shutting down...")

    # Shutdown scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("✓ Scheduler shutdown complete")

    # Close cache connections
    await cache.close()

    logger.info("✓ Application shutdown complete")
