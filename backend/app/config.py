"""Application configuration.

Settings are loaded from environment variables (and an optional ``.env`` file)
using pydantic-settings. Sensible development defaults are provided so the
project runs out-of-the-box with SQLite, while production can point
``DATABASE_URL`` at PostgreSQL without any code changes.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Attributes:
        app_name: Human-readable service name.
        environment: Deployment environment (``development``/``production``).
        debug: Enables verbose behaviour and API docs.
        database_url: SQLAlchemy connection string. Defaults to a local
            SQLite file so the app runs with zero external dependencies.
            Set to a ``postgresql+psycopg://...`` URL for production.
        cors_origins: Comma-separated list of allowed frontend origins.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "BOTMARKET"
    environment: str = "development"
    debug: bool = True

    # SQLite by default; swap for PostgreSQL via the DATABASE_URL env var.
    database_url: str = "sqlite:///./botmarket.db"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a clean list of strings."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (loaded once per process)."""
    return Settings()
