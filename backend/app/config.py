"""Application configuration using pydantic-settings.

All environment variables are loaded and validated here.
Import `settings` from anywhere in the app to access config values.

Usage:
    from app.config import settings
    print(settings.database_url)
"""

from typing import List
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Project root is one level up from backend/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Database ---
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/labassist",
        description="Async SQLAlchemy URL for PostgreSQL",
    )

    # Sync URL (needed for Alembic and seed script, which use synchronous connections)
    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "").replace(
            "postgresql://", "postgresql+psycopg2://"
        )

    # --- LLM (Qwen API) ---
    llm_api_base: str = Field(
        default="https://api.qwen.ai/v1",
        description="Base URL for the LLM API",
    )
    llm_api_key: str = Field(
        default="",
        description="API key for LLM authentication",
    )

    # --- Auth ---
    secret_key: str = Field(
        default="change-me-to-a-random-string",
        description="Secret key for JWT token signing",
    )
    access_token_expire_minutes: int = Field(
        default=60,
        description="JWT token expiration time in minutes",
    )

    # --- CORS ---
    # Comma-separated list of allowed origins (no spaces)
    cors_origins: str = Field(
        default="http://localhost",
        description="Comma-separated list of allowed CORS origins",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # --- App ---
    app_env: str = Field(
        default="development",
        description="Application environment (development / production)",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG / INFO / WARNING / ERROR)",
    )

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Singleton instance — import this from anywhere
settings = Settings()
