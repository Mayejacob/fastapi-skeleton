# FastAPI Skeleton

A modular, secure, and scalable FastAPI project template — ready for development and production.

![GitHub stars](https://img.shields.io/github/stars/Mayejacob/fastapi-skeleton?style=flat-square)
![GitHub forks](https://img.shields.io/github/forks/Mayejacob/fastapi-skeleton?style=flat-square)
![GitHub watchers](https://img.shields.io/github/watchers/Mayejacob/fastapi-skeleton?style=flat-square)
![GitHub issues](https://img.shields.io/github/issues/Mayejacob/fastapi-skeleton?style=flat-square)
![GitHub license](https://img.shields.io/github/license/Mayejacob/fastapi-skeleton?style=flat-square)
![Python version](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)

## Table of contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick setup](#quick-setup)
- [Manual setup](#manual-setup)
  - [Using pip](#using-pip)
  - [Using uv (recommended)](#using-uv-recommended)
- [Configuration reference](#configuration-reference)
- [Database & migrations](#database--migrations)
- [Seeding](#seeding)
- [Run options](#run-options)
- [Tests](#tests)
- [Deploying](#deploying)
- [Live demo](#live-demo)
- [Author](#author)

---

## Features

- Async SQLAlchemy models (PostgreSQL / SQLite)
- JWT authentication with OAuth2
- Multi-backend caching: in-memory, Redis, or database
- Optional Redis-based rate limiting
- Async email sending with Jinja2 templates
- Alembic migrations
- Seeder system with auto-discovery and environment filtering
- Pytest test suite with async support and HTML reports
- Loguru logging with file rotation
- APScheduler for background tasks

---

## Prerequisites

- Python 3.10+
- PostgreSQL (recommended) or SQLite (local dev)
- Redis (optional — required only for Redis cache or rate limiting)

---

## Quick setup

The fastest way to get started after cloning. The setup script interactively asks for your app name, database, cache type, and other settings, then generates a configured `.env` for you.

```bash
git clone https://github.com/Mayejacob/fastapi-skeleton.git
cd fastapi-skeleton

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # macOS / Linux
# On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the interactive setup (generates .env)
python setup.py

# Apply migrations and start
alembic upgrade head
uvicorn main:app --reload
```

Or with `uv`:

```bash
git clone https://github.com/Mayejacob/fastapi-skeleton.git
cd fastapi-skeleton

uv venv && source .venv/bin/activate
uv pip install -e .

python setup.py   # or: uv run python setup.py

alembic upgrade head
uvicorn main:app --reload
```

Once running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

---

## Manual setup

If you prefer to configure `.env` yourself instead of using the setup script.

### Using pip

1. Clone and enter the repo

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

4. Create `.env` and generate a secret key

```bash
cp .env.example .env
python generate_secret.py
# Paste the output into .env as SECRET_KEY
```

5. Apply migrations

```bash
alembic upgrade head
```

### Using uv (recommended)

`uv` is a faster Python package manager.

1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# On Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. Clone and set up

```bash
git clone https://github.com/Mayejacob/fastapi-skeleton.git
cd fastapi-skeleton

uv venv --python 3.11
source .venv/bin/activate   # macOS / Linux
# On Windows: .venv\Scripts\activate

uv pip install -e .
```

3. Create `.env` and generate a secret key

```bash
cp .env.example .env
uv run python generate_secret.py
# Paste the output into .env as SECRET_KEY
```

4. Apply migrations

```bash
uv run alembic upgrade head
```

> **Tip:** Use `uv run <command>` to run commands without activating the virtual environment, e.g. `uv run uvicorn main:app --reload`.

---

## Configuration reference

All options are set in `.env`. See `.env.example` for the full template.

### App

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | `My FastAPI App` | Application name shown in docs |
| `APP_URL` | `http://localhost:8000` | Base URL of the application |
| `PROJECT_VERSION` | `1.0.0` | API version shown in docs |
| `DEBUG` | `true` | FastAPI debug mode |
| `ENVIRONMENT` | `development` | `development`, `test`, `staging`, `production` |
| `ALLOWED_ORIGINS` | `*` | CORS origins — comma-separated URLs or `*` for all |

### Database

| Variable | Example | Description |
|---|---|---|
| `DATABASE_URL` | — | PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/db` |
| | | SQLite: `sqlite+aiosqlite:///db.sqlite` |

### Cache

| Variable | Default | Options | Description |
|---|---|---|---|
| `CACHE_TYPE` | `inmemory` | `inmemory`, `redis`, `database` | Caching backend |
| `REDIS_URL` | `redis://localhost:6379/0` | — | Required when `CACHE_TYPE=redis` |

### Rate limiting

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `false` | `true` requires a working `REDIS_URL` |

### Security

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | — | Generate with `python generate_secret.py` |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime |

### File upload

| Variable | Default | Description |
|---|---|---|
| `UPLOAD_DIR` | `uploads` | Directory where uploaded files are stored |

### Email

| Variable | Default | Description |
|---|---|---|
| `EMAIL_HOST` | `smtp.example.com` | SMTP server host |
| `EMAIL_PORT` | `587` | SMTP port (587 for STARTTLS, 465 for SSL) |
| `EMAIL_USERNAME` | — | SMTP login username |
| `EMAIL_PASSWORD` | — | SMTP login password |
| `EMAIL_FROM` | — | Sender address |
| `MAIL_STARTTLS` | `True` | Use STARTTLS (port 587) |
| `MAIL_SSL_TLS` | `False` | Use SSL/TLS (port 465) |
| `TEMPLATE_FOLDER` | `templates/emails` | Path to Jinja2 email templates |
| `SUPPRESS_SEND` | `0` | Set to `1` to mock sending (useful in development) |

---

## Database & migrations

```bash
# Generate a new migration after changing models
alembic revision --autogenerate -m "describe your change"

# Apply all pending migrations
alembic upgrade head

# Roll back the last migration
alembic downgrade -1
```

With uv, prefix each command with `uv run`.

---

## Seeding

### Running seeders

```bash
# Run all seeders (auto-discovered, ordered)
python seed.py

# Run a specific seeder
python seed.py UserSeeder

# Run for a specific environment
python seed.py --env=production

# Show help
python seed.py --help
```

### Creating a seeder

Create a file in `app/db/seeders/` ending in `_seeder.py`:

```python
from app.db.seeders.base import BaseSeeder
from app.db.models.user import User
from sqlalchemy import select


class PostSeeder(BaseSeeder):
    order = 20                             # lower numbers run first
    environments = ["development", "test"] # omit to run everywhere

    async def seed(self) -> None:
        result = await self.db.execute(select(User).where(User.email == "admin@example.com"))
        admin = result.scalar_one_or_none()
        if not admin:
            print("  ⚠ Admin user not found, skipping")
            return

        # add your records here
        await self.db.flush()
```

The seeder is **automatically discovered** the next time you run `python seed.py`.

### Order conventions

| Range | Use for |
|---|---|
| 1 – 10 | System / config data |
| 10 – 20 | Users, roles, permissions |
| 20 – 30 | Main content (posts, products, …) |
| 30 – 40 | Related content (comments, reviews, …) |
| 40+ | Analytics, logs, … |

### Output emoji convention

| Symbol | Meaning |
|---|---|
| `→` | Starting |
| `✓` | Created |
| `⊙` | Already exists (skipped) |
| `⚠` | Warning |
| `✗` | Error |

---

## Run options

### Development (auto-reload)

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# or
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production (Gunicorn + Uvicorn workers)

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
# or
uv run gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Adjust `-w` to match your CPU core count.

---

## Tests

```bash
# Run all tests
pytest -v

# Single file
pytest tests/test_token_service.py

# Single test
pytest tests/test_token_service.py::test_create_access_token

# With coverage
pytest --cov=app --cov-report=html
```

Prefix with `uv run` when using uv.

---

## Deploying

The repo includes `start.sh` for any hosting provider (Render, Railway, Fly.io, VPS, etc.). It runs migrations then starts Gunicorn:

```bash
#!/usr/bin/env bash
set -e

python -m alembic upgrade head
exec gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT
```

`python -m alembic` is used instead of the bare `alembic` binary to ensure the same Python environment that runs the app is also used for migrations — regardless of how the host activates the virtualenv.

For uv-based deployments, replace the above with:

```bash
uv run python -m alembic upgrade head
exec uv run gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT
```

---

## Live demo

https://fastapi-skeleton-nsr7.onrender.com

---

## Author

Jacob Olorunmaye  
GitHub: https://github.com/Mayejacob  
Website: https://mayeconcept.com.ng
