from typing import Annotated
from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.dependencies import DBDependency
from app.core.responses import send_success, send_error
from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    create_verification_token,
    verify_verification_token,
    create_reset_token,
    verify_reset_token,
    generate_verification_code,
    hash_verification_code,
    verify_verification_code,
)
from app.db.models.user import User
from app.db.models.tokens import EmailVerificationToken, PasswordResetToken
from app.db.schemas.user import (
    UserCreate,
    UserResponse,
    LoginRequest,
    Token,
    VerifyRequest,
    ForgotPasswordRequest,
    ResetRequest,
)
from app.services.email import send_email
from app.utils.caching import cache
from app.core.config import settings
from sqlalchemy import delete


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(user_data: UserCreate, db: DBDependency):
    # Check if username or email already exists
    existing_user = await db.execute(
        select(User).where(
            (User.username == user_data.username) | (User.email == user_data.email)
        )
    )
    existing_user = existing_user.scalar_one_or_none()

    if existing_user:
        if existing_user.username == user_data.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
    # Proceed with creating the user
    hashed_password = get_password_hash(user_data.password)
    verification_code = generate_verification_code()
    hashed_code = hash_verification_code(verification_code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)  # 15-min expiration

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        verification_code=hashed_code,
        verification_code_expires_at=expires_at,
    )
    db.add(new_user)
    await db.flush()
    await db.commit()
    await db.refresh(new_user)

    # Send verification email

    await send_email(
        to=user_data.email,
        subject=f"Verify Your {settings.APP_NAME} Account",
        template="verify.html",
        context={
            "user_name": user_data.username,
            "verification_code": verification_code,
            "verification_code_expires_at": expires_at,
        },
    )

    response_data = UserResponse.model_validate(new_user)

    return send_success(
        data=response_data,
        message="User registered. Check email to verify.",
    )


@router.post("/verify")
async def verify_account(request: VerifyRequest, db: DBDependency):
    user = await db.execute(
        select(User).where(and_(User.email == request.email, User.is_active == False))
    )
    db_user = user.scalar_one_or_none()
    if not db_user:
        return send_error(status_code=400, message="Invalid email or already verified")

    if db_user.verification_code_expires_at < datetime.now(timezone.utc):
        return send_error(
            status_code=400,
            message="Verification code expired, kindly request a fresh verification code",
        )

    if not verify_verification_code(db_user.verification_code, request.code):
        return send_error(
            status_code=400,
            message="Invalid verification code",
        )

    # Mark as active and set timestamp
    db_user.is_active = True
    db_user.email_verified_at = datetime.now(timezone.utc)
    db_user.verification_code = None
    db_user.verification_code_expires_at = None
    await db.commit()
    await db.refresh(db_user)

    userData = UserResponse.model_validate(db_user)
    response = {"user": userData}
    return send_success(message="Account verified successfully!", data=response)


@router.post("/resend_verification_code")
async def resendVerificationCode(form_data: ForgotPasswordRequest, db: DBDependency):
    user = await db.execute(select(User).where(User.email == form_data.email))
    db_user = user.scalar_one_or_none()
    if not db_user:
        return send_error(
            message="invalid email address", status_code=status.HTTP_400_BAD_REQUEST
        )
    if db_user.is_active == True:
        return send_error(message="Account has been previously verified")

    verification_code = generate_verification_code()
    hashed_code = hash_verification_code(verification_code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)  # 15-min expiration

    db_user.verification_code = hashed_code
    db_user.verification_code_expires_at = expires_at
    await db.commit()
    await db.refresh(db_user)

    await send_email(
        to=db_user.email,
        subject=f"Your New {settings.APP_NAME} Verification Code",
        template="verify.html",
        context={
            "user_name": db_user.username,
            "verification_code": verification_code,
            "verification_code_expires_at": expires_at,
        },
    )

    return send_success(
        message="A verification code has been sent to your email address"
    )


@router.post("/login")
async def login(form_data: LoginRequest, db: DBDependency):
    user = await db.execute(select(User).where(User.email == form_data.email))
    db_user = user.scalar_one_or_none()
    if not db_user or not verify_password(form_data.password, db_user.hashed_password):
        return send_error(
            message="Incorrect email or password",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if not db_user.is_active:
        return send_error(
            message="Account is yet to be verified, kindly verify your account",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    userData = UserResponse.model_validate(db_user)
    response = {"access_token": access_token, "token_type": "bearer", "user": userData}
    return send_success(
        message="Login successful",
        data=response,
    )


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: DBDependency):
    user = await db.execute(select(User).where(User.email == request.email))
    db_user = user.scalar_one_or_none()

    if not db_user:
        return send_error(
            message="Invalid email address", status_code=status.HTTP_404_NOT_FOUND
        )

    user_id = db_user.id
    user_email = db_user.email
    user_name = db_user.username

    await db.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == db_user.id)
    )
    await db.commit()
    # Generate and store reset code (not URL)
    reset_code = generate_verification_code()
    hashed_code = hash_verification_code(reset_code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    reset_token = PasswordResetToken(
        token=hashed_code,
        user_id=user_id,
        expires_at=expires_at,
    )

    db.add(reset_token)
    await db.commit()

    await send_email(
        to=user_email,
        subject=f"Reset Your {settings.APP_NAME} Password",
        template="reset.html",
        context={
            "user_name": user_name,
            "reset_code": reset_code,
            "reset_code_expires_at": expires_at,
        },
    )

    return send_success(message="Password reset email sent successfully.")


@router.post("/reset-password")
async def reset_password(request: ResetRequest, db: DBDependency):
    # Find user by email
    user_query = await db.execute(select(User).where(User.email == request.email))
    db_user = user_query.scalar_one_or_none()

    if not db_user:
        return send_error(
            message="Invalid email address", status_code=status.HTTP_404_NOT_FOUND
        )

    token_query = await db.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.user_id == db_user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    reset_token = token_query.scalar_one_or_none()

    if not reset_token:
        return send_error(
            message="No reset code found for this user.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Verify the reset code
    if not verify_verification_code(reset_token.token, request.verification_code):
        return send_error(
            message="Invalid verification code.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Check expiry and usage
    if reset_token.expires_at < datetime.now(timezone.utc):
        return send_error(
            message="Reset code has expired.", status_code=status.HTTP_400_BAD_REQUEST
        )

    if reset_token.used_at is not None:
        return send_error(
            message="This reset code has already been used.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Update password
    db_user.hashed_password = get_password_hash(request.new_password)
    db_user.updated_at = datetime.now(timezone.utc)

    # Mark token as used
    reset_token.used_at = datetime.now(timezone.utc)

    db.add_all([db_user, reset_token])
    await db.commit()

    return send_success(message="Password reset successfully.").model_dump()


@router.get("/me")
async def read_users_me(current_user: Annotated[dict, Depends(get_current_user)]):
    return send_success(data=UserResponse.model_validate(current_user)).model_dump()


@router.get("/test-cache")
async def test_cache(db: DBDependency):
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
