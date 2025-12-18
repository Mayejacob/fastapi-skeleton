"""
Tests for TokenService

Tests JWT token creation, validation, and revocation
"""
import pytest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.services.token import TokenService
from app.db.models.user import User


class TestTokenCreation:
    """Test token creation"""

    @pytest.mark.asyncio
    async def test_create_access_token(self, db_session: AsyncSession, test_user: User):
        """Test creating an access token"""
        token_service = TokenService()

        token_string, token_record = await token_service.create_access_token(
            user_id=test_user.id,
            email=test_user.email,
            db=db_session,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        assert token_string is not None
        assert len(token_string) > 0
        assert token_record.user_id == test_user.id
        assert token_record.ip_address == "192.168.1.1"
        assert token_record.user_agent == "Mozilla/5.0"
        assert token_record.revoked is False
        assert token_record.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_create_refresh_token(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test creating a refresh token"""
        token_service = TokenService()

        # Create access token first
        _, access_token_record = await token_service.create_access_token(
            user_id=test_user.id, email=test_user.email, db=db_session
        )

        # Create refresh token
        refresh_token_string, refresh_token_record = (
            await token_service.create_refresh_token(
                user_id=test_user.id,
                access_token_id=access_token_record.id,
                db=db_session,
                ip_address="192.168.1.1",
            )
        )

        assert refresh_token_string is not None
        assert refresh_token_record.user_id == test_user.id
        assert refresh_token_record.access_token_id == access_token_record.id
        assert refresh_token_record.revoked is False


class TestTokenValidation:
    """Test token validation"""

    @pytest.mark.asyncio
    async def test_validate_valid_token(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test validating a valid token"""
        token_service = TokenService()

        # Create token
        token_string, _ = await token_service.create_access_token(
            user_id=test_user.id, email=test_user.email, db=db_session
        )
        await db_session.commit()

        # Validate token
        payload, token_record = await token_service.validate_token(
            token_string, db_session
        )

        assert payload is not None
        assert payload["sub"] == test_user.email
        assert str(payload["user_id"]) == str(test_user.id)
        assert token_record.revoked is False

    @pytest.mark.asyncio
    async def test_validate_invalid_signature(self, db_session: AsyncSession):
        """Test validating token with invalid signature"""
        token_service = TokenService()

        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"

        with pytest.raises(HTTPException) as exc_info:
            await token_service.validate_token(invalid_token, db_session)

        assert exc_info.value.status_code == 401
        assert "invalid token" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_revoked_token(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test validating a revoked token"""
        token_service = TokenService()

        # Create token
        token_string, token_record = await token_service.create_access_token(
            user_id=test_user.id, email=test_user.email, db=db_session
        )
        await db_session.commit()

        # Revoke token
        token_hash = token_service._hash_token(token_string)
        await token_service.revoke_token(token_hash, db_session)
        await db_session.commit()

        # Try to validate
        with pytest.raises(HTTPException) as exc_info:
            await token_service.validate_token(token_string, db_session)

        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_nonexistent_token(self, db_session: AsyncSession):
        """Test validating a token that doesn't exist in database"""
        token_service = TokenService()

        # Create a valid JWT with a different secret (won't be in DB)
        import jwt

        fake_token = jwt.encode(
            {
                "sub": "fake@example.com",
                "user_id": str(uuid.uuid4()),
                "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
                "jti": str(uuid.uuid4()),
            },
            "different-secret-key",  # Different secret key
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as exc_info:
            await token_service.validate_token(fake_token, db_session)

        assert exc_info.value.status_code == 401
        assert "invalid token" in exc_info.value.detail.lower()


class TestTokenRevocation:
    """Test token revocation"""

    @pytest.mark.asyncio
    async def test_revoke_single_token(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test revoking a single token"""
        token_service = TokenService()

        # Create token
        token_string, _ = await token_service.create_access_token(
            user_id=test_user.id, email=test_user.email, db=db_session
        )
        await db_session.commit()

        # Revoke
        token_hash = token_service._hash_token(token_string)
        result = await token_service.revoke_token(token_hash, db_session)
        await db_session.commit()

        assert result is True

        # Verify revoked
        with pytest.raises(HTTPException):
            await token_service.validate_token(token_string, db_session)

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test revoking all tokens for a user"""
        token_service = TokenService()

        # Create multiple tokens
        tokens = []
        for _ in range(3):
            token_string, _ = await token_service.create_access_token(
                user_id=test_user.id, email=test_user.email, db=db_session
            )
            tokens.append(token_string)
        await db_session.commit()

        # Revoke all
        count = await token_service.revoke_all_user_tokens(test_user.id, db_session)
        await db_session.commit()

        assert count == 3

        # Verify all revoked
        for token in tokens:
            with pytest.raises(HTTPException):
                await token_service.validate_token(token, db_session)

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_token(self, db_session: AsyncSession):
        """Test revoking a token that doesn't exist"""
        token_service = TokenService()

        fake_hash = "nonexistent_hash"
        result = await token_service.revoke_token(fake_hash, db_session)

        assert result is False


class TestTokenCleanup:
    """Test token cleanup"""

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test cleaning up expired tokens"""
        token_service = TokenService()

        # Create token
        token_string, token_record = await token_service.create_access_token(
            user_id=test_user.id, email=test_user.email, db=db_session
        )
        await db_session.commit()

        # Manually expire it
        token_record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.commit()

        # Cleanup
        count = await token_service.cleanup_expired_tokens(db_session)
        await db_session.commit()

        assert count >= 1

        # Verify token deleted
        from sqlalchemy import select
        from app.db.models.tokens import AccessToken

        result = await db_session.execute(
            select(AccessToken).where(AccessToken.id == token_record.id)
        )
        deleted_token = result.scalar_one_or_none()

        assert deleted_token is None

    @pytest.mark.asyncio
    async def test_cleanup_doesnt_delete_valid_tokens(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test that cleanup doesn't delete valid tokens"""
        token_service = TokenService()

        # Create valid token
        token_string, token_record = await token_service.create_access_token(
            user_id=test_user.id, email=test_user.email, db=db_session
        )
        await db_session.commit()

        # Cleanup
        await token_service.cleanup_expired_tokens(db_session)
        await db_session.commit()

        # Verify token still exists and valid
        payload, _ = await token_service.validate_token(token_string, db_session)
        assert payload["sub"] == test_user.email


class TestTokenHashing:
    """Test token hashing"""

    def test_hash_token_consistency(self):
        """Test that hashing is consistent"""
        token_service = TokenService()

        token = "test_token_123"
        hash1 = token_service._hash_token(token)
        hash2 = token_service._hash_token(token)

        assert hash1 == hash2

    def test_hash_token_different_inputs(self):
        """Test that different tokens produce different hashes"""
        token_service = TokenService()

        token1 = "test_token_1"
        token2 = "test_token_2"

        hash1 = token_service._hash_token(token1)
        hash2 = token_service._hash_token(token2)

        assert hash1 != hash2

    def test_hash_token_sha256_length(self):
        """Test that hash is SHA-256 (64 hex characters)"""
        token_service = TokenService()

        token = "test_token"
        token_hash = token_service._hash_token(token)

        assert len(token_hash) == 64  # SHA-256 produces 64 hex characters
        assert all(c in "0123456789abcdef" for c in token_hash)
