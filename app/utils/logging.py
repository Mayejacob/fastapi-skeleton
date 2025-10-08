import os
from loguru import logger
from app.core.config import settings

# Base directory for logs
LOG_DIR = getattr(settings, "LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Main app log
APP_LOG_PATH = os.path.join(LOG_DIR, "app.log")
logger.add(
    APP_LOG_PATH,
    rotation="10 MB",
    level=settings.LOG_LEVEL,
    enqueue=True,
    backtrace=True,
    diagnose=False,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

# DB error log
DB_LOG_PATH = os.path.join(LOG_DIR, "db_errors.log")
logger.add(
    DB_LOG_PATH,
    rotation="10 MB",
    level="WARNING",
    enqueue=True,
    backtrace=True,
    diagnose=False,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

# Startup log
STARTUP_LOG_PATH = os.path.join(LOG_DIR, "startup", "startup.log")
os.makedirs(os.path.dirname(STARTUP_LOG_PATH), exist_ok=True)
logger.add(
    STARTUP_LOG_PATH,
    rotation="10 MB",
    level="INFO",
    enqueue=True,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


def get_logger():
    """Return the global logger."""
    return logger
