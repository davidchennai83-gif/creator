from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum
from typing import Optional
from pathlib import Path
import secrets
from pydantic import Field, SecretStr, model_validator

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env", BACKEND_DIR / ".env.public"), env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = Field(default=8000, ge=1, le=65535)
    TLS_CERTFILE: str = ""
    TLS_KEYFILE: str = ""
    COOKIE_SECURE: bool = False
    REQUIRE_REDIS: bool = False
    ALLOW_REGISTRATION: bool = True

    DATABASE_URL: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'creator_platform.db').as_posix()}"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(48), min_length=32)
    JWT_REFRESH_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(48), min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    BCRYPT_ROUNDS: int = 12

    STORAGE_PROVIDER: str = "local"
    STORAGE_PATH: str = str(BACKEND_DIR / "storage")

    AI_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:4b"
    HISTORY_MODEL: str = "gemma3:4b"
    HISTORY_FONT: str = "C:/Windows/Fonts/Nirmala.ttf"
    PEXELS_API_KEY: SecretStr = SecretStr("")

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MAX_FILE_SIZE: int = 20 * 1024 * 1024
    UPLOAD_MAX_FILES: int = 20

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_TIMEZONE: str = "UTC"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_ACK_LATE: bool = True
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    CELERY_TASK_RETRY_DEFAULT: int = 3

    WORKER_CONCURRENCY: int = 4
    VIDEO_QUEUE_NAME: str = "video_queue"
    PUBLISHING_QUEUE_NAME: str = "publishing_queue"
    ANALYTICS_QUEUE_NAME: str = "analytics_queue"
    NOTIFICATION_QUEUE_NAME: str = "notification_queue"
    AFFILIATE_QUEUE_NAME: str = "affiliate_queue"
    COMMERCE_QUEUE_NAME: str = "commerce_queue"
    AI_QUEUE_NAME: str = "ai_queue"

    SENTRY_DSN: Optional[str] = None
    WORKSPACE_ID: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None
    EMAIL_FROM: str = "noreply@creator-platform.com"

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.JWT_ALGORITHM != "HS256":
            raise ValueError("Only HS256 is configured")
        if bool(self.TLS_CERTFILE) != bool(self.TLS_KEYFILE):
            raise ValueError("TLS requires both certificate and key")
        if self.ENVIRONMENT == Environment.PRODUCTION:
            for name in ("JWT_SECRET", "JWT_REFRESH_SECRET"):
                value = getattr(self, name)
                if name not in self.model_fields_set or len(value) < 32 or "change-me" in value:
                    raise ValueError(f"Set a unique {name} of at least 32 characters")
            if self.JWT_SECRET == self.JWT_REFRESH_SECRET or not self.COOKIE_SECURE:
                raise ValueError("Production requires separate signing keys and secure cookies")
        return self

settings = Settings()

def get_database_url() -> str:
    return settings.DATABASE_URL

def get_sync_database_url() -> str:
    return settings.DATABASE_URL.replace("sqlite+aiosqlite:", "sqlite:").replace("postgresql+asyncpg:", "postgresql+psycopg2:")
