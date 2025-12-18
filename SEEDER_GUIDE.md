# 🌱 Seeder System - Complete Guide

## Overview

The seeder system provides a generic, auto-discovering infrastructure for populating your database with initial or test data. It's environment-aware, supports execution ordering, and is completely reusable across projects.

---

## 📁 Seeder System Structure

```
app/db/seeders/
├── __init__.py           # Package marker
├── base.py               # BaseSeeder abstract class
├── runner.py             # SeederRunner (auto-discovery + execution)
└── user_seeder.py        # Example: UserSeeder

seed.py                   # CLI script (project root)
```

---

## 🚀 Quick Start

### Running Seeders

```bash
# Run all seeders (auto-discovers and runs in order)
python seed.py

# Run a specific seeder
python seed.py UserSeeder

# Run in a specific environment
python seed.py --env=production

# Show help
python seed.py --help
```

### Expected Output

```
INFO: Running all seeders...
INFO: Discovered 1 seeder(s) for environment: development
INFO: Running 1 seeder(s)...
INFO: → Running UserSeeder...
  ✓ Created user: admin@example.com (password: admin123)
  ✓ Created user: test@example.com (password: test123)
  ✓ Created user: john@example.com (password: john123)
INFO: ✓ UserSeeder completed successfully
INFO: All seeders completed!
INFO: Seeding completed successfully!
```

---

## 📝 Creating Your Own Seeder

### Step 1: Create the Seeder File

Create a new file in `app/db/seeders/`. The filename should end with `_seeder.py` (convention).

**Example:** `app/db/seeders/post_seeder.py`

```python
from datetime import datetime, timezone
from sqlalchemy import select

from app.db.seeders.base import BaseSeeder
from app.db.models.user import User
from app.db.models.post import Post  # Your model


class PostSeeder(BaseSeeder):
    """Seed sample blog posts"""

    # Execution order (lower numbers run first)
    # UserSeeder is 10, so posts should come after users
    order = 20

    # Environments where this should run
    # Don't seed posts in production!
    environments = ["development", "test"]

    async def seed(self) -> None:
        """Create sample posts"""

        # Get a user to associate posts with
        result = await self.db.execute(
            select(User).where(User.email == "admin@example.com")
        )
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            print("  ⚠ Admin user not found, skipping post seeding")
            return

        # Sample posts
        posts_data = [
            {
                "title": "Welcome to FastAPI",
                "content": "This is a sample blog post...",
                "user_id": admin_user.id,
            },
            {
                "title": "Building RESTful APIs",
                "content": "FastAPI makes it easy...",
                "user_id": admin_user.id,
            },
        ]

        for post_data in posts_data:
            # Check if post exists (by title)
            result = await self.db.execute(
                select(Post).where(Post.title == post_data["title"])
            )
            existing_post = result.scalar_one_or_none()

            if existing_post:
                print(f"  ⊙ Post already exists: {post_data['title']}")
                continue

            # Create new post
            post = Post(**post_data)
            self.db.add(post)
            print(f"  ✓ Created post: {post_data['title']}")

        # Flush changes (commit happens automatically in base class)
        await self.db.flush()
```

### Step 2: Run Your Seeder

The seeder will be **automatically discovered** when you run:

```bash
python seed.py
```

Or run it specifically:

```bash
python seed.py PostSeeder
```

---

## 🎯 Seeder Best Practices

### 1. **Always Check if Data Exists**

Make seeders idempotent (safe to run multiple times):


# Create only if doesn't exist
user = User(**user_data)
self.db.add(user)
```


### 2. **Use Execution Order Wisely**

Order matters when seeders depend on each other:

```python
# UserSeeder should run first
class UserSeeder(BaseSeeder):
    order = 10  # Lower = runs first

# PostSeeder needs users to exist
class PostSeeder(BaseSeeder):
    order = 20  # Runs after users

# CommentSeeder needs posts to exist
class CommentSeeder(BaseSeeder):
    order = 30  # Runs after posts
