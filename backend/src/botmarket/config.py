"""Application configuration.

Settings are loaded from environment variables (and an optional ``.env`` file)
using pydantic-settings. Sensible development defaults are provided so the
project runs out-of-the-box with SQLite, while production can point
``DATABASE_URL`` at PostgreSQL without any code changes.

Economic constants live here too, so the simulation can be re-tuned from the
environment without touching code.
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
        starting_wallet: Credits granted to a newly registered agent.
        trade_fee_rate: Fraction of a $BOT trade burned as a fee.
        coin_launch_fee: Credits burned to launch a memecoin.
        coin_base_price: Price of the first unit on a memecoin bonding curve.
        coin_slope: Per-unit price increase along the bonding curve.
        coin_graduation_reserve: Reserve at which a memecoin graduates.
        proposal_cost: Credits burned to submit a governance proposal.
        proposal_voting_ticks: Ticks a proposal stays open for voting.
        proposal_quorum: Minimum total vote weight for a proposal to pass.
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

    # --- Economy -------------------------------------------------------
    starting_wallet: float = 1000.0
    trade_fee_rate: float = 0.003

    coin_launch_fee: float = 100.0
    coin_base_price: float = 1.0
    coin_slope: float = 0.01
    coin_graduation_reserve: float = 5_000.0

    proposal_cost: float = 250.0
    proposal_voting_ticks: int = 3
    proposal_quorum: float = 1.0

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a clean list of strings."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (loaded once per process)."""
    return Settings()
