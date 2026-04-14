"""Application configuration loaded from environment variables.

Classes:
    Settings: Pydantic BaseSettings model that reads from .env file
        and provides typed access to all configuration values.
"""

import logging

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All values can be overridden via environment variables or a .env file
    in the project root. The field names map to uppercase env var names
    (e.g. ``app_env`` reads ``APP_ENV``).
    """

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        """Accept both comma-separated string and JSON list for CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://cra_user:cra_password@localhost:5432/cra_db",
        alias="DATABASE_URL",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        """Ensure the async psycopg3 driver prefix is used.

        Railway (and many PaaS providers) inject ``postgresql://`` URLs.
        SQLAlchemy's async engine requires ``postgresql+psycopg://``.
        """
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    # LLM APIs
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_host: str = "http://localhost:11434"

    # GitHub App
    github_app_id: int | None = None
    github_app_private_key: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_webhook_secret: str = ""

    # JWT
    jwt_secret: str = Field(
        default="change-me-in-production",
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Encryption
    fernet_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        env_ignore_empty=True,
    )


settings = Settings()

_DEFAULT_JWT_SECRET = "change-me-in-production"
if settings.jwt_secret == _DEFAULT_JWT_SECRET and settings.app_env != "development":
    _logger.critical(
        "JWT_SECRET is set to the default value '%s'. "
        "Anyone can forge valid tokens. Set a strong JWT_SECRET env var immediately.",
        _DEFAULT_JWT_SECRET,
    )

if not settings.github_webhook_secret:
    _logger.warning(
        "GITHUB_WEBHOOK_SECRET is not set. "
        "All incoming webhook requests will be rejected with 401."
    )
