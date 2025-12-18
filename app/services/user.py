import uuid
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.db.models.user import User


class UserService:
    """Service for user CRUD operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Get user by ID

        Args:
            user_id: User's UUID

        Returns:
            User object or None if not found
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email

        Args:
            email: User's email

        Returns:
            User object or None if not found
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username

        Args:
            username: User's username

        Returns:
            User object or None if not found
        """
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def update_user(
        self, user_id: uuid.UUID, **fields: Dict[str, Any]
    ) -> User:
        """
        Update user fields

        Args:
            user_id: User's UUID
            **fields: Fields to update

        Returns:
            Updated User object

        Raises:
            HTTPException: If user not found
        """
        user = await self.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Update fields
        for field, value in fields.items():
            if hasattr(user, field):
                setattr(user, field, value)

        # Update timestamp
        user.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """
        Delete user account

        Args:
            user_id: User's UUID

        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(user_id)

        if not user:
            return False

        await self.db.delete(user)
        await self.db.flush()

        return True

    async def exists_by_email(self, email: str) -> bool:
        """
        Check if user exists by email

        Args:
            email: User's email

        Returns:
            True if exists, False otherwise
        """
        user = await self.get_by_email(email)
        return user is not None

    async def exists_by_username(self, username: str) -> bool:
        """
        Check if user exists by username

        Args:
            username: User's username

        Returns:
            True if exists, False otherwise
        """
        user = await self.get_by_username(username)
        return user is not None
