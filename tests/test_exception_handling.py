"""
Tests for exception handling and error responses

Verifies that all exceptions return proper JSON responses
"""
import pytest
from httpx import AsyncClient

from app.db.models.user import User


class TestValidationErrors:
    """Test validation error handling"""

    @pytest.mark.asyncio
    async def test_invalid_email_format(self, client: AsyncClient):
        """Test validation error for invalid email"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "not-an-email",  # Invalid
                "password": "password123",
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert data["message"] == "Validation failed"
        assert "errors" in data["data"]
        assert "email" in data["data"]["errors"]

    @pytest.mark.asyncio
    async def test_short_password(self, client: AsyncClient):
        """Test validation error for short password"""
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
        assert "errors" in data["data"]
        assert "password" in data["data"]["errors"]

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client: AsyncClient):
        """Test validation error for missing fields"""
        response = await client.post(
            "/api/v1/auth/register",
            json={"username": "testuser"},  # Missing email and password
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "errors" in data["data"]
        assert "email" in data["data"]["errors"]
        assert "password" in data["data"]["errors"]

    @pytest.mark.asyncio
    async def test_multiple_validation_errors(self, client: AsyncClient):
        """Test multiple validation errors at once"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "a",  # Too short
                "email": "invalid",  # Invalid format
                "password": "123",  # Too short
            },
        )

        assert response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert len(data["data"]["errors"]) >= 2


class TestAuthenticationErrors:
    """Test authentication error handling"""

    @pytest.mark.asyncio
    async def test_missing_token(self, client: AsyncClient):
        """Test accessing protected endpoint without token"""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_invalid_token_format(self, client: AsyncClient):
        """Test with malformed token"""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_format"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "invalid" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_revoked_token(self, client: AsyncClient, auth_token: str):
        """Test using revoked token"""
        # Revoke token
        await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        # Try to use revoked token
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert "revoked" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_wrong_password(self, client: AsyncClient, test_user: User):
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
        assert data["status_code"] == 401


class TestNotFoundErrors:
    """Test 404 error handling"""

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, client: AsyncClient):
        """Test login with non-existent user"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401  # Auth returns 401 for security
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, client: AsyncClient, auth_token: str):
        """Test accessing non-existent file"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/files/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["status_code"] == 404


class TestForbiddenErrors:
    """Test 403 forbidden error handling"""

    @pytest.mark.asyncio
    async def test_access_other_user_file(
        self, client: AsyncClient, auth_token: str, admin_token: str, sample_image_file
    ):
        """Test accessing another user's file"""
        # User 1 uploads file
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            upload_response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        file_id = upload_response.json()["data"]["id"]

        # User 2 tries to access
        response = await client.get(
            f"/api/v1/files/{file_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["status_code"] == 403


class TestBadRequestErrors:
    """Test 400 bad request error handling"""

    @pytest.mark.asyncio
    async def test_duplicate_email(self, client: AsyncClient, test_user: User):
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
        assert data["status_code"] == 400
        assert "already" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_invalid_file_type(
        self, client: AsyncClient, auth_token: str, tmp_path
    ):
        """Test uploading invalid file type"""
        # Create invalid file
        exe_file = tmp_path / "malware.exe"
        exe_file.write_bytes(b"MZ\x90\x00")

        with open(exe_file, "rb") as f:
            files = {"file": ("malware.exe", f, "application/x-msdownload")}
            response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["status_code"] == 400


class TestResponseFormat:
    """Test that all error responses follow the standard format"""

    @pytest.mark.asyncio
    async def test_error_response_structure(self, client: AsyncClient):
        """Test that error responses have correct structure"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrong@example.com",
                "password": "wrong",
            },
        )

        data = response.json()

        # Check all required fields exist
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "status_code" in data

        # Check types
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)
        assert isinstance(data["status_code"], int)

        # Check values for error
        assert data["success"] is False
        assert len(data["message"]) > 0
        assert data["status_code"] >= 400

    @pytest.mark.asyncio
    async def test_success_response_structure(
        self, client: AsyncClient, test_user: User
    ):
        """Test that success responses have correct structure"""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            },
        )

        data = response.json()

        # Check all required fields exist
        assert "success" in data
        assert "message" in data
        assert "data" in data
        assert "status_code" in data

        # Check values for success
        assert data["success"] is True
        assert data["status_code"] == 200
        assert data["data"] is not None


class TestHTTPStatusCodes:
    """Test that correct HTTP status codes are returned"""

    @pytest.mark.asyncio
    async def test_200_on_success(self, client: AsyncClient, test_user: User):
        """Test 200 status code on success"""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpassword123"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_400_on_bad_request(self, client: AsyncClient, test_user: User):
        """Test 400 status code on bad request"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "different",
                "email": test_user.email,  # Duplicate
                "password": "password123",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_401_on_unauthorized(self, client: AsyncClient):
        """Test 401 status code on unauthorized"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_403_on_forbidden(
        self, client: AsyncClient, auth_token: str, admin_token: str, sample_image_file
    ):
        """Test 403 status code on forbidden"""
        # Upload as user 1
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            upload_response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        file_id = upload_response.json()["data"]["id"]

        # Try to delete as user 2
        response = await client.delete(
            f"/api/v1/files/{file_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_404_on_not_found(self, client: AsyncClient, auth_token: str):
        """Test 404 status code on not found"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/files/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_422_on_validation_error(self, client: AsyncClient):
        """Test 422 status code on validation error"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "test",
                "email": "invalid-email",
                "password": "123",
            },
        )
        assert response.status_code == 422
