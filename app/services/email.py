import aiosmtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape  # For templating

from app.core.config import settings

# Jinja2 setup
env = Environment(
    loader=FileSystemLoader("templates/emails"),
    autoescape=select_autoescape(["html", "xml"]),
)


async def send_email(
    to: str,
    subject: str,
    template: str | None = None,  # e.g., "welcome"
    context: (
        dict | None
    ) = None,  # e.g., {"user_name": "John", "app_name": settings.APP_NAME}
    body: str | None = None,  # Fallback plain text
):
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject

    if template:
        # Render HTML template with context (defaults from settings)
        template_context = {
            **{
                "app_name": settings.APP_NAME,
                "app_url": settings.APP_URL,
                "year": "2025",
            },
            **(context or {}),
        }
        html_body = env.get_template(f"{template}.html").render(template_context)
        message.add_alternative(html_body, subtype="html")
        if not body:
            # Auto-generate plain text from HTML (simple strip, or use pandoc if needed)
            body = (
                html_body.replace("<[^>]*>", "").replace("\n\n", "\n").strip()
            )  # Basic HTML-to-text
    else:
        body = body or "No content provided."

    message.set_content(body)

    smtp = aiosmtplib.SMTP(
        hostname=settings.EMAIL_HOST, port=settings.EMAIL_PORT, use_tls=True
    )
    await smtp.connect()
    await smtp.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
    await smtp.send_message(message)
    await smtp.quit()
