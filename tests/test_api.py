import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.db.models.user import User
from app.db.models.tokens import PasswordResetToken
from app.core.security import hash_verification_code
from app.utils.caching import cache


# ── Cache unit tests ──────────────────────────────────────────────────────────

class TestCache:
    """Test the cache utility directly (inmemory backend)."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Value written with set() is returned by get()."""
        await cache.set("test:key", {"hello": "world"}, expire=60)
        result = await cache.get("test:key")
        assert result == {"hello": "world"}

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self):
        """get() returns None for a key that was never set."""
        result = await cache.get("test:nonexistent_key_xyz")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """delete() removes the key so subsequent get() returns None."""
        await cache.set("test:delete_me", {"v": 1}, expire=60)
        await cache.delete("test:delete_me")
        assert await cache.get("test:delete_me") is None

    @pytest.mark.asyncio
    async def test_overwrite(self):
        """set() on an existing key replaces the value."""
        await cache.set("test:overwrite", {"v": 1}, expire=60)
        await cache.set("test:overwrite", {"v": 2}, expire=60)
        result = await cache.get("test:overwrite")
        assert result == {"v": 2}


# ── Refresh token tests ───────────────────────────────────────────────────────

class TestRefreshToken:
    """Test the /refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """A valid refresh token returns a new access + refresh token pair."""
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert login.status_code == 200
        refresh_token = login.json()["data"]["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        # Tokens should be new (different from originals)
        assert data["data"]["refresh_token"] != refresh_token

    @pytest.mark.asyncio
    async def test_refresh_token_rotation(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Old refresh token is revoked after rotation — cannot be reused."""
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        old_refresh = login.json()["data"]["refresh_token"]

        # Use the refresh token once
        await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})

        # Try to use the old token again — should be rejected
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client: AsyncClient):
        """A garbage token returns 401."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not.a.valid.token"},
        )
        assert response.status_code == 401
        assert response.json()["success"] is False


# ── Login lockout tests ───────────────────────────────────────────────────────

class TestLoginLockout:
    """Test progressive failure messaging and lockout on login."""

    @pytest.mark.asyncio
    async def test_failed_login_shows_remaining_attempts(
        self, client: AsyncClient, test_user: User
    ):
        """Failed login response includes remaining attempts count."""
        # Clear any existing failure state
        await cache.delete(f"login_fail:{test_user.email}")
        await cache.delete(f"login_locked:{test_user.email}")

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"},
        )
        assert response.status_code == 401
        assert "remaining" in response.json()["message"].lower()

    @pytest.mark.asyncio
    async def test_lockout_after_max_attempts(
        self, client: AsyncClient, test_user: User
    ):
        """Account is locked after exceeding the maximum failed attempts."""
        # Clear any existing failure state
        await cache.delete(f"login_fail:{test_user.email}")
        await cache.delete(f"login_locked:{test_user.email}")

        # Exhaust all attempts
        for _ in range(5):
            await client.post(
                "/api/v1/auth/login",
                json={"email": test_user.email, "password": "wrongpassword"},
            )

        # Next attempt should be blocked
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"},
        )
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_successful_login_clears_failures(
        self, client: AsyncClient, test_user: User
    ):
        """Successful login clears the failure counter."""
        await cache.delete(f"login_fail:{test_user.email}")
        await cache.delete(f"login_locked:{test_user.email}")

        # One failed attempt
        await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"},
        )

        # Correct login should succeed
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert response.status_code == 200

        # Failure counter is gone
        assert await cache.get(f"login_fail:{test_user.email}") is None
