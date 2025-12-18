import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.tokens import AccessToken, RefreshToken
from app.db.models.user import User


class TokenService:
    """Service for managing JWT tokens with database storage"""

    def _hash_token(self, token: str) -> str:
        """Hash token using SHA-256 for storage"""
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_access_token(
        self,
        user_id: uuid.UUID,
        email: str,
        db: AsyncSession,
        ip_address: str = None,
        user_agent: str = None,
        device_name: str = None,
    ) -> Tuple[str, AccessToken]:
        """
        Create JWT access token and store in database

        Args:
            user_id: User's UUID
            email: User's email
            db: Database session
            ip_address: Client IP address
            user_agent: Client user agent
            device_name: Device name

        Returns:
            Tuple of (token_string, AccessToken record)
        """
        # Generate token ID
        token_id = str(uuid.uuid4())

        # Calculate expiration
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expires_at = datetime.now(timezone.utc) + expires_delta

        # Create JWT payload
        payload = {
            "sub": email,
            "user_id": str(user_id),
            "exp": expires_at,
            "jti": token_id,
        }

        # Encode JWT
        token_string = jwt.encode(
            payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )

        # Hash token for storage
        token_hash = self._hash_token(token_string)

        # Create database record
        access_token = AccessToken(
            id=uuid.UUID(token_id),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            device_name=device_name,
        )

        db.add(access_token)
        await db.flush()

        return token_string, access_token

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        access_token_id: uuid.UUID,
        db: AsyncSession,
        ip_address: str = None,
        user_agent: str = None,
    ) -> Tuple[str, RefreshToken]:
        """
        Create refresh token and store in database

        Args:
            user_id: User's UUID
            access_token_id: Associated access token ID
            db: Database session
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Tuple of (token_string, RefreshToken record)
        """
        # Generate token ID
        token_id = str(uuid.uuid4())

        # Calculate expiration (default 30 days)
        expires_delta = timedelta(days=getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 30))
        expires_at = datetime.now(timezone.utc) + expires_delta

        # Create JWT payload
        payload = {
            "sub": str(user_id),
            "exp": expires_at,
            "jti": token_id,
            "type": "refresh",
        }

        # Encode JWT
        token_string = jwt.encode(
            payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )

        # Hash token for storage
        token_hash = self._hash_token(token_string)

        # Create database record
        refresh_token = RefreshToken(
            id=uuid.UUID(token_id),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            access_token_id=access_token_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        db.add(refresh_token)
        await db.flush()

        return token_string, refresh_token

    async def validate_token(
        self, token: str, db: AsyncSession
    ) -> Tuple[dict, AccessToken]:
        """
        Validate JWT token signature and check database for revocation

        Args:
            token: JWT token string
            db: Database session

        Returns:
            Tuple of (payload dict, AccessToken record)

        Raises:
            HTTPException: If token is invalid, revoked, or expired
        """
        try:
            # Decode and verify JWT signature
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )

            # Get token ID from payload
            token_id = payload.get("jti")
            if not token_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing token ID",
                )

            # Hash token to look up in database
            token_hash = self._hash_token(token)

            # Query database for token
            result = await db.execute(
                select(AccessToken).where(
                    AccessToken.id == uuid.UUID(token_id),
                    AccessToken.token_hash == token_hash,
                )
            )
            token_record = result.scalar_one_or_none()

            if not token_record:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token not found in database",
                )

            # Check if token is revoked
            if token_record.revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )

            # Check expiration (belt and suspenders with JWT exp check)
            if token_record.expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                )

            return payload, token_record

        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )

    async def revoke_token(self, token_hash: str, db: AsyncSession) -> bool:
        """
        Revoke a token by its hash

        Args:
            token_hash: SHA-256 hash of the token
            db: Database session

        Returns:
            True if token was revoked, False if not found
        """
        result = await db.execute(
            select(AccessToken).where(AccessToken.token_hash == token_hash)
        )
        token_record = result.scalar_one_or_none()

        if token_record:
            token_record.revoked = True
            token_record.revoked_at = datetime.now(timezone.utc)
            await db.flush()
            return True

        return False

    async def revoke_all_user_tokens(self, user_id: uuid.UUID, db: AsyncSession) -> int:
        """
        Revoke all active tokens for a user (logout all devices)

        Args:
            user_id: User's UUID
            db: Database session

        Returns:
            Number of tokens revoked
        """
        result = await db.execute(
            select(AccessToken).where(
                AccessToken.user_id == user_id, AccessToken.revoked == False
            )
        )
        tokens = result.scalars().all()

        count = 0
        revoked_at = datetime.now(timezone.utc)
        for token in tokens:
            token.revoked = True
            token.revoked_at = revoked_at
            count += 1

        if count > 0:
            await db.flush()

        return count

    async def cleanup_expired_tokens(self, db: AsyncSession) -> int:
        """
        Delete expired tokens from database (scheduled cleanup task)

        Args:
            db: Database session

        Returns:
            Number of tokens deleted
        """
        now = datetime.now(timezone.utc)

        # Delete expired access tokens
        access_result = await db.execute(
            select(AccessToken).where(AccessToken.expires_at < now)
        )
        expired_access_tokens = access_result.scalars().all()

        # Delete expired refresh tokens
        refresh_result = await db.execute(
            select(RefreshToken).where(RefreshToken.expires_at < now)
        )
        expired_refresh_tokens = refresh_result.scalars().all()

        count = 0
        for token in expired_access_tokens:
            await db.delete(token)
            count += 1

        for token in expired_refresh_tokens:
            await db.delete(token)
            count += 1

        if count > 0:
            await db.flush()

        return count
