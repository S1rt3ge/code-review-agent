"""Application configuration loaded from environment variables.

Classes:
    Settings: Pydantic BaseSettings model that reads from .env file
        and provides typed access to all configuration values.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
