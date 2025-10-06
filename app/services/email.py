import aiosmtplib
from email.message import EmailMessage

from app.core.config import settings


async def send_email(to: str, subject: str, body: str):
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    smtp = aiosmtplib.SMTP(
        hostname=settings.EMAIL_HOST, port=settings.EMAIL_PORT, use_tls=True
    )
    await smtp.connect()
    await smtp.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
    await smtp.send_message(message)
    await smtp.quit()
