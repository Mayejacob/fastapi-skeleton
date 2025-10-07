import aiosmtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import settings
import re

env = Environment(
    loader=FileSystemLoader("templates/emails"),
    autoescape=select_autoescape(["html", "xml"]),
)


async def send_email(
    to: str,
    subject: str,
    template: str | None = None,
    context: dict | None = None,
    body: str | None = None,
):
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject

    if template:
        # Prepare context
        template_context = {
            "app_name": settings.APP_NAME,
            "app_url": settings.APP_URL,
            "year": "2025",
            **(context or {}),
        }

        # Render HTML template
        html_body = env.get_template(f"{template}.html").render(template_context)

        # Generate plain text fallback
        if not body:
            # Strip HTML tags to create a readable text version
            body = re.sub(r"<[^>]+>", "", html_body).strip()

        # Add plain text first
        message.set_content(body)

        # Then add HTML version
        message.add_alternative(html_body, subtype="html")
    else:
        # Only plain text
        message.set_content(body or "No content provided.")

    # Send the email
    smtp = aiosmtplib.SMTP(
        hostname=settings.EMAIL_HOST, port=settings.EMAIL_PORT, use_tls=True
    )
    await smtp.connect()
    await smtp.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
    await smtp.send_message(message)
    await smtp.quit()
