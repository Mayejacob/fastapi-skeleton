import pytest
from app.core.security import hash_verification_code, verify_password
from app.db.models.user import User
from sqlalchemy import select
from datetime import datetime, timedelta, timezone

from app.db.models.tokens import PasswordResetToken

import asyncio, sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ✅ Safe run_async helper
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


async def test_register_user(client):
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "User registered" in data["message"]
    assert data["data"]["email"] == payload["email"]

 
async def test_duplicate_email_or_username(client):
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Password123!",
    }
    # First registration should succeed
    response1 = await client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == 200

    # Second registration with same email should fail
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    error_data = response.json()
    assert (
        "already" in (error_data.get("message") or error_data.get("detail", "")).lower()
    )


@pytest.mark.asyncio
async def test_verification_and_login_flow(client, db_session):
    # Register a new user
    payload = {
        "username": "logintest",
        "email": "logintest@example.com",
        "password": "Password123!",
    }
    register_resp = await client.post("/api/v1/auth/register", json=payload)
    assert register_resp.status_code == 200

    # Get the user from database and verify them
    result = await db_session.execute(
        select(User).where(User.email == payload["email"])
    )
    user = result.scalar_one()

    # Manually verify the user
    user.is_active = True
    user.email_verified_at = datetime.now(timezone.utc)
    await db_session.commit()

    # Now login should work
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert login_resp.status_code == 200

async def test_resend_verification_code(client):
    payload = {"email": "test@example.com"}
    response = await client.post("/api/v1/auth/resend_verification_code", json=payload)
    assert response.status_code in [200, 400]


async def test_forgot_and_reset_password(client, db_session):
    # First, register and verify a user
    payload = {
        "username": "resettest",
        "email": "resettest@example.com",
        "password": "Password123!",
    }
    register_resp = await client.post("/api/v1/auth/register", json=payload)
    assert register_resp.status_code == 200

    # Verify user
    result = await db_session.execute(
        select(User).where(User.email == payload["email"])
    )
    user = result.scalar_one()
    user.is_active = True
    user.email_verified_at = datetime.now(timezone.utc)
    await db_session.commit()

    # Request password reset
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": payload["email"]}
    )
    assert resp.status_code == 200
    assert "Password reset email" in resp.json()["message"]

    # Get the reset token from database
    token_result = await db_session.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    token = token_result.scalar_one()

    # Update token with known code
    correct_code = "999999"
    token.token = hash_verification_code(correct_code)
    await db_session.commit()

    # Reset password
    correct_reset = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": payload["email"],
            "verification_code": correct_code,
            "new_password": "Newpass123!",
        },
    )
    assert correct_reset.status_code == 200


async def test_me_endpoint(client, db_session):
    # Register and verify a user
    payload = {
        "username": "metest",
        "email": "metest@example.com",
        "password": "Password123!",
    }
    register_resp = await client.post("/api/v1/auth/register", json=payload)
    assert register_resp.status_code == 200

    # Verify user
    result = await db_session.execute(
        select(User).where(User.email == payload["email"])
    )
    user = result.scalar_one()
    user.is_active = True
    user.email_verified_at = datetime.now(timezone.utc)
    await db_session.commit()

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    data = login_resp.json()
    assert login_resp.status_code == 200, data
    assert "access_token" in data["data"]


async def test_cache(client):
    resp1 = await client.get("/api/v1/auth/test-cache")
    assert resp1.status_code == 200
    assert "Cached" in resp1.json()["data"]["message"]
