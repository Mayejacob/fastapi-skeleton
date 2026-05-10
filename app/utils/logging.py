import os
from loguru import logger

# Base directory for logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Main app log
APP_LOG_PATH = os.path.join(LOG_DIR, "app.log")
logger.add(
    APP_LOG_PATH,
    rotation="1 day",
    retention="14 days",
    compression="gz",
    level="INFO",
    enqueue=True,
    backtrace=True,
    diagnose=False,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

# DB error log
DB_LOG_PATH = os.path.join(LOG_DIR, "db_errors.log")
logger.add(
    DB_LOG_PATH,
    rotation="1 day",
    retention="14 days",
    compression="gz",
    level="WARNING",
    enqueue=True,
    backtrace=True,
    diagnose=False,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

# Startup log
STARTUP_LOG_PATH = os.path.join(LOG_DIR, "startup.log")
logger.add(
    STARTUP_LOG_PATH,
    rotation="1 day",
    retention="14 days",
    compression="gz",
    level="INFO",
    enqueue=True,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)


def get_logger():
    """Return the global logger."""
    return logger
