"""
Tests for authentication endpoints

Tests use SQLite in-memory database for fast, isolated execution
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class TestRegisterEndpoint:
    """Test user registration endpoint"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Test successful user registration"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "User registered. Check email to verify."
        assert data["data"]["username"] == "newuser"
        assert data["data"]["email"] == "new@example.com"
        assert data["data"]["is_active"] is False  # Not verified yet
        assert data["data"]["email_verified_at"] is None

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "different",
                "email": test_user.email,  # Duplicate
                "password": "password123",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "already registered" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_register_duplicate_username(
        self, client: AsyncClient, test_user: User
    ):
        """Test registration with duplicate username"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": test_user.username,  # Duplicate
                "email": "different@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "already taken" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Test registration with invalid email"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "not-an-email",
                "password": "password123",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "validation failed" in data["message"].lower()
        assert "email" in data["data"]["errors"]

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Test registration with short password"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "123",  # Too short
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False


class TestLoginEndpoint:
    """Test login endpoint"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",  # From fixture
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"
        assert data["data"]["user"]["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "incorrect" in data["message"].lower() or "invalid" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent email"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_login_unverified_account(
        self, client: AsyncClient, unverified_user: User
    ):
        """Test login with unverified account"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": unverified_user.email,
                "password": "testpassword123",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "verify" in data["message"].lower()


class TestLogoutEndpoints:
    """Test logout endpoints"""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient, auth_token: str):
        """Test successful logout"""
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "logged out" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_logout_invalid_token(self, client: AsyncClient):
        """Test logout with invalid token"""
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_logout_all_devices(self, client: AsyncClient, auth_token: str):
        """Test logout from all devices"""
        response = await client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "revoked_count" in data["data"]
        assert data["data"]["revoked_count"] >= 1

    @pytest.mark.asyncio
    async def test_use_token_after_logout(
        self, client: AsyncClient, auth_token: str
    ):
        """Test that token can't be used after logout"""
        # Logout
        await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        # Try to use token
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "revoked" in data["message"].lower()


class TestGetCurrentUser:
    """Test get current user endpoint"""

    @pytest.mark.asyncio
    async def test_get_current_user_success(
        self, client: AsyncClient, auth_token: str, test_user: User
    ):
        """Test getting current user info"""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["email"] == test_user.email
        assert data["data"]["username"] == test_user.username

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test getting current user without token"""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token"""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False


class TestPasswordReset:
    """Test password reset flow"""

    @pytest.mark.asyncio
    async def test_forgot_password_success(
        self, client: AsyncClient, test_user: User
    ):
        """Test forgot password request"""
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user.email},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_forgot_password_nonexistent_email(self, client: AsyncClient):
        """Test forgot password with non-existent email"""
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_reset_password_invalid_code(
        self, client: AsyncClient, test_user: User
    ):
        """Test reset password with invalid code"""
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "email": test_user.email,
                "verification_code": "000000",  # Invalid
                "new_password": "newpassword123",
            },
        )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
