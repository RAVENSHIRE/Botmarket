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
        venue_encryption_key: Fernet key protecting venue secrets at rest.
            Empty means no secret can be stored, so only paper trading works.
        trading_enabled: Global kill switch for every venue order.
        allow_mainnet: Whether real-money orders may be placed at all.
        max_leverage: Highest leverage any order may request.
        min_order_value: Dust floor for a single order.
        max_order_value: Ceiling for a single order's notional.
        max_position_value: Ceiling for one symbol's notional.
        max_gross_notional: Ceiling for total exposure across positions.
        max_daily_loss: Realised loss past which only reducing orders pass.
        paper_starting_balance: Cash a new paper account is opened with.
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

    # --- Live trading ---------------------------------------------------
    # Defaults are the safe ones: paper trading, mainnet off. Going live is
    # something an operator does on purpose, never something a default does.
    venue_encryption_key: str = ""
    trading_enabled: bool = True
    allow_mainnet: bool = False
    max_leverage: int = 5
    min_order_value: float = 10.0
    max_order_value: float = 1000.0
    max_position_value: float = 5000.0
    max_gross_notional: float = 25_000.0
    max_daily_loss: float = 500.0
    paper_starting_balance: float = 10_000.0

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a clean list of strings."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance (loaded once per process)."""
    return Settings()
