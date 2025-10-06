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
- Migrations: Alembic for database schema management.
- Tests: Pytest with test database.

## Adding Features

- Models: `app/db/models/`
- Schemas: `app/db/schemas/`
- Endpoints: `app/api/v1/endpoints/`
- Services: `app/services/`
- Tests: `tests/`

Run tests: `pytest`

## Additional Setup for Migrations

After creating `alembic.ini` and `migrations/env.py`, ensure `migrations/env.py` points to your models (`app.db.base.Base`).  
Run `alembic revision --autogenerate -m "Initial migration"` to generate a migration script for the User model.  
Apply migrations with `alembic upgrade head`.

## Notes

- **Caching:** The `CACHE_TYPE` in `.env` defaults to `inmemory`. Set to `redis` and provide `REDIS_URL` to use Redis.
- **Database:** Use PostgreSQL for production (`postgresql+asyncpg://...`) or SQLite for dev/testing (`sqlite+aiosqlite:///db.sqlite`).
- **Security:** JWT tokens are validated with a secret key. Generate one with `openssl rand -hex 32`.
- **Extensibility:** Add new models, schemas, and endpoints by following the `user.py` examples.
- **Rate Limiting:** Install `slowapi` and add middleware if needed (not included by default to keep it lightweight).
