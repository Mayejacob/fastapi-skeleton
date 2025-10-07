import os
from loguru import logger

from app.core.config import settings

os.makedirs(os.path.dirname(settings.LOG_FILE_PATH), exist_ok=True)
logger.add(settings.LOG_FILE_PATH, rotation="500 MB", level=settings.LOG_LEVEL)


def get_logger():
    return logger
