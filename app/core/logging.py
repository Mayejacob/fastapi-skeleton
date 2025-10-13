import logging
import os

from app.utils.logging import get_logger


def setup_early_logging():
    os.makedirs("logs", exist_ok=True)
    early_logger = logging.getLogger("startup")
    early_logger.setLevel(logging.ERROR)
    fh = logging.FileHandler("logs/startup.log")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    early_logger.addHandler(fh)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    early_logger.addHandler(console_handler)
