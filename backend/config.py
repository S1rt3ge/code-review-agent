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
    frontend_base_url: str = Field(
        default="http://localhost:5173",
        alias="FRONTEND_BASE_URL",
    )
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
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(default=30, alias="DB_POOL_TIMEOUT_SECONDS")
    db_pool_recycle_seconds: int = Field(default=1800, alias="DB_POOL_RECYCLE_SECONDS")
    db_connect_timeout_seconds: int = Field(
        default=10, alias="DB_CONNECT_TIMEOUT_SECONDS"
    )
    analysis_queue_poll_interval_seconds: float = Field(
        default=2.0,
        alias="ANALYSIS_QUEUE_POLL_INTERVAL_SECONDS",
    )
    analysis_queue_batch_size: int = Field(
        default=3,
        alias="ANALYSIS_QUEUE_BATCH_SIZE",
    )
    analysis_queue_max_attempts: int = Field(
        default=5,
        alias="ANALYSIS_QUEUE_MAX_ATTEMPTS",
    )
    analysis_queue_base_retry_seconds: int = Field(
        default=15,
        alias="ANALYSIS_QUEUE_BASE_RETRY_SECONDS",
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

    # Observability
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(
        default=0.2,
        alias="SENTRY_TRACES_SAMPLE_RATE",
    )
    sentry_profiles_sample_rate: float = Field(
        default=0.0,
        alias="SENTRY_PROFILES_SAMPLE_RATE",
    )

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

    # Auth rate limits
    auth_register_rate_limit: str = Field(
        default="5/minute",
        alias="AUTH_REGISTER_RATE_LIMIT",
    )
    auth_login_rate_limit: str = Field(
        default="5/minute",
        alias="AUTH_LOGIN_RATE_LIMIT",
    )
    auth_password_reset_rate_limit: str = Field(
        default="5/minute",
        alias="AUTH_PASSWORD_RESET_RATE_LIMIT",
    )
    auth_email_verify_rate_limit: str = Field(
        default="5/minute",
        alias="AUTH_EMAIL_VERIFY_RATE_LIMIT",
    )

    # Auth token expiration windows
    password_reset_token_expire_minutes: int = Field(
        default=30,
        alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
    )
    email_verification_token_expire_minutes: int = Field(
        default=1440,
        alias="EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES",
    )

    # Email delivery (SMTP). When unset, emails are logged.
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_from: str = Field(default="noreply@code-review-agent.local", alias="SMTP_FROM")

    # Realtime fan-out (optional). If unset, WebSocket updates are local-only.
    redis_url: str | None = Field(default=None, alias="REDIS_URL")

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
_NON_ENFORCED_ENVS = {"development", "dev", "local", "test", "testing"}


def _should_reject_default_jwt_secret(app_env: str, jwt_secret: str) -> bool:
    """Return True when app should refuse boot with default JWT secret."""
    return (
        jwt_secret == _DEFAULT_JWT_SECRET and app_env.lower() not in _NON_ENFORCED_ENVS
    )


if _should_reject_default_jwt_secret(settings.app_env, settings.jwt_secret):
    message = (
        "JWT_SECRET is set to the default value 'change-me-in-production'. "
        "Refusing to start in non-dev environment because tokens would be forgeable."
    )
    _logger.critical(message)
    raise RuntimeError(message)

if not settings.github_webhook_secret:
    _logger.warning(
        "GITHUB_WEBHOOK_SECRET is not set. "
        "All incoming webhook requests will be rejected with 401."
    )
