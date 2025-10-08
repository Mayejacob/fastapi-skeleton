from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import DBDependency  # If needed for auth/context
from app.services.email import send_email
from app.core.responses import send_success, send_error
from app.core.config import settings

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/test")
async def test_email():
    try:
        await send_email(
            to="test@example.com",  # Replace with your test email
            subject="Test Email from FastAPI",
            template="welcome.html",  # Use an existing template, or None for plain
            context={"user_name": "Test User", "app_name": settings.APP_NAME},
            body="This is a plain text test body.",  # Fallback
        )
        return send_success("Test email sent successfully!")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to send test email: {str(e)}"
        )
