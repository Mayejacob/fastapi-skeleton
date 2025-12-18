from typing import Annotated, Optional
import uuid

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import DBDependency
from app.core.responses import send_success
from app.core.security import get_current_user
from app.db.models.user import User
from app.services.file import FileService
from app.core.config import settings


router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    purpose: Optional[str] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: DBDependency = None,
):
    """
    Upload a file

    - **file**: The file to upload
    - **purpose**: Optional purpose tag (e.g., "avatar", "document")
    """
    file_service = FileService(db)

    # Parse allowed types from settings
    allowed_types = [
        t.strip() for t in settings.ALLOWED_UPLOAD_TYPES.split(",") if t.strip()
    ]

    # Upload file
    uploaded = await file_service.upload_file(
        file=file,
        user_id=current_user.id if current_user else None,
        purpose=purpose,
        allowed_types=allowed_types,
        max_size_mb=settings.MAX_UPLOAD_SIZE_MB,
    )

    # Commit to database
    await db.commit()

    return send_success(
        message="File uploaded successfully",
        data={
            "id": str(uploaded.id),
            "filename": uploaded.filename,
            "original_filename": uploaded.original_filename,
            "file_size": uploaded.file_size,
            "mime_type": uploaded.mime_type,
            "purpose": uploaded.purpose,
            "created_at": uploaded.created_at.isoformat(),
        },
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: DBDependency,
    hard_delete: bool = False,
):
    """
    Delete a file (soft delete by default)

    - **file_id**: UUID of the file to delete
    - **hard_delete**: If true, permanently delete the file from disk
    """
    file_service = FileService(db)

    # Get file and verify ownership
    file_record = await file_service.get_file(file_id)

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check if user owns the file
    if file_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this file"
        )

    # Delete file
    deleted = await file_service.delete_file(file_id, soft_delete=not hard_delete)

    # Commit changes
    await db.commit()

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    return send_success(
        message="File deleted successfully",
        data={"hard_delete": hard_delete},
    )


@router.get("/my-files")
async def get_my_files(
    current_user: Annotated[User, Depends(get_current_user)],
    purpose: Optional[str] = None,
    db: DBDependency = None,
):
    """
    Get current user's files

    - **purpose**: Optional filter by purpose (e.g., "avatar", "document")
    """
    file_service = FileService(db)

    # Get user's files
    files = await file_service.get_user_files(user_id=current_user.id, purpose=purpose)

    return send_success(
        data=[
            {
                "id": str(f.id),
                "filename": f.filename,
                "original_filename": f.original_filename,
                "file_size": f.file_size,
                "mime_type": f.mime_type,
                "purpose": f.purpose,
                "created_at": f.created_at.isoformat(),
            }
            for f in files
        ],
        message=f"Found {len(files)} file(s)",
    )


@router.get("/{file_id}")
async def get_file_info(
    file_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: DBDependency,
):
    """
    Get file information

    - **file_id**: UUID of the file
    """
    file_service = FileService(db)

    # Get file
    file_record = await file_service.get_file(file_id)

    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check if user owns the file
    if file_record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this file"
        )

    return send_success(
        data={
            "id": str(file_record.id),
            "filename": file_record.filename,
            "original_filename": file_record.original_filename,
            "file_path": file_record.file_path,
            "file_size": file_record.file_size,
            "mime_type": file_record.mime_type,
            "purpose": file_record.purpose,
            "created_at": file_record.created_at.isoformat(),
        }
    )
