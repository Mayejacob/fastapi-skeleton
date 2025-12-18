"""
Example tests for the services layer

These tests demonstrate how to test the refactored services.
Run with: pytest tests/test_services.py -v
"""
import pytest
from datetime import datetime, timezone, timedelta
import uuid

from app.services.auth import AuthService
from app.services.user import UserService
from app.services.token import TokenService
from app.db.models.user import User
from app.db.models.tokens import AccessToken


class TestUserService:
    """Test UserService CRUD operations"""

    @pytest.mark.asyncio
    async def test_create_and_get_user(self, db_session):
        """Test user creation and retrieval"""
        user_service = UserService(db_session)

        # Create a test user manually
        from app.core.security import get_password_hash
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Test get by email
        found_user = await user_service.get_by_email("test@example.com")
        assert found_user is not None
        assert found_user.username == "testuser"

        # Test get by username
        found_user = await user_service.get_by_username("testuser")
        assert found_user is not None
        assert found_user.email == "test@example.com"

        # Test get by ID
        found_user = await user_service.get_by_id(user.id)
        assert found_user is not None

    @pytest.mark.asyncio
    async def test_update_user(self, db_session):
        """Test user update"""
        user_service = UserService(db_session)

        # Create user
        from app.core.security import get_password_hash
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Update user
        updated_user = await user_service.update_user(
            user.id, username="newtestuser"
        )
        await db_session.commit()

        assert updated_user.username == "newtestuser"
        assert updated_user.email == "test@example.com"  # Unchanged

    @pytest.mark.asyncio
    async def test_exists_by_email(self, db_session):
        """Test email existence check"""
        user_service = UserService(db_session)

        # Initially doesn't exist
        exists = await user_service.exists_by_email("nonexistent@example.com")
        assert exists is False

        # Create user
        from app.core.security import get_password_hash
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
        )
        db_session.add(user)
        await db_session.commit()

        # Now exists
        exists = await user_service.exists_by_email("test@example.com")
        assert exists is True


class TestAuthService:
    """Test AuthService business logic"""

    @pytest.mark.asyncio
    async def test_register_user(self, db_session):
        """Test user registration"""
        auth_service = AuthService(db_session)

        # Register user
        user, verification_code = await auth_service.register_user(
            username="newuser",
            email="newuser@example.com",
            password="password123",
        )
        await db_session.commit()

        assert user is not None
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.is_active is False  # Not verified yet
        assert verification_code is not None
        assert len(verification_code) == 6  # 6-digit code

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, db_session):
        """Test registration with duplicate email"""
        auth_service = AuthService(db_session)

        # Register first user
        await auth_service.register_user(
            username="user1",
            email="duplicate@example.com",
            password="password123",
        )
        await db_session.commit()

        # Try to register with same email
        with pytest.raises(Exception) as exc_info:
            await auth_service.register_user(
                username="user2",
                email="duplicate@example.com",
                password="password123",
            )

        assert "already registered" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_verify_account(self, db_session):
        """Test account verification"""
        auth_service = AuthService(db_session)

        # Register user
        user, verification_code = await auth_service.register_user(
            username="verifyuser",
            email="verify@example.com",
            password="password123",
        )
        await db_session.commit()

        # Verify account
        verified_user = await auth_service.verify_account(
            email="verify@example.com", code=verification_code
        )
        await db_session.commit()

        assert verified_user.is_active is True
        assert verified_user.email_verified_at is not None

    @pytest.mark.asyncio
    async def test_login_success(self, db_session):
        """Test successful login"""
        auth_service = AuthService(db_session)

        # Register and verify user
        user, verification_code = await auth_service.register_user(
            username="loginuser",
            email="login@example.com",
            password="password123",
        )
        await db_session.commit()

        await auth_service.verify_account(
            email="login@example.com", code=verification_code
        )
        await db_session.commit()

        # Login
        user, access_token, refresh_token = await auth_service.login(
            email="login@example.com",
            password="password123",
            ip_address="127.0.0.1",
            user_agent="Test Agent",
        )
        await db_session.commit()

        assert user is not None
        assert access_token is not None
        assert refresh_token is not None
        assert len(access_token) > 0
        assert len(refresh_token) > 0

    @pytest.mark.asyncio
    async def test_login_unverified_account(self, db_session):
        """Test login with unverified account"""
        auth_service = AuthService(db_session)

        # Register but don't verify
        await auth_service.register_user(
            username="unverified",
            email="unverified@example.com",
            password="password123",
        )
        await db_session.commit()

        # Try to login
        with pytest.raises(Exception) as exc_info:
            await auth_service.login(
                email="unverified@example.com",
                password="password123",
            )

        assert "verify" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_password_reset(self, db_session):
        """Test password reset flow"""
        auth_service = AuthService(db_session)

        # Create verified user
        user, verification_code = await auth_service.register_user(
            username="resetuser",
            email="reset@example.com",
            password="oldpassword123",
        )
        await db_session.commit()

        await auth_service.verify_account(
            email="reset@example.com", code=verification_code
        )
        await db_session.commit()

        # Request password reset
        reset_code = await auth_service.request_password_reset(
            email="reset@example.com"
        )
        await db_session.commit()

        assert reset_code is not None
        assert len(reset_code) == 6

        # Reset password
        reset_user = await auth_service.reset_password(
            email="reset@example.com",
            code=reset_code,
            new_password="newpassword123",
        )
        await db_session.commit()

        assert reset_user is not None

        # Try to login with new password
        user, access_token, refresh_token = await auth_service.login(
            email="reset@example.com", password="newpassword123"
        )
        await db_session.commit()

        assert access_token is not None


