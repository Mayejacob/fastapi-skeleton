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


class AuthService:
    """Service for handling authentication business logic"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.token_service = TokenService()

    async def register_user(
        self, username: str, email: str, password: str
    ) -> Tuple[User, str]:
        """
        Register a new user

        Args:
            username: User's username
            email: User's email
            password: Plain text password

        Returns:
            Tuple of (User, verification_code)

        Raises:
            HTTPException: If username or email already exists
        """
        # Check if username or email already exists
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

        # Hash password
        hashed_password = get_password_hash(password)

        # Generate verification code
        verification_code = generate_verification_code()
        hashed_code = hash_verification_code(verification_code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Create user
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
        Verify user account with verification code

        Args:
            email: User's email
            code: 6-digit verification code

        Returns:
            Verified User object

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

        # Check expiration
        expires_at = ensure_timezone_aware(user.verification_code_expires_at)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired, kindly request a fresh verification code",
            )

        # Verify code
        if not verify_verification_code(user.verification_code, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code",
            )

        # Mark as active
        user.is_active = True
        user.email_verified_at = datetime.now(timezone.utc)
        user.verification_code = None
        user.verification_code_expires_at = None

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def resend_verification_code(self, email: str) -> str:
        """
        Resend verification code to user

        Args:
            email: User's email

        Returns:
            New verification code

        Raises:
            HTTPException: If user not found or already verified
        """
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

        # Generate new code
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
        Authenticate user and create tokens

        Args:
            email: User's email
            password: Plain text password
            ip_address: Client IP address
            user_agent: Client user agent
            device_name: Device name

        Returns:
            Tuple of (User, access_token, refresh_token)

        Raises:
            HTTPException: If authentication fails
        """
        # Get user
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        # Verify credentials
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        # Check if account is verified
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is yet to be verified, kindly verify your account",
            )

        # Create access token
        access_token_str, access_token_record = await self.token_service.create_access_token(
            user_id=user.id,
            email=user.email,
            db=self.db,
            ip_address=ip_address,
            user_agent=user_agent,
            device_name=device_name,
        )

        # Create refresh token
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
        Request password reset code

        Args:
            email: User's email

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

        # Delete existing reset tokens for this user
        await self.db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )

        # Generate reset code
        reset_code = generate_verification_code()
        hashed_code = hash_verification_code(reset_code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Create reset token
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
        Reset password with verification code

        Args:
            email: User's email
            code: Password reset code
            new_password: New plain text password

        Returns:
            Updated User object

        Raises:
            HTTPException: If reset fails
        """
        # Find user
        user_result = await self.db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid email address",
            )

        # Get latest reset token
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

        # Verify code
        if not verify_verification_code(reset_token.token, code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code",
            )

        # Check expiration
        expires_at = ensure_timezone_aware(reset_token.expires_at)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset code has expired",
            )

        # Check if already used
        if reset_token.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset code has already been used",
            )

        # Update password
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)

        # Mark token as used
        reset_token.used_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def logout(self, token: str) -> bool:
        """
        Logout by revoking the current token

        Args:
            token: JWT access token

        Returns:
            True if successful

        Raises:
            HTTPException: If token is invalid
        """
        # Validate and get token record
        _, token_record = await self.token_service.validate_token(token, self.db)

        # Revoke token
        token_hash = self.token_service._hash_token(token)
        revoked = await self.token_service.revoke_token(token_hash, self.db)

        return revoked

    async def logout_all_devices(self, user_id: uuid.UUID) -> int:
        """
        Logout from all devices by revoking all user tokens

        Args:
            user_id: User's UUID

        Returns:
            Number of tokens revoked
        """
        count = await self.token_service.revoke_all_user_tokens(user_id, self.db)
        return count
