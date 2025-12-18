import secrets
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.file import UploadedFile
from app.core.config import settings


class FileService:
    """Service for file upload/delete operations"""

    def __init__(self, db: AsyncSession, upload_dir: str = None):
        self.db = db
        self.upload_dir = Path(upload_dir or getattr(settings, "UPLOAD_DIR", "uploads"))
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _generate_secure_filename(self, original_filename: str) -> tuple[str, str]:
        """
        Generate a secure, unique filename

        Args:
            original_filename: Original file name

        Returns:
            Tuple of (secure_filename, extension)
        """
        # Get file extension
        path = Path(original_filename)
        extension = path.suffix.lower()

        # Generate secure random filename
        random_name = secrets.token_urlsafe(16)
        secure_filename = f"{random_name}{extension}"

        return secure_filename, extension

    def _validate_file(
        self,
        file: UploadFile,
        allowed_types: Optional[List[str]] = None,
        max_size_mb: int = 10,
    ) -> None:
        """
        Validate file type and size

        Args:
            file: Uploaded file
            allowed_types: List of allowed MIME types
            max_size_mb: Maximum file size in MB

        Raises:
            HTTPException: If validation fails
        """
        # Check MIME type if restrictions specified
        if allowed_types and file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(allowed_types)}",
            )

        # Note: Size validation should be done during upload with streaming
        # This is a placeholder for the max size config
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def upload_file(
        self,
        file: UploadFile,
        user_id: Optional[uuid.UUID] = None,
        purpose: Optional[str] = None,
        allowed_types: Optional[List[str]] = None,
        max_size_mb: int = 10,
    ) -> UploadedFile:
        """
        Upload a file

        Args:
            file: File to upload
            user_id: ID of user uploading the file
            purpose: Purpose of the file (e.g., "avatar", "document")
            allowed_types: List of allowed MIME types
            max_size_mb: Maximum file size in MB

        Returns:
            UploadedFile database record

        Raises:
            HTTPException: If upload fails
        """
        # Validate file
        self._validate_file(file, allowed_types, max_size_mb)

        # Check file size if available (some clients provide this upfront)
        if hasattr(file, 'size') and file.size is not None:
            if file.size > self.max_size_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File too large. Maximum size: {max_size_mb}MB",
                )

        # Generate secure filename
        secure_filename, extension = self._generate_secure_filename(file.filename)

        # Create subdirectories based on date (year/month)
        now = datetime.now(timezone.utc)
        subdirs = self.upload_dir / str(now.year) / f"{now.month:02d}"
        subdirs.mkdir(parents=True, exist_ok=True)

        # Full file path
        file_path = subdirs / secure_filename
        relative_path = str(file_path.relative_to(self.upload_dir))

        try:
            # Write file in chunks
            file_size = 0
            with open(file_path, "wb") as f:
                while chunk := await file.read(8192):  # 8KB chunks
                    file_size += len(chunk)

                    # Check size limit
                    if file_size > self.max_size_bytes:
                        # Delete partial file
                        file_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"File too large. Maximum size: {max_size_mb}MB",
                        )

                    f.write(chunk)

            # Create database record
            uploaded_file = UploadedFile(
                user_id=user_id,
                filename=secure_filename,
                original_filename=file.filename,
                file_path=relative_path,
                file_size=file_size,
                mime_type=file.content_type,
                purpose=purpose,
            )

            self.db.add(uploaded_file)
            await self.db.flush()
            await self.db.refresh(uploaded_file)

            return uploaded_file

        except HTTPException:
            raise
        except Exception as e:
            # Clean up file if database operation fails
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File upload failed: {str(e)}",
            )

    async def delete_file(
        self, file_id: uuid.UUID, soft_delete: bool = True
    ) -> bool:
        """
        Delete a file (soft or hard delete)

        Args:
            file_id: File UUID
            soft_delete: If True, mark as deleted but keep file; if False, delete physically

        Returns:
            True if deleted, False if not found

        Raises:
            HTTPException: If deletion fails
        """
        # Get file record
        result = await self.db.execute(
            select(UploadedFile).where(UploadedFile.id == file_id)
        )
        file_record = result.scalar_one_or_none()

        if not file_record:
            return False

        if soft_delete:
            # Soft delete: just mark as deleted
            file_record.deleted_at = datetime.now(timezone.utc)
            await self.db.flush()
        else:
            # Hard delete: remove file and database record
            file_path = self.upload_dir / file_record.file_path

            # Delete physical file
            if file_path.exists():
                file_path.unlink()

            # Delete database record
            await self.db.delete(file_record)
            await self.db.flush()

        return True

    async def get_file(self, file_id: uuid.UUID) -> Optional[UploadedFile]:
        """
        Get file record by ID

        Args:
            file_id: File UUID

        Returns:
            UploadedFile object or None
        """
        result = await self.db.execute(
            select(UploadedFile).where(
                UploadedFile.id == file_id, UploadedFile.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def get_user_files(
        self, user_id: uuid.UUID, purpose: Optional[str] = None
    ) -> List[UploadedFile]:
        """
        Get all files for a user

        Args:
            user_id: User UUID
            purpose: Optional filter by purpose

        Returns:
            List of UploadedFile objects
        """
        query = select(UploadedFile).where(
            UploadedFile.user_id == user_id, UploadedFile.deleted_at.is_(None)
        )

        if purpose:
            query = query.where(UploadedFile.purpose == purpose)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    def get_file_path(self, file_record: UploadedFile) -> Path:
        """
        Get full filesystem path for a file

        Args:
            file_record: UploadedFile database record

        Returns:
            Full Path to the file
        """
        return self.upload_dir / file_record.file_path
