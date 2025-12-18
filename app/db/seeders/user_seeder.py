from datetime import datetime, timezone
from sqlalchemy import select

from app.db.seeders.base import BaseSeeder
from app.db.models.user import User
from app.core.security import get_password_hash


class UserSeeder(BaseSeeder):
    """Seed initial users for development and testing"""

    order = 10  # Run early (low number = high priority)
    environments = ["development", "test"]  # Don't run in production

    async def seed(self) -> None:
        """Create test users"""

        users_data = [
            {
                "username": "admin",
                "email": "admin@example.com",
                "password": "admin123",
                "is_active": True,
            },
            {
                "username": "testuser",
                "email": "test@example.com",
                "password": "test123",
                "is_active": True,
            },
            {
                "username": "john",
                "email": "john@example.com",
                "password": "john123",
                "is_active": True,
            },
        ]

        for user_data in users_data:
            # Check if user already exists
            result = await self.db.execute(
                select(User).where(User.email == user_data["email"])
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"  ⊙ User already exists: {user_data['email']}")
                continue

            # Create new user
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=get_password_hash(user_data["password"]),
                is_active=user_data["is_active"],
                email_verified_at=datetime.now(timezone.utc),
            )

            self.db.add(user)
            print(f"  ✓ Created user: {user_data['email']} (password: {user_data['password']})")

        await self.db.flush()
