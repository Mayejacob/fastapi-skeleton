from fastapi_mail import FastMail, MessageSchema, MessageType
from pathlib import Path
from typing import List

from app.core.mail import conf  # email configuration
from app.core.config import settings
from datetime import datetime

fm = FastMail(conf)


async def send_email(
    to: str,
    subject: str,
    template: str | None = None,  # e.g., "welcome"
    context: dict | None = None,  # e.g., {"user_name": "John"}
    body: str | None = None,  # Fallback plain text
    attachments: List[str] | None = None,  # New: List of file paths to attach
):
    # Prepare context (add defaults)
    template_context = {
        **{
            "app_name": settings.APP_NAME,
            "app_url": settings.APP_URL,
            "year": str(datetime.now().year),
        },
        **(context or {}),
    }

    # Message setup
    message = MessageSchema(
        subject=subject,
        recipients=[to],
        subtype=MessageType.html if template else MessageType.plain,
        attachments=(
            []
            if not attachments
            else [
                {
                    "file": Path(attach_path),
                    "headers": {
                        "Content-Disposition": f"attachment; filename={Path(attach_path).name}"
                    },
                }
                for attach_path in attachments
            ]
        ),
    )

    if template:
        message.template_body = template_context  # Data for template
        message.body = template  # Template name (e.g., "welcome.html")
    else:
        message.body = body or "No content provided."

    # Send async
    await fm.send_message(message, template_name=template if template else None)
