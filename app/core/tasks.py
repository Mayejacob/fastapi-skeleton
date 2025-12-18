"""
Scheduled background tasks
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import SessionLocal
from app.services.token import TokenService
from app.utils.logging import get_logger

logger = get_logger()


async def cleanup_expired_tokens():
    """
    Cleanup expired access and refresh tokens from database

    This task runs daily at 2:00 AM to remove expired tokens
    and keep the database clean
    """
    logger.info("Starting expired token cleanup task...")

    try:
        async with SessionLocal() as db:
            token_service = TokenService()
            count = await token_service.cleanup_expired_tokens(db)
            await db.commit()

            logger.info(f"✓ Cleaned up {count} expired token(s)")

    except Exception as e:
        logger.error(f"✗ Token cleanup task failed: {e}")
        import traceback
        traceback.print_exc()


def setup_scheduled_tasks() -> AsyncIOScheduler:
    """
    Setup and start scheduled background tasks

    Returns:
        AsyncIOScheduler: The initialized scheduler instance
    """
    scheduler = AsyncIOScheduler()

    # Task 1: Cleanup expired tokens daily at 2:00 AM
    scheduler.add_job(
        cleanup_expired_tokens,
        trigger=CronTrigger(hour=2, minute=0),
        id="cleanup_expired_tokens",
        name="Cleanup Expired Tokens",
        replace_existing=True,
    )

    # Start the scheduler
    scheduler.start()

    logger.info("✓ Scheduled tasks initialized")
    logger.info("  - cleanup_expired_tokens: Daily at 2:00 AM")

    return scheduler
