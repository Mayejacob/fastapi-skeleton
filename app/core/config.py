from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import secrets  # For key generation if needed


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    # App Settings
    APP_NAME: str = "FastAPI Skeleton"
    APP_URL: str = "http://localhost:8000"
    PROJECT_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "*"  # Comma-separated string or "*"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = False

    DATABASE_URL: str
    CACHE_TYPE: str = "inmemory"  # inmemory, redis, or database
    REDIS_URL: str | None = None
    SECRET_KEY: str = ""  # Required; validate below
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str
    EMAIL_FROM: str
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/app.log"

    # Parse ALLOWED_ORIGINS
    @property
    def allowed_origins_list(self) -> List[str]:
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def secret_key_valid(self) -> bool:
        return bool(
            self.SECRET_KEY and self.SECRET_KEY != "your-secret-key"
        )  # Basic check; customize if needed


settings = Settings()

# Validate SECRET_KEY on import (will raise ValidationError if invalid)
if not settings.secret_key_valid:
    raise ValueError(
        "SECRET_KEY must be set in .env (run python generate_secret.py to generate one)."
    )
