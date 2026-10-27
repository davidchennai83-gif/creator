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
    # Config chain: root .env (secrets/compose) then backend/.env (local overrides;
    # later file wins). backend/.env.public used to sit here and silently force
    # COOKIE_SECURE + a stale ngrok origin — it is no longer loaded.
    model_config = SettingsConfigDict(env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    SERVER_HOST: str = "127.0.0.1"
    SERVER_PORT: int = Field(default=8000, ge=1, le=65535)
    TLS_CERTFILE: str = ""
    TLS_KEYFILE: str = ""
    COOKIE_SECURE: bool = False
    REQUIRE_REDIS: bool = False
    ALLOW_REGISTRATION: bool = True
    # Disable the scheduler/voice/ops loops in tests or single-request tooling.
    BACKGROUND_WORKERS: bool = True

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
    # Public address used in Meesho video descriptions and the click-tracking
    # redirect (/go/<product_id>). Override in .env when the tunnel changes.
    FINDS_PUBLIC_BASE_URL: str = "https://desktop-57mkr8o.tail979641.ts.net"
    # Optional AI copy for the daily Meesho video. The deterministic template is
    # still used whenever the local model is unavailable or returns unsafe copy.
    # Set MEESHO_AI_COPY=false in .env to force the old template.
    MEESHO_AI_COPY: bool = True
    MEESHO_AI_MODEL: str = "gemma3:4b"

    AI_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:4b"
    HISTORY_MODEL: str = "gemma3:4b"
    # Rewrites ten RSS headlines into spoken Tamil bulletin lines. Off by
    # default: the extractive summary keeps every fact exactly as published.
    # A 4B model can invert a fact ("in custody" -> "on bail"), which is not
    # acceptable on a news channel; enable only after reviewing its output.
    NEWS_AI_REWRITE: bool = False
    NEWS_MODEL: str = "gemma3:4b"
    HISTORY_FONT: str = "C:/Windows/Fonts/Nirmala.ttf"
    PEXELS_API_KEY: SecretStr = SecretStr("")

    # Video rendering: portrait short-video output and optional AI video provider.
    VIDEO_OUTPUT_WIDTH: int = 1080
    VIDEO_OUTPUT_HEIGHT: int = 1920
    VIDEO_FPS: int = 24
    # Animated end-card (Like / Share / Subscribe) appended to every narrated
    # video. CHANNEL_NAME is optional — leave it empty for a generic tagline.
    CHANNEL_NAME: str = ""
    OUTRO_SECONDS: float = 3.4
    # 'local' renders animated-image motion (Ken Burns / parallax / particles).
    # 'http' connects a generic image-to-video/text-to-video API (see video_gen.py).
    VIDEO_PROVIDER: str = "local"
    VIDEO_PROVIDER_URL: str = ""
    VIDEO_PROVIDER_KEY: SecretStr = SecretStr("")
    VIDEO_PROVIDER_MODEL: str = ""
    VIDEO_PROVIDER_TIMEOUT: int = 900
    SUBTITLE_FONT: str = "Nirmala UI"
    # Scene videos already carry the full sentence on screen. Burning the same
    # narration again as ASS subtitles duplicates the words and can overlap them.
    # Keep SRT/JSON captions for uploads, but leave this off for a clean picture.
    BURN_SUBTITLES: bool = False

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    # Honour X-Forwarded-For for rate-limit keys only when this process is reachable
    # through a reverse proxy (docker compose sets true; direct exposure must stay false).
    TRUST_PROXY: bool = False
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

    # ── Recorder (local Windows agent: desktop + already-open-Chrome capture) ──
    # Recordings are plain .py scripts under RECORDINGS_PATH/<web|desktop>/.
    RECORDINGS_PATH: str = str(BACKEND_DIR / "storage" / "recorder")
    # Playwright automation projects live under AUTOMATION_PATH/projects/<project>/.
    AUTOMATION_PATH: str = str(BACKEND_DIR / "storage" / "automation")
    # Hard limit for a single automation run. The watchdog kills the whole process
    # tree on expiry so a hung script can never hold the automation gate forever.
    AUTOMATION_RUN_TIMEOUT: int = Field(default=3600, ge=30, le=86400)
    # Shared secret the local agent must present in `recorder_register` before it
    # is allowed to receive commands. Leave empty to accept any agent (LAN/dev only).
    RECORDER_AGENT_TOKEN: SecretStr = SecretStr("")
    # Chrome DevTools port used to attach to the browser the user already has open.
    RECORDER_CHROME_DEBUG_PORT: int = Field(default=9222, ge=1024, le=65535)
    # Seconds to wait for Chrome's debugging endpoint to come up after launching it.
    RECORDER_CHROME_LAUNCH_TIMEOUT: int = Field(default=25, ge=5, le=120)
    # Port is open, but the browser was NOT started with --remote-debugging-port
    # (e.g. it was already running on the default profile). Set false to fail
    # loudly instead of closing and relaunching the user's Chrome.
    RECORDER_RELAUNCH_CHROME: bool = True

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
