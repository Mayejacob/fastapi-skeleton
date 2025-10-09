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
    await db.refresh(new_user)

    # Send verification email
    # token = create_verification_token(user_data.email)
    # verify_url = f"{settings.APP_URL}/auth/verify?token={token}"
    # await send_email(
    #     to=user_data.email,
    #     subject=f"Verify Your {settings.APP_NAME} Account",
    #     template="verify.html",
    #     context={"user_name": user_data.username, "verify_url": verify_url},
    # )

    await send_email(
        to=user_data.email,
        subject=f"Verify Your {settings.APP_NAME} Account",
        template="verify.html",
        context={
            "user_name": user_data.username,
            "verification_code": verification_code,
        },
    )

    response_data = UserResponse.model_validate(new_user)

    return send_success(
        data=response_data,
        message="User registered. Check email to verify.",
    ).model_dump()


@router.post("/verify")
async def verify_account(request: VerifyRequest, db: DBDependency):
    user = await db.execute(
        select(User).where(and_(User.email == request.email, User.is_active == False))
    )
    db_user = user.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid email or already verified")

    if db_user.verification_code_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification code expired")

    if not verify_verification_code(db_user.verification_code, request.code):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Mark as active and set timestamp
    db_user.is_active = True
    db_user.email_verified_at = datetime.now(timezone.utc)
    db_user.verification_code = None  # Clear code
    db_user.verification_code_expires_at = None
    await db.commit()
    await db.refresh(db_user)

    return send_success(message="Account verified successfully!").model_dump()


@router.post("/login", response_model=Token)
async def login(form_data: LoginRequest, db: DBDependency):
    user = await db.execute(select(User).where(User.username == form_data.username))
    db_user = user.scalar_one_or_none()
    if not db_user or not verify_password(form_data.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not db_user.is_active:
        raise HTTPException(status_code=400, detail="Account not verified")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )
    return send_success(
        data={"access_token": access_token, "token_type": "bearer"}
    ).model_dump()


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: DBDependency):
    user = await db.execute(select(User).where(User.email == request.email))
    db_user = user.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=404, detail="Email not found")

    # Generate and store token
    token = create_reset_token(db_user.email)
    reset_token = PasswordResetToken(token=token, user_id=db_user.id)
    db.add(reset_token)
    await db.commit()

    # Send email
    reset_url = f"{settings.APP_URL}/auth/reset-password?token={token}"
    await send_email(
        to=db_user.email,
        subject=f"Reset Your {settings.APP_NAME} Password",
        template="reset",
        context={"user_name": db_user.username, "reset_url": reset_url},
    )

    return send_success(message="Password reset email sent.").model_dump()


@router.post("/reset-password")
async def reset_password(request: ResetRequest, db: DBDependency):
    email = verify_reset_token(request.token)
    user = await db.execute(select(User).where(User.email == email))
    db_user = user.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid token")

    # Update password and mark token used
    db_user.hashed_password = get_password_hash(request.new_password)
    db_user.updated_at = datetime.now(timezone.utc)
    token = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == request.token)
    )
    reset_token = token.scalar_one_or_none()
    if reset_token:
        reset_token.used_at = datetime.now(timezone.utc)
        db.add(reset_token)
    await db.commit()

    return send_success(message="Password reset successfully.").model_dump()


@router.get("/me", response_model=UserResponse)
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
