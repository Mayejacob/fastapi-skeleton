from fastapi_mail import ConnectionConfig

from app.core.config import settings
from pathlib import Path

conf = ConnectionConfig(
    MAIL_USERNAME=settings.EMAIL_USERNAME,
    MAIL_PASSWORD=settings.EMAIL_PASSWORD,
    MAIL_FROM=settings.EMAIL_FROM,
    MAIL_PORT=settings.EMAIL_PORT,
    MAIL_SERVER=settings.EMAIL_HOST,  # Maps to your EMAIL_HOST
    MAIL_FROM_NAME=settings.APP_NAME,  # Optional: Sender name
    MAIL_STARTTLS=(
        settings.MAIL_STARTTLS if hasattr(settings, "MAIL_STARTTLS") else True
    ),
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS if hasattr(settings, "MAIL_SSL_TLS") else False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(settings.TEMPLATE_FOLDER),
    SUPPRESS_SEND=getattr(settings, "SUPPRESS_SEND", 0),  # For testing
)
