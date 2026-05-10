import uuid
from typing import Annotated
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import DBDependency
from app.core.rate_limiting import limiter
from app.core.responses import send_success, send_error
from app.core.security import get_current_user, oauth2_scheme
from app.db.models.user import User
from app.db.schemas.user import (
    UserCreate,
    UserResponse,
    LoginRequest,
    VerifyRequest,
    ForgotPasswordRequest,
    ResendVerificationRequest,
    ResetRequest,
    RefreshTokenRequest,
)
from app.services.email import send_email
from app.services.auth import AuthService
from app.services.token import TokenService
from app.services.user import UserService
from app.core.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])

# Public endpoints — no Bearer token required in Swagger UI
_PUBLIC = {"security": []}


def get_client_ip(request: Request) -> str | None:
    """Return the real client IP, honoring X-Forwarded-For from proxies."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/register", openapi_extra=_PUBLIC)
@limiter.limit("5/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: DBDependency,
):
    """Register a new user"""
    auth_service = AuthService(db)

    user, verification_code = await auth_service.register_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
    )

    background_tasks.add_task(
        send_email,
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


@router.post("/verify", openapi_extra=_PUBLIC)
@limiter.limit("10/minute")
async def verify_account(request: Request, body: VerifyRequest, db: DBDependency):
    """Verify user account with verification code"""
    auth_service = AuthService(db)

    user = await auth_service.verify_account(
        email=body.email,
        code=body.code,
    )

    return send_success(
        message="Account verified successfully!",
        data={"user": UserResponse.model_validate(user)},
    )


@router.post("/resend_verification_code", openapi_extra=_PUBLIC)
@limiter.limit("3/minute")
async def resend_verification_code(
    request: Request,
    form_data: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: DBDependency,
):
    """Resend verification code to user"""
    auth_service = AuthService(db)

    verification_code = await auth_service.resend_verification_code(
        email=form_data.email
    )

    user_service = UserService(db)
    user = await user_service.get_by_email(form_data.email)

    background_tasks.add_task(
        send_email,
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


@router.post("/login", openapi_extra=_PUBLIC)
@limiter.limit("10/minute")
async def login(request: Request, form_data: LoginRequest, db: DBDependency):
    """Authenticate user and return tokens"""
    auth_service = AuthService(db)

    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    user, access_token, refresh_token = await auth_service.login(
        email=form_data.email,
        password=form_data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return send_success(
        message="Login successful",
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user),
        },
    )


@router.post("/refresh", openapi_extra=_PUBLIC)
@limiter.limit("20/minute")
async def refresh_access_token(
    request: Request, body: RefreshTokenRequest, db: DBDependency
):
    """Exchange a valid refresh token for a new access + refresh token pair"""
    token_service = TokenService()

    payload, refresh_record = await token_service.validate_refresh_token(
        body.refresh_token, db
    )

    user_id = uuid.UUID(payload["sub"])
    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    refresh_record.revoked = True

    access_token_str, access_token_record = await token_service.create_access_token(
        user_id=user.id,
        email=user.email,
        db=db,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    new_refresh_token_str, _ = await token_service.create_refresh_token(
        user_id=user.id,
        access_token_id=access_token_record.id,
        db=db,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return send_success(
        message="Token refreshed successfully",
        data={
            "access_token": access_token_str,
            "refresh_token": new_refresh_token_str,
            "token_type": "bearer",
        },
    )


@router.post("/forgot-password", openapi_extra=_PUBLIC)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: DBDependency,
):
    """Request password reset code"""
    auth_service = AuthService(db)

    reset_code = await auth_service.request_password_reset(email=body.email)

    user_service = UserService(db)
    user = await user_service.get_by_email(body.email)

    background_tasks.add_task(
        send_email,
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


@router.post("/reset-password", openapi_extra=_PUBLIC)
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetRequest, db: DBDependency):
    """Reset password with verification code"""
    auth_service = AuthService(db)

    await auth_service.reset_password(
        email=body.email,
        code=body.verification_code,
        new_password=body.new_password,
    )

    return send_success(message="Password reset successfully.")


@router.post("/logout")
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBDependency,
):
    """Logout from current device"""
    auth_service = AuthService(db)
    await auth_service.logout(token)
    return send_success(message="Logged out successfully")


@router.post("/logout-all")
async def logout_all_devices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: DBDependency,
):
    """Logout from all devices"""
    auth_service = AuthService(db)
    count = await auth_service.logout_all_devices(current_user.id)
    return send_success(
        message=f"Logged out from {count} device(s)",
        data={"revoked_count": count},
    )


@router.get("/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current authenticated user"""
    return send_success(data=UserResponse.model_validate(current_user))
