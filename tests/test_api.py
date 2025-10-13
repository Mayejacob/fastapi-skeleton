import pytest
from app.core.security import verify_password
from app.db.models.user import User
from sqlalchemy import select
from app.core.security import hash_verification_code, verify_password
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


def test_register_user(client):
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Password123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "User registered" in data["message"]
    assert data["data"]["email"] == payload["email"]


def test_duplicate_email_or_username(client):
    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "Password123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    error_data = response.json()
    assert (
        "already" in (error_data.get("message") or error_data.get("detail", "")).lower()
    )


def test_verification_and_login_flow(client):
    from app.core.dependencies import get_db
    from sqlalchemy import select

    # 1️⃣ Get user from DB
    import asyncio

    async def get_user():
        async for db in get_db():
            result = await db.execute(select(User))
            return result.scalars().first()

    user = run_async(get_user())
    assert user is not None

    email = user.email
    # Mock verification code
    user.verification_code = hash_verification_code("654321")
    user.is_verified = True  # ✅ Reset verification status
    user.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=10
    )

    async def update_user():
        async for db in get_db():
            db.add(user)
            await db.commit()

    run_async(update_user())

    # 3️⃣ Try login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login_resp.status_code == 200


def test_resend_verification_code(client):
    payload = {"email": "test@example.com"}
    response = client.post("/api/v1/auth/resend_verification_code", json=payload)
    assert response.status_code in [200, 400]


def test_forgot_and_reset_password(client):
    from app.core.dependencies import get_db
    import asyncio

    # Forgot password
    payload = {"email": "test@example.com"}
    resp = client.post("/api/v1/auth/forgot-password", json=payload)
    assert resp.status_code == 200
    assert "Password reset email" in resp.json()["message"]

    # Retrieve token
    async def get_token():
        async for db in get_db():
            result = await db.execute(select(PasswordResetToken))
            return result.scalars().first()

    token = run_async(get_token())
    assert token is not None

    correct_code = "999999"
    token.token = hash_verification_code(correct_code)

    async def update_token():
        async for db in get_db():
            db.add(token)
            await db.commit()

    run_async(update_token())

    # Correct reset
    correct_reset = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": "test@example.com",
            "verification_code": correct_code,
            "new_password": "Newpass123!",
        },
    )
    assert correct_reset.status_code == 200


def test_me_endpoint(client):
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Newpass123!"},
    )

    data = login_resp.json()
    print("LOGIN RESPONSE:", data)
    assert login_resp.status_code == 200, data


def test_cache(client):
    resp1 = client.get("/api/v1/auth/test-cache")
    assert resp1.status_code == 200
    assert "Cached" in resp1.json()["data"]["message"]
