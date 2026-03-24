# FastAPI Skeleton

A modular, secure, and scalable FastAPI project template.

## Setup

1. Create virtual environment: `python -m venv venv && venv\Scripts\activate`
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure.
4. Initialize Alembic: `alembic init migrations`
5. Generate migration: `alembic revision --autogenerate -m "Initial migration"`
6. Apply migration: `alembic upgrade head`
7. Run: `uvicorn main:app --reload`
8. Access Swagger UI: `http://localhost:8000/docs`

## Features

- Database: PostgreSQL/SQLite with SQLAlchemy (async).
- Caching: In-memory (default) or Redis (configurable via `.env`).
- Authentication: JWT with OAuth2.
- Email: Async email sending.
- Logging: Loguru with file rotation.
- Responses: Reusable success/error responses.
# FastAPI Skeleton

A modular, secure, and scalable FastAPI project template — ready for development and production.

## Table of contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick install](#quick-install)
  - [Using pip (traditional)](#using-pip-traditional)
  - [Using uv (faster, recommended)](#using-uv-faster-recommended)
- [Environment](#environment)
- [Database & migrations](#database--migrations)
- [Seeding](#seeding)
- [Run options (development & production)](#run-options-development--production)
- [Tests](#tests)
- [Deploying / start scripts](#deploying--start-scripts)
- [Notes](#notes)
- [Live demo](#live-demo)
- [Author](#author)

## Features

- Async SQLAlchemy models (Postgres / SQLite)
- JWT authentication (OAuth2)
- Optional Redis caching and rate-limiting
- Async email sending
- Alembic migrations
- Pytest test suite

## Prerequisites

- Python 3.10+
- PostgreSQL (recommended for production) or SQLite for local development
- Redis (optional; required if you enable rate limiting or Redis cache)

## Quick install

Choose your preferred package manager:

### Using pip (traditional)

1. Clone the repo

```bash
git clone https://github.com/Mayejacob/fastapi-skeleton.git
cd fastapi-skeleton
```

2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # macOS / Linux
# On Windows: venv\Scripts\activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Create `.env` from the example

```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Generate a SECRET_KEY

```bash
python generate_secret.py
# Copy the printed value into .env as SECRET_KEY
```

### Using uv (faster, recommended)

`uv` is a next-generation Python package manager that's much faster than pip.

1. Install uv (if not already installed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or pip install uv
# On Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. Clone the repo

```bash
git clone https://github.com/Mayejacob/fastapi-skeleton.git
cd fastapi-skeleton
```

```bash
uv init

uv add -r requirements.in
```

3. Create virtual environment and install dependencies

```bash
# Create environment with Python 3.11 (recommended for stability)
uv venv --python 3.11
source .venv/bin/activate   # macOS / Linux
# On Windows: .venv\Scripts\activate

# Install all dependencies from requirements.txt
uv pip install -r requirements.txt
```

4. Create `.env` from the example and generate SECRET_KEY

```bash
cp .env.example .env
uv run python generate_secret.py
# Copy the printed value into .env as SECRET_KEY
```

💡 uv tips:

- Use `uv run <command>` to run commands without activating the virtual environment

Example: `uv run alembic upgrade head` or `uv run uvicorn main:app --reload`

- Update dependencies with `uv pip install --upgrade <package>`

## Environment

Edit `.env` with your configuration:

```bash
# Database (choose one)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname   # PostgreSQL
# DATABASE_URL=sqlite+aiosqlite:///db.sqlite                   # SQLite (local dev)

# Security
SECRET_KEY=your-secret-key-here  # Generate with python generate_secret.py

# Optional: Redis (for caching/rate limiting)
REDIS_URL=redis://localhost:6379/0
CACHE_TYPE=redis                  # or 'inmemory'
RATE_LIMIT_ENABLED=true

# Email (optional)
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=noreply@example.com
```

## Database & migrations

With pip:

```bash
# Generate initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

With uv:

```bash
# Generate initial migration
uv run alembic revision --autogenerate -m "Initial migration"

# Apply migrations
uv run alembic upgrade head

# Rollback last migration
uv run alembic downgrade -1
```

## Seeding

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

```python
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


## Run options (development & production)

### Development (auto-reload)

With pip:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

With uv:

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

### Production (with Gunicorn)

```bash
# With pip
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# With uv
uv run gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Adjust `-w` (worker count) to match your CPU cores.

## Tests

Run the test suite:

With pip:

```bash
pytest -v
pytest tests/test_token_service.py          # Single file
pytest tests/test_token_service.py::test_create_access_token  # Single test
```

With uv:

```bash
uv run pytest -v
uv run pytest tests/test_token_service.py   # Single file
```

With coverage:

```bash
# pip
pytest --cov=app --cov-report=html

# uv
uv run pytest --cov=app --cov-report=html
```

## Deploying / start scripts

The repo contains a start.sh for hosting providers (e.g., Render). For uv-based deployments, update it to:

```bash
#!/usr/bin/env bash
set -e

echo "🚀 Starting deployment process with uv..."
uv run alembic upgrade head
exec uv run gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT
```

Or for simpler deployments:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Notes

- Python version: Python 3.11 is recommended for stability with uv. Python 3.14 is not yet fully supported.

- Caching: Set `CACHE_TYPE=inmemory` (default) or `CACHE_TYPE=redis` and configure `REDIS_URL`.

- Database URLs: postgresql+asyncpg://... for Postgres, sqlite+aiosqlite:///db.sqlite for local dev.

- Security: Keep SECRET_KEY secret. Generate with openssl rand -hex 32 or python generate_secret.py.

- Rate limiting: To enable, set RATE_LIMIT_ENABLED=true and provide a working REDIS_URL.

## Live demo

https://fastapi-skeleton-nsr7.onrender.com

## Author

Jacob Olorunmaye

GitHub: Mayejacob

Website: mayeconcept.com.ng
