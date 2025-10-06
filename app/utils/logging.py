from loguru import logger

from app.core.config import settings

logger.add("logs/app.log", rotation="500 MB", level=settings.LOG_LEVEL)


def get_logger():
    return logger
