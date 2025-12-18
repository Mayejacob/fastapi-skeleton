from typing import Annotated
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import DBDependency
from app.core.responses import send_success, send_error
from app.core.security import get_current_user, oauth2_scheme
from app.db.models.user import User
from app.db.schemas.user import (
    UserCreate,
    UserResponse,
    LoginRequest,
    VerifyRequest,
    ForgotPasswordRequest,
    ResetRequest,
)
from app.services.email import send_email
from app.services.auth import AuthService
from app.utils.caching import cache
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(user_data: UserCreate, db: DBDependency):
    """Register a new user"""
    auth_service = AuthService(db)

    # Register user
    user, verification_code = await auth_service.register_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
    )

    # Send verification email
    await send_email(
        to=user.email,
        subject=f"Verify Your {settings.APP_NAME} Account",
        template="verify.html",
        context={
            "user_name": user.username,
            "verification_code": verification_code,
            "verification_code_expires_at": user.verification_code_expires_at,
        },
    )

    return send_success(
        data=UserResponse.model_validate(user),
        message="User registered. Check email to verify.",
    )


@router.post("/verify")
async def verify_account(request: VerifyRequest, db: DBDependency):
    """Verify user account with verification code"""
    auth_service = AuthService(db)

    # Verify account
    user = await auth_service.verify_account(
        email=request.email,
        code=request.code,
    )

    return send_success(
        message="Account verified successfully!",
        data={"user": UserResponse.model_validate(user)},
    )


@router.post("/resend_verification_code")
async def resend_verification_code(form_data: ForgotPasswordRequest, db: DBDependency):
    """Resend verification code to user"""
    auth_service = AuthService(db)

    # Generate new verification code
    verification_code = await auth_service.resend_verification_code(
        email=form_data.email
    )

    # Get user for email
    from app.services.user import UserService
    user_service = UserService(db)
    user = await user_service.get_by_email(form_data.email)

    # Send verification email
    await send_email(
        to=user.email,
        subject=f"Your New {settings.APP_NAME} Verification Code",
        template="verify.html",
        context={
            "user_name": user.username,
            "verification_code": verification_code,
            "verification_code_expires_at": user.verification_code_expires_at,
        },
    )

    return send_success(
        message="A verification code has been sent to your email address"
    )


@router.post("/login")
async def login(form_data: LoginRequest, request: Request, db: DBDependency):
    """Authenticate user and return tokens"""
    auth_service = AuthService(db)

    # Extract metadata
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Login
    user, access_token, refresh_token = await auth_service.login(
        email=form_data.email,
        password=form_data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Commit the transaction to save tokens
    await db.commit()

    return send_success(
        message="Login successful",
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user),
        },
    )


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: DBDependency):
    """Request password reset code"""
    auth_service = AuthService(db)

    # Request password reset
    reset_code = await auth_service.request_password_reset(email=request.email)

    # Get user for email
    from app.services.user import UserService
    user_service = UserService(db)
    user = await user_service.get_by_email(request.email)

    # Commit to save reset token
    await db.commit()

    # Send reset email
    await send_email(
        to=user.email,
        subject=f"Reset Your {settings.APP_NAME} Password",
        template="reset.html",
        context={
            "user_name": user.username,
            "reset_code": reset_code,
            "reset_code_expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
    )

    return send_success(message="Password reset email sent successfully.")


@router.post("/reset-password")
async def reset_password(request: ResetRequest, db: DBDependency):
    """Reset password with verification code"""
    auth_service = AuthService(db)

    # Reset password
    user = await auth_service.reset_password(
        email=request.email,
        code=request.verification_code,
        new_password=request.new_password,
    )

    # Commit the changes
    await db.commit()

    return send_success(message="Password reset successfully.").model_dump()


@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBDependency,
):
    """Logout from current device"""
    auth_service = AuthService(db)

    # Revoke current token
    await auth_service.logout(token)

    # Commit the revocation
    await db.commit()

    return send_success(message="Logged out successfully")


@router.post("/logout-all")
async def logout_all_devices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: DBDependency,
):
    """Logout from all devices"""
    auth_service = AuthService(db)

    # Revoke all user tokens
    count = await auth_service.logout_all_devices(current_user.id)

    # Commit the revocations
    await db.commit()

    return send_success(
        message=f"Logged out from {count} device(s)",
        data={"revoked_count": count},
    )


@router.get("/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current authenticated user"""
    return send_success(data=UserResponse.model_validate(current_user)).model_dump()


@router.get("/test-cache")
async def test_cache(db: DBDependency):
    """Test cache functionality"""
    # Simple cache test: Store/retrieve a value
    key = "test_key"
    value = {"timestamp": datetime.now(timezone.utc).isoformat(), "message": "Cached!"}

    # Get
    cached = await cache.get(key, db=db)
    if not cached:
        # Set if missing
        await cache.set(key, value, expire=60, db=db)  # 60s expiry
        cached = value

    return send_success(data=cached, message="Cache test successful.").model_dump()
