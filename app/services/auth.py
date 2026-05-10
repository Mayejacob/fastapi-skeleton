import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    get_password_hash,
    verify_password,
    generate_verification_code,
    hash_verification_code,
    verify_verification_code,
)
from app.db.models.user import User
from app.db.models.tokens import PasswordResetToken
from app.services.token import TokenService, ensure_timezone_aware
from app.utils.caching import cache

# ── Lockout configuration ──────────────────────────────────────────────────
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60   # 15-minute sliding window
LOGIN_LOCKOUT_SECONDS = 15 * 60  # 15-minute lockout

RESEND_MAX_ATTEMPTS = 3
RESEND_WINDOW_SECONDS = 10 * 60  # 10-minute sliding window
RESEND_LOCKOUT_SECONDS = 10 * 60


class AuthService:
    """Service for handling authentication business logic"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.token_service = TokenService()

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _check_lockout(self, lock_key: str) -> None:
        """Raise 429 if the lockout key is present in cache."""
        locked = await cache.get(lock_key, db=self.db)
        if locked:
            locked_until = locked.get("locked_until", "a few minutes")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again after {locked_until}.",
            )

    async def _record_failure(
        self,
        fail_key: str,
        lock_key: str,
        max_attempts: int,
        window_seconds: int,
        lockout_seconds: int,
        locked_message: str,
    ) -> int:
        """
        Increment the failure counter. If max_attempts is reached, set a
        lockout and clear the counter.

        Returns:
            Remaining attempts before lockout (0 when lockout is set).
        """
        data = await cache.get(fail_key, db=self.db) or {"count": 0}
        data["count"] += 1
        remaining = max_attempts - data["count"]

        if data["count"] >= max_attempts:
            locked_until = datetime.now(timezone.utc) + timedelta(seconds=lockout_seconds)
            await cache.set(
                lock_key,
                {"locked_until": locked_until.strftime("%H:%M UTC")},
                expire=lockout_seconds,
                db=self.db,
            )
            await cache.delete(fail_key, db=self.db)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=locked_message,
            )

        await cache.set(fail_key, data, expire=window_seconds, db=self.db)
        return remaining

    async def _clear_failures(self, fail_key: str, lock_key: str) -> None:
        """Clear failure counter and any lockout for an email."""
        await cache.delete(fail_key, db=self.db)
        await cache.delete(lock_key, db=self.db)

    # ── Public methods ────────────────────────────────────────────────────────

    async def register_user(
        self, username: str, email: str, password: str
    ) -> Tuple[User, str]:
        """
        Register a new user.

        Returns:
            Tuple of (User, verification_code)

        Raises:
            HTTPException: If username or email already exists
        """
        result = await self.db.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            if existing_user.username == username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

        hashed_password = get_password_hash(password)
        verification_code = generate_verification_code()
        hashed_code = hash_verification_code(verification_code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            verification_code=hashed_code,
            verification_code_expires_at=expires_at,
        )

        self.db.add(new_user)
        await self.db.flush()
        await self.db.refresh(new_user)

        return new_user, verification_code

    async def verify_account(self, email: str, code: str) -> User:
        """
        Verify user account with verification code.

        Raises:
            HTTPException: If verification fails
        """
        result = await self.db.execute(
            select(User).where(and_(User.email == email, User.is_active == False))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email or already verified",
            )

        expires_at = ensure_timezone_aware(user.verification_code_expires_at)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired. Request a fresh code.",
            )

        if not verify_verification_code(user.verification_code, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code",
            )

        user.is_active = True
        user.email_verified_at = datetime.now(timezone.utc)
        user.verification_code = None
        user.verification_code_expires_at = None

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def resend_verification_code(self, email: str) -> str:
        """
        Resend verification code with abuse protection.

        Returns:
            New verification code

        Raises:
            HTTPException: If user not found, already verified, or locked out
        """
        fail_key = f"resend_fail:{email}"
        lock_key = f"resend_locked:{email}"

        await self._check_lockout(lock_key)

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email address",
            )

        if user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account has been previously verified",
            )

        remaining = await self._record_failure(
            fail_key=fail_key,
            lock_key=lock_key,
            max_attempts=RESEND_MAX_ATTEMPTS,
            window_seconds=RESEND_WINDOW_SECONDS,
            lockout_seconds=RESEND_LOCKOUT_SECONDS,
            locked_message=(
                f"Too many resend attempts. "
                f"Wait {RESEND_LOCKOUT_SECONDS // 60} minutes before trying again."
            ),
        )

        verification_code = generate_verification_code()
        hashed_code = hash_verification_code(verification_code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        user.verification_code = hashed_code
        user.verification_code_expires_at = expires_at

        await self.db.flush()
        await self.db.refresh(user)

        return verification_code

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
        device_name: str = None,
    ) -> Tuple[User, str, str]:
        """
        Authenticate user and create tokens with lockout protection.

        Returns:
            Tuple of (User, access_token, refresh_token)

        Raises:
            HTTPException: If authentication fails or account is locked out
        """
        fail_key = f"login_fail:{email}"
        lock_key = f"login_locked:{email}"

        await self._check_lockout(lock_key)

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            remaining = await self._record_failure(
                fail_key=fail_key,
                lock_key=lock_key,
                max_attempts=LOGIN_MAX_ATTEMPTS,
                window_seconds=LOGIN_WINDOW_SECONDS,
                lockout_seconds=LOGIN_LOCKOUT_SECONDS,
                locked_message=(
                    f"Account locked for {LOGIN_LOCKOUT_SECONDS // 60} minutes "
                    f"due to too many failed login attempts."
                ),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"Incorrect email or password. "
                    f"{remaining} attempt(s) remaining before lockout."
                ),
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is not verified. Check your email.",
            )

        # Success — clear any existing failure tracking
        await self._clear_failures(fail_key, lock_key)

        access_token_str, access_token_record = (
            await self.token_service.create_access_token(
                user_id=user.id,
                email=user.email,
                db=self.db,
                ip_address=ip_address,
                user_agent=user_agent,
                device_name=device_name,
            )
        )

        refresh_token_str, _ = await self.token_service.create_refresh_token(
            user_id=user.id,
            access_token_id=access_token_record.id,
            db=self.db,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return user, access_token_str, refresh_token_str

    async def request_password_reset(self, email: str) -> str:
        """
        Request password reset code.

        Returns:
            Password reset code

        Raises:
            HTTPException: If user not found
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid email address",
            )

        await self.db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )

        reset_code = generate_verification_code()
        hashed_code = hash_verification_code(reset_code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        reset_token = PasswordResetToken(
            token=hashed_code,
            user_id=user.id,
            expires_at=expires_at,
        )

        self.db.add(reset_token)
        await self.db.flush()

        return reset_code

    async def reset_password(
        self, email: str, code: str, new_password: str
    ) -> User:
        """
        Reset password with verification code. Clears any login lockout.

        Raises:
            HTTPException: If reset fails
        """
        user_result = await self.db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid email address",
            )

        token_result = await self.db.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id)
            .order_by(PasswordResetToken.created_at.desc())
            .limit(1)
        )
        reset_token = token_result.scalar_one_or_none()

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No reset code found for this user",
            )

        if not verify_verification_code(reset_token.token, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code",
            )

        expires_at = ensure_timezone_aware(reset_token.expires_at)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code has expired",
            )

        if reset_token.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset code has already been used",
            )

        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)
        reset_token.used_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(user)

        # Clear login lockout so the user can log in with the new password
        await self._clear_failures(
            fail_key=f"login_fail:{email}",
            lock_key=f"login_locked:{email}",
        )

        return user

    async def logout(self, token: str) -> bool:
        """Revoke the current access token."""
        _, token_record = await self.token_service.validate_token(token, self.db)
        token_hash = self.token_service._hash_token(token)
        return await self.token_service.revoke_token(token_hash, self.db)

    async def logout_all_devices(self, user_id: uuid.UUID) -> int:
        """Revoke all tokens for a user (logout all devices)."""
        return await self.token_service.revoke_all_user_tokens(user_id, self.db)
