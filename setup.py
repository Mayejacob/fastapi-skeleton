#!/usr/bin/env python3
"""Interactive setup script for FastAPI Skeleton.

Run this once after cloning to generate a configured .env file.
"""

import secrets
import sys
from pathlib import Path


def prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{question}{suffix}: ").strip()
    return answer if answer else default


def prompt_choice(question: str, choices: list, default: str) -> str:
    choices_display = "/".join(choices)
    while True:
        answer = input(f"{question} ({choices_display}) [{default}]: ").strip().lower()
        if not answer:
            return default
        if answer in choices:
            return answer
        print(f"  Please choose one of: {choices_display}")


def main() -> None:
    base_dir = Path(__file__).parent
    env_example = base_dir / ".env.example"
    env_file = base_dir / ".env"

    if not env_example.exists():
        print("Error: .env.example not found.")
        sys.exit(1)

    if env_file.exists():
        action = prompt_choice(
            "\n.env already exists. What would you like to do?\n"
            "  overwrite — replace it\n"
            "  backup    — save current as .env.bak and create new\n"
            "  cancel    — abort\n"
            "Choice",
            ["overwrite", "backup", "cancel"],
            "cancel",
        )
        if action == "cancel":
            print("Setup cancelled.")
            sys.exit(0)
        if action == "backup":
            bak_file = base_dir / ".env.bak"
            env_file.rename(bak_file)
            print(f"  Backed up existing .env → .env.bak")

    print("\nFastAPI Skeleton — Interactive Setup")
    print("=" * 42)
    print("Press Enter to accept the default shown in [brackets].\n")

    # ── App ──────────────────────────────────────────────────────────────────
    app_name = prompt("App name", "FastAPI App")
    app_url = prompt("App URL", "http://localhost:8000")
    environment = prompt_choice(
        "Environment", ["development", "staging", "production"], "development"
    )
    debug = "true" if environment == "development" else "false"

    # ── Database ─────────────────────────────────────────────────────────────
    print("\n--- Database ---")
    db_type = prompt_choice("Database type", ["postgresql", "sqlite"], "postgresql")
    if db_type == "postgresql":
        db_user = prompt("  User", "postgres")
        db_password = prompt("  Password", "password")
        db_host = prompt("  Host", "localhost")
        db_port = prompt("  Port", "5432")
        db_name = prompt("  Database name", app_name.lower().replace(" ", "_"))
        database_url = (
            f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        )
    else:
        db_file = prompt("  SQLite filename", "db.sqlite")
        database_url = f"sqlite+aiosqlite:///{db_file}"

    # ── Cache ────────────────────────────────────────────────────────────────
    print("\n--- Cache ---")
    cache_type = prompt_choice("Cache type", ["inmemory", "redis", "database"], "inmemory")
    redis_url = "redis://localhost:6379/0"
    if cache_type == "redis":
        redis_host = prompt("  Redis host", "localhost")
        redis_port = prompt("  Redis port", "6379")
        redis_password = input("  Redis password (leave blank if none): ").strip()
        redis_db = prompt("  Redis database index", "0")
        if redis_password:
            redis_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
        else:
            redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

    # ── Rate Limiting ────────────────────────────────────────────────────────
    rate_limit_enabled = "false"
    if cache_type == "redis":
        rate_limit_enabled = prompt_choice(
            "Enable rate limiting (requires Redis)", ["true", "false"], "false"
        )

    # ── Security ─────────────────────────────────────────────────────────────
    print("\n--- Security ---")
    secret_key = secrets.token_hex(32)
    print(f"  SECRET_KEY auto-generated.")
    access_token_expire = prompt("Access token expiry (minutes)", "30")
    refresh_token_expire = prompt("Refresh token expiry (days)", "30")

    # ── CORS & Trusted Hosts ─────────────────────────────────────────────────
    print("\n--- CORS & Trusted Hosts ---")
    if environment == "production":
        allowed_origins = prompt(
            "Allowed origins (comma-separated)", "https://yourdomain.com"
        )
        allowed_hosts = prompt(
            "Allowed hosts (comma-separated)", "yourdomain.com,www.yourdomain.com"
        )
    else:
        allowed_origins = prompt("Allowed origins", "*")
        allowed_hosts = "*"

    # ── Email ────────────────────────────────────────────────────────────────
    print("\n--- Email ---")
    print("  (Press Enter to keep placeholder defaults — you can edit .env later)")
    email_host = prompt("  SMTP host", "smtp.example.com")
    email_port = prompt("  SMTP port", "587")
    email_username = prompt("  SMTP username", "your-email@example.com")
    email_password = prompt("  SMTP password", "your-password")
    email_from = prompt("  From address", email_username)
    suppress_send = "1" if environment == "development" else "0"

    # ── Write .env ───────────────────────────────────────────────────────────
    env_content = f"""# App
APP_NAME={app_name}
APP_URL={app_url}
PROJECT_VERSION=1.0.0
DEBUG={debug}
ALLOWED_ORIGINS={allowed_origins}
ALLOWED_HOSTS={allowed_hosts}
ENVIRONMENT={environment}

# Database
DATABASE_URL={database_url}

# Cache
CACHE_TYPE={cache_type}
REDIS_URL={redis_url}

# Rate Limiting
RATE_LIMIT_ENABLED={rate_limit_enabled}

# Security
SECRET_KEY={secret_key}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES={access_token_expire}
REFRESH_TOKEN_EXPIRE_DAYS={refresh_token_expire}

# File Upload
UPLOAD_DIR=uploads

# Email
EMAIL_HOST={email_host}
EMAIL_PORT={email_port}
EMAIL_USERNAME={email_username}
EMAIL_PASSWORD={email_password}
EMAIL_FROM={email_from}
MAIL_STARTTLS=True
MAIL_SSL_TLS=False
TEMPLATE_FOLDER=templates/emails
SUPPRESS_SEND={suppress_send}
"""

    env_file.write_text(env_content)

    print("\n" + "=" * 42)
    print(f"  .env created successfully!")
    print("=" * 42)
    print("\nNext steps:")
    print("  1. Review .env and adjust any values")
    print("  2. Apply migrations:  alembic upgrade head")
    print("  3. Start the server:  uvicorn main:app --reload")
    print("\n  API docs: http://localhost:8000/docs")
    print("  Health:   http://localhost:8000/health\n")


if __name__ == "__main__":
    main()
