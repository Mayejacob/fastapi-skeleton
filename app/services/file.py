import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import HTTPException, status, UploadFile

from app.core.config import settings


class FileService:
    """Handles file uploads to disk and returns the stored filename."""

    def __init__(self, upload_dir: str = None):
        self.upload_dir = Path(upload_dir or getattr(settings, "UPLOAD_DIR", "uploads"))
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _generate_secure_filename(self, original_filename: str) -> str:
        extension = Path(original_filename).suffix.lower()
        return f"{secrets.token_urlsafe(16)}{extension}"

    async def upload_file(
        self,
        file: UploadFile,
        allowed_types: Optional[List[str]] = None,
        max_size_mb: int = 10,
    ) -> str:
        """
        Upload a file to disk.

        Returns:
            Relative path string (e.g. "2025/04/abc123.jpg") to be stored by the caller.

        Raises:
            HTTPException: If MIME type or size validation fails.
        """
        max_size_bytes = max_size_mb * 1024 * 1024

        if allowed_types and file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(allowed_types)}",
            )

        secure_filename = self._generate_secure_filename(file.filename)

        now = datetime.now(timezone.utc)
        subdirs = self.upload_dir / str(now.year) / f"{now.month:02d}"
        subdirs.mkdir(parents=True, exist_ok=True)

        file_path = subdirs / secure_filename
        relative_path = str(file_path.relative_to(self.upload_dir))

        try:
            file_size = 0
            with open(file_path, "wb") as f:
                while chunk := await file.read(8192):
                    file_size += len(chunk)
                    if file_size > max_size_bytes:
                        file_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"File too large. Maximum size: {max_size_mb}MB",
                        )
                    f.write(chunk)
        except HTTPException:
            raise
        except Exception as e:
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File upload failed: {str(e)}",
            )

        return relative_path

    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file from disk.

        Args:
            relative_path: Path relative to upload_dir (as returned by upload_file).

        Returns:
            True if file existed and was deleted, False if not found.
        """
        file_path = self.upload_dir / relative_path
        if file_path.exists():
            file_path.unlink()
            return True
        return False
