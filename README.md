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

## Setup

### Prerequisites

- Python 3.10+.
- PostgreSQL (or SQLite for local dev/testing).
- Redis (optional, for caching/rate limiting).

### Cloning and Initial Setup

1. Clone the repo:  
   `git clone https://github.com/Mayejacob/fastapi-skeleton.git`
2. Navigate to the project directory:  
   `cd fastapi-skeleton`

3. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

4. Install dependencies:  
   `pip install -r requirements.txt`

5. Generate a secure SECRET_KEY:  
   `python generate_secret.py`  
   Copy the output to `.env` (e.g., `SECRET_KEY=abc123...`).

6. Copy `.env.example` to `.env` and configure:
   - Set `DATABASE_URL` (e.g., for SQLite: `sqlite+aiosqlite:///db.sqlite`).
   - Set email/Redis details if needed.
   - Set `DEBUG=true` for local dev.
   - For rate limiting: Set `RATE_LIMIT_ENABLED=true` and provide `REDIS_URL`.

### Running Migrations

1. Initialize Alembic (if not done):  
   `alembic init migrations`  
   _(This creates `migrations/`; ensure `migrations/env.py` imports your models correctly.)_

2. Generate a migration for existing models (e.g., User):  
   `alembic revision --autogenerate -m "Initial migration"`
3. Apply migrations:  
   `alembic upgrade head`  
   _(To rollback a migration, use `alembic downgrade <revision>`; for example, `alembic downgrade -1` to undo the last migration.)_

### Starting the Project Locally

1. Run the app:  
   `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

2. Access:
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`
   - Root: `http://localhost:8000/`
   - Health: `http://localhost:8000/health`

### Running Tests Locally

1. Ensure test DB (SQLite in-memory) is configured.
2. Run all tests:  
   `pytest tests/ -v`  
   Or with coverage:  
   `pytest tests/ --cov=app/ --cov-report=html`

### Deploying to Production

1. **Environment**:
   - Set `DEBUG=false`.
   - Use production DB (e.g., PostgreSQL on a managed service like AWS RDS).
   - Set `ALLOWED_ORIGINS` to specific domains (e.g., `https://yourdomain.com`).
   - Enable `RATE_LIMIT_ENABLED=true` for security.
   - Use a WSGI/ASGI server like Gunicorn + Uvicorn:  
     `gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker`

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