class TestTokenService:
    """Test TokenService JWT management"""

    @pytest.mark.asyncio
    async def test_create_access_token(self, db_session):
        """Test access token creation"""
        token_service = TokenService()

        user_id = uuid.uuid4()
        email = "test@example.com"

        # Create token
        token_string, token_record = await token_service.create_access_token(
            user_id=user_id,
            email=email,
            db=db_session,
            ip_address="127.0.0.1",
            user_agent="Test Agent",
        )
        await db_session.commit()

        assert token_string is not None
        assert token_record is not None
        assert token_record.user_id == user_id
        assert token_record.ip_address == "127.0.0.1"
        assert token_record.revoked is False

    @pytest.mark.asyncio
    async def test_validate_token(self, db_session):
        """Test token validation"""
        token_service = TokenService()

        user_id = uuid.uuid4()
        email = "test@example.com"

        # Create token
        token_string, token_record = await token_service.create_access_token(
            user_id=user_id, email=email, db=db_session
        )
        await db_session.commit()

        # Validate token
        payload, validated_token = await token_service.validate_token(
            token_string, db_session
        )

        assert payload is not None
        assert payload["sub"] == email
        assert str(payload["user_id"]) == str(user_id)
        assert validated_token.id == token_record.id

    @pytest.mark.asyncio
    async def test_revoke_token(self, db_session):
        """Test token revocation"""
        token_service = TokenService()

        user_id = uuid.uuid4()
        email = "test@example.com"

        # Create token
        token_string, token_record = await token_service.create_access_token(
            user_id=user_id, email=email, db=db_session
        )
        await db_session.commit()

        # Revoke token
        token_hash = token_service._hash_token(token_string)
        revoked = await token_service.revoke_token(token_hash, db_session)
        await db_session.commit()

        assert revoked is True

        # Try to validate revoked token
        with pytest.raises(Exception) as exc_info:
            await token_service.validate_token(token_string, db_session)

        assert "revoked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, db_session):
        """Test revoking all user tokens"""
        token_service = TokenService()

        user_id = uuid.uuid4()
        email = "test@example.com"

        # Create multiple tokens
        token1, _ = await token_service.create_access_token(
            user_id=user_id, email=email, db=db_session
        )
        token2, _ = await token_service.create_access_token(
            user_id=user_id, email=email, db=db_session
        )
        token3, _ = await token_service.create_access_token(
            user_id=user_id, email=email, db=db_session
        )
        await db_session.commit()

        # Revoke all tokens
        count = await token_service.revoke_all_user_tokens(user_id, db_session)
        await db_session.commit()

        assert count == 3

        # All tokens should be invalid
        for token in [token1, token2, token3]:
            with pytest.raises(Exception):
                await token_service.validate_token(token, db_session)

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self, db_session):
        """Test expired token cleanup"""
        token_service = TokenService()

        user_id = uuid.uuid4()
        email = "test@example.com"

        # Create token
        token_string, token_record = await token_service.create_access_token(
            user_id=user_id, email=email, db=db_session
        )
        await db_session.commit()

        # Manually expire it
        token_record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await db_session.commit()

        # Cleanup
        count = await token_service.cleanup_expired_tokens(db_session)
        await db_session.commit()

        assert count >= 1

        # Token should be deleted
        from sqlalchemy import select
        result = await db_session.execute(
            select(AccessToken).where(AccessToken.id == token_record.id)
        )
        deleted_token = result.scalar_one_or_none()

        assert deleted_token is None


class TestLogoutFlow:
    """Test complete logout scenarios"""

    @pytest.mark.asyncio
    async def test_single_device_logout(self, db_session):
        """Test logout from single device"""
        auth_service = AuthService(db_session)

        # Create and verify user
        user, verification_code = await auth_service.register_user(
            username="logoutuser",
            email="logout@example.com",
            password="password123",
        )
        await db_session.commit()

        await auth_service.verify_account(
            email="logout@example.com", code=verification_code
        )
        await db_session.commit()

        # Login
        user, access_token, refresh_token = await auth_service.login(
            email="logout@example.com", password="password123"
        )
        await db_session.commit()

        # Logout
        result = await auth_service.logout(access_token)
        await db_session.commit()

        assert result is True

        # Token should be revoked
        token_service = TokenService()
        with pytest.raises(Exception) as exc_info:
            await token_service.validate_token(access_token, db_session)

        assert "revoked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_all_devices_logout(self, db_session):
        """Test logout from all devices"""
        auth_service = AuthService(db_session)

        # Create and verify user
        user, verification_code = await auth_service.register_user(
            username="multidevice",
            email="multidevice@example.com",
            password="password123",
        )
        await db_session.commit()

        await auth_service.verify_account(
            email="multidevice@example.com", code=verification_code
        )
        await db_session.commit()

        # Login from multiple devices
        user1, token1, _ = await auth_service.login(
            email="multidevice@example.com",
            password="password123",
            user_agent="Device 1",
        )
        await db_session.commit()

        user2, token2, _ = await auth_service.login(
            email="multidevice@example.com",
            password="password123",
            user_agent="Device 2",
        )
        await db_session.commit()

        user3, token3, _ = await auth_service.login(
            email="multidevice@example.com",
            password="password123",
            user_agent="Device 3",
        )
        await db_session.commit()

        # Logout from all devices
        count = await auth_service.logout_all_devices(user1.id)
        await db_session.commit()

        assert count == 3

        # All tokens should be revoked
        token_service = TokenService()
        for token in [token1, token2, token3]:
            with pytest.raises(Exception):
                await token_service.validate_token(token, db_session)


# Pytest fixtures would be defined in conftest.py
# This is just an example of what they might look like:

"""
@pytest.fixture
async def db_session():
    # Setup test database session
    # This would use SQLite in-memory for tests
    pass

@pytest.fixture
async def client():
    # Setup FastAPI test client
    pass
"""
