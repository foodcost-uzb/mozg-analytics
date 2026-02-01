from functools import lru_cache
from typing import Optional

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "MOZG Analytics"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://mozg:mozg_secret_password@localhost:5432/mozg_analytics"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # 5 minutes default cache TTL

    # Security
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_WEBAPP_URL: Optional[str] = None

    # iiko API
    IIKO_API_URL: str = "https://api-ru.iiko.services"
    IIKO_API_LOGIN: Optional[str] = None

    # R-Keeper API
    RKEEPER_API_URL: Optional[str] = None
    RKEEPER_API_KEY: Optional[str] = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    @property
    def database_url_sync(self) -> str:
        """Return sync database URL for Alembic."""
        return self.DATABASE_URL.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