```

**Common Order Convention:**
- **1-10:** System/configuration data
- **10-20:** Users, roles, permissions
- **20-30:** Main content (posts, products, etc.)
- **30-40:** Related content (comments, reviews, etc.)
- **40+:** Analytics, logs, etc.

### 3. **Use Environment Filtering**

```python
class UserSeeder(BaseSeeder):
    # Only run in dev and test
    environments = ["development", "test"]

class SystemConfigSeeder(BaseSeeder):
    # Run in all environments
    environments = ["development", "test", "staging", "production"]

class DemoDataSeeder(BaseSeeder):
    # Only in development
    environments = ["development"]
```

### 4. **Provide Helpful Output**


**Emoji Convention:**
- `→` Starting a task
- `✓` Success
- `⊙` Already exists (skipped)
- `⚠` Warning
- `✗` Error

### 5. **Use Realistic Test Data**


---

## 📚 Advanced Examples

### Example 1: Seeder with Relationships


First, install Faker:
```bash
pip install faker
```

Then create the seeder:

```python
from faker import Faker

class FakeUserSeeder(BaseSeeder):
    """Generate realistic fake users for testing"""

    order = 15
    environments = ["development", "test"]

    async def seed(self):
        fake = Faker()
        num_users = 50

        for i in range(num_users):
            email = fake.email()

            # Check if exists
            result = await self.db.execute(
                select(User).where(User.email == email)
            )
            if result.scalar_one_or_none():
                continue

            user = User(
                username=fake.user_name(),
                email=email,
                hashed_password=get_password_hash("password123"),
                is_active=True,
                email_verified_at=fake.date_time_this_year(),
            )
            self.db.add(user)

        await self.db.flush()
        print(f"  ✓ Created {num_users} fake users")
```

---

## 🔧 BaseSeeder API Reference

### Class Attributes

```python
class BaseSeeder(ABC):
    # Execution order (lower runs first)
    order: ClassVar[int] = 100

    # Environments where seeder runs
    environments: ClassVar[list] = ["development", "test"]
```

---

## 🎮 SeederRunner Usage

### Programmatic Usage

---

## 🐛 Troubleshooting

### Seeder Not Discovered

**Problem:** Your seeder doesn't appear when running `python seed.py`

**Solutions:**
1. Make sure file is in `app/db/seeders/`
2. Filename should end with `_seeder.py` (convention)
3. Class must inherit from `BaseSeeder`
4. Class must implement `async def seed(self)`

## 📊 Real-World Seeding Strategy

### Development Environment

```python
# 1. System data (always run)
class SystemConfigSeeder(BaseSeeder):
    order = 1
    environments = ["development", "test", "staging", "production"]

# 2. Basic users
class UserSeeder(BaseSeeder):
    order = 10
    environments = ["development", "test"]

# 3. Realistic fake data
class FakeUserSeeder(BaseSeeder):
    order = 15
    environments = ["development"]  # Only in dev

# 4. Content
class PostSeeder(BaseSeeder):
    order = 20
    environments = ["development", "test"]

# 5. Demo data
class DemoDataSeeder(BaseSeeder):
    order = 100
    environments = ["development"]  # Only for demos
```


## 🎯 Quick Reference

### Running Seeders

```bash
# All seeders
python seed.py

# Specific seeder
python seed.py UserSeeder

# Different environment
python seed.py --env=production
```

### Creating a Seeder (Template)

```python
from app.db.seeders.base import BaseSeeder
from app.db.models.your_model import YourModel
from sqlalchemy import select

class YourModelSeeder(BaseSeeder):
    """Description of what this seeds"""

    order = 20  # Execution order
    environments = ["development", "test"]

    async def seed(self) -> None:
        """Seed your data"""
        data = [
            {"field": "value1"},
            {"field": "value2"},
        ]

        for item_data in data:
            # Check if exists
            result = await self.db.execute(
                select(YourModel).where(YourModel.field == item_data["field"])
            )
            if result.scalar_one_or_none():
                print(f"  ⊙ Already exists: {item_data['field']}")
                continue

            # Create
            item = YourModel(**item_data)
            self.db.add(item)
            print(f"  ✓ Created: {item_data['field']}")

        await self.db.flush()
```

---

