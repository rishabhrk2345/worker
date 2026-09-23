"""
apps/api/core/config.py

Authoritative configuration settings loaded from environment variables.
"""

from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Resolve .env from the repo root regardless of working directory.
# Walks up from this file (apps/api/core/) until it finds a .env file
# or bottoms out at the filesystem root.
def _find_env_file() -> str:
    here = Path(__file__).resolve().parent
    for directory in [here, *here.parents]:
        candidate = directory / ".env"
        if candidate.exists():
            return str(candidate)
    return ".env"  # fallback — let pydantic-settings handle missing gracefully


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application
    APP_ENV: str = Field(default="development")
    APP_NAME: str = Field(default="ai-marketing-os")
    LOG_LEVEL: str = Field(default="INFO")
    SIMULATION_MODE: bool = Field(default=True)

    # Tenancy defaults
    DEFAULT_ORG_ID: str = Field(default="00000000-0000-0000-0000-000000000001")
    DEFAULT_ORG_NAME: str = Field(default="Acme Growth Corp")

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./aimarketing_os.db",
        description="Async database connection string. Defaults to SQLite for local tests, PostgreSQL in Docker."
    )
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Temporal
    TEMPORAL_HOST: str = Field(default="localhost:7233")
    TEMPORAL_NAMESPACE: str = Field(default="default")
    TEMPORAL_TASK_QUEUE: str = Field(default="aimarketing-workforce-queue")

    # Security
    JWT_SECRET: str = Field(default="super-secret-jwt-key-minimum-32-chars-change-in-prod")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_MINUTES: int = Field(default=1440)
    CREDENTIAL_ENCRYPTION_KEY: str = Field(
        default="dGhpcy1pcy1hLTMyLWJ5dGUtc2VjcmV0LWtleS0xMjM0NTY=",
        description="32-byte base64-encoded AES-256-GCM encryption key"
    )

    # CORS
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://127.0.0.1:3000"])

    # LLM & Embedding Defaults
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LITELLM_CHEAP_MODEL: str = "gpt-4o-mini"
    LITELLM_MEDIUM_MODEL: str = "gpt-4o"
    LITELLM_STRONG_MODEL: str = "claude-3-7-sonnet"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # Source connector keys
    YOUTUBE_API_KEY: Optional[str] = None   # YouTube Data API v3 (optional — Invidious fallback used if blank)
    SERPAPI_KEY: Optional[str] = None
    NEWSAPI_KEY: Optional[str] = None
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None

    # Rate limiting (per-org defaults)
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=120)
    RATE_LIMIT_BURST: int = Field(default=20)

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_SERVICE_NAME: str = Field(default="ai-marketing-os-api")

settings = Settings()
