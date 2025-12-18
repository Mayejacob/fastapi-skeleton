"""
Tests for file management endpoints

Tests use SQLite in-memory database and temporary upload directories
"""
import pytest
from httpx import AsyncClient
from pathlib import Path
import io

from app.db.models.user import User


class TestFileUpload:
    """Test file upload endpoint"""

    @pytest.mark.asyncio
    async def test_upload_image_success(
        self, client: AsyncClient, auth_token: str, sample_image_file: Path
    ):
        """Test successful image upload"""
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "File uploaded successfully"
        assert "id" in data["data"]
        assert data["data"]["original_filename"] == "test.jpg"
        assert data["data"]["mime_type"] == "image/jpeg"
        assert data["data"]["file_size"] > 0

    @pytest.mark.asyncio
    async def test_upload_pdf_success(
        self, client: AsyncClient, auth_token: str, sample_pdf_file: Path
    ):
        """Test successful PDF upload"""
        with open(sample_pdf_file, "rb") as f:
            files = {"file": ("document.pdf", f, "application/pdf")}
            response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["mime_type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_upload_with_purpose(
        self, client: AsyncClient, auth_token: str, sample_image_file: Path
    ):
        """Test file upload with purpose tag"""
        with open(sample_image_file, "rb") as f:
            files = {"file": ("avatar.jpg", f, "image/jpeg")}
            data_form = {"purpose": "avatar"}
            response = await client.post(
                "/api/v1/files/upload",
                files=files,
                data=data_form,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["purpose"] == "avatar"

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(
        self, client: AsyncClient, auth_token: str, tmp_path
    ):
        """Test upload with disallowed file type"""
        # Create a .exe file
        exe_file = tmp_path / "malware.exe"
        exe_file.write_bytes(b"MZ\x90\x00")  # PE header

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
        assert "not allowed" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_upload_file_too_large(
        self, client: AsyncClient, auth_token: str, tmp_path
    ):
        """Test upload with file exceeding size limit"""
        # Create file larger than 10MB (default limit)
        large_file = tmp_path / "large.jpg"
        large_file.write_bytes(b"\x00" * (11 * 1024 * 1024))  # 11MB

        with open(large_file, "rb") as f:
            files = {"file": ("large.jpg", f, "image/jpeg")}
            response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "too large" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_upload_without_auth(
        self, client: AsyncClient, sample_image_file: Path
    ):
        """Test file upload without authentication"""
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            response = await client.post("/api/v1/files/upload", files=files)

        assert response.status_code == 401


class TestListFiles:
    """Test file listing endpoint"""

    @pytest.mark.asyncio
    async def test_list_my_files(
        self, client: AsyncClient, auth_token: str, sample_image_file: Path
    ):
        """Test listing user's files"""
        # Upload a file first
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        # List files
        response = await client.get(
            "/api/v1/files/my-files",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1
        assert "1 file(s)" in data["message"]

    @pytest.mark.asyncio
    async def test_list_files_by_purpose(
        self, client: AsyncClient, auth_token: str, sample_image_file: Path
    ):
        """Test filtering files by purpose"""
        # Upload with purpose
        with open(sample_image_file, "rb") as f:
            files = {"file": ("avatar.jpg", f, "image/jpeg")}
            data_form = {"purpose": "avatar"}
            await client.post(
                "/api/v1/files/upload",
                files=files,
                data=data_form,
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        # List by purpose
        response = await client.get(
            "/api/v1/files/my-files?purpose=avatar",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert all(f["purpose"] == "avatar" for f in data["data"])

    @pytest.mark.asyncio
    async def test_list_files_empty(self, client: AsyncClient, auth_token: str):
        """Test listing files when user has none"""
        response = await client.get(
            "/api/v1/files/my-files",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []
        assert "0 file(s)" in data["message"]


class TestGetFileInfo:
    """Test get file info endpoint"""

    @pytest.mark.asyncio
    async def test_get_file_info_success(
        self, client: AsyncClient, auth_token: str, sample_image_file: Path
    ):
        """Test getting file information"""
        # Upload file
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            upload_response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        file_id = upload_response.json()["data"]["id"]

        # Get file info
        response = await client.get(
            f"/api/v1/files/{file_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == file_id
        assert "file_path" in data["data"]

    @pytest.mark.asyncio
    async def test_get_file_info_nonexistent(
        self, client: AsyncClient, auth_token: str
    ):
        """Test getting info for non-existent file"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/files/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_get_file_info_unauthorized(
        self,
        client: AsyncClient,
        auth_token: str,
        admin_token: str,
        sample_image_file: Path,
    ):
        """Test accessing another user's file"""
        # User uploads file
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            upload_response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        file_id = upload_response.json()["data"]["id"]

        # Admin tries to access user's file
        response = await client.get(
            f"/api/v1/files/{file_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False


class TestDeleteFile:
    """Test file deletion endpoint"""

    @pytest.mark.asyncio
    async def test_soft_delete_file(
        self, client: AsyncClient, auth_token: str, sample_image_file: Path
    ):
        """Test soft deletion of file"""
        # Upload file
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            upload_response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        file_id = upload_response.json()["data"]["id"]

        # Soft delete
        response = await client.delete(
            f"/api/v1/files/{file_id}?hard_delete=false",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["hard_delete"] is False

    @pytest.mark.asyncio
    async def test_hard_delete_file(
        self, client: AsyncClient, auth_token: str, sample_image_file: Path
    ):
        """Test hard deletion of file"""
        # Upload file
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            upload_response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        file_id = upload_response.json()["data"]["id"]

        # Hard delete
        response = await client.delete(
            f"/api/v1/files/{file_id}?hard_delete=true",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["hard_delete"] is True

    @pytest.mark.asyncio
    async def test_delete_file_unauthorized(
        self,
        client: AsyncClient,
        auth_token: str,
        admin_token: str,
        sample_image_file: Path,
    ):
        """Test deleting another user's file"""
        # User uploads file
        with open(sample_image_file, "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            upload_response = await client.post(
                "/api/v1/files/upload",
                files=files,
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        file_id = upload_response.json()["data"]["id"]

        # Admin tries to delete user's file
        response = await client.delete(
            f"/api/v1/files/{file_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(
        self, client: AsyncClient, auth_token: str
    ):
        """Test deleting non-existent file"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/api/v1/files/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
