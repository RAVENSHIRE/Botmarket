"""Pydantic schemas for API request/response bodies.

Kept separate from the ORM models so the wire format can evolve independently
of the database schema.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentOut(BaseModel):
    """Public representation of an agent."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    agent_type: str
    personality: str
    strategy: str
    wallet: float
    reputation: float
    status: str
    created_at: datetime


class AgentCreate(BaseModel):
    """Request body for registering a new agent."""

    name: str = Field(min_length=1, max_length=120)
    agent_type: str = Field(pattern="^(trader|meme|analyst)$")
    wallet: float = 1000.0


class PostOut(BaseModel):
    """Public representation of a feed post."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    content: str
    kind: str
    tick: int
    likes: int
    created_at: datetime


class PostCreate(BaseModel):
    """Request body for an agent posting to the social feed."""

    content: str = Field(min_length=1, max_length=1000)
    kind: str = Field(default="post", max_length=50)


class HealthOut(BaseModel):
    """Health-check response."""

    status: str
    app: str
    environment: str


class TickResult(BaseModel):
    """Summary returned after advancing the simulation one tick."""

    tick: int
    market_price: float
    market_trend: float
    event: dict | None
    posts_created: int
    actions: list[dict]
    leaderboard: list[dict]


class CoinCreate(BaseModel):
    """Request body for launching a memecoin."""

    name: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=20)
    base_price: float = Field(default=1.0, gt=0)
    slope: float = Field(default=0.01, ge=0)
    # Optional creator allocation bought at launch (funded from the wallet).
    initial_buy: float = Field(default=0.0, ge=0)


class CoinTrade(BaseModel):
    """Request body for buying or selling a coin."""

    agent_id: int
    qty: float = Field(gt=0)


class CoinOut(BaseModel):
    """Public representation of a coin, enriched with computed price/market cap."""

    id: int
    name: str
    symbol: str
    creator_id: int
    creator_name: str | None
    supply: float
    reserve: float
    base_price: float
    slope: float
    spot_price: float
    market_cap: float
    status: str
    tick: int


class CoinTradeResult(BaseModel):
    """Result of a buy or sell against the bonding curve."""

    coin_id: int
    agent_id: int
    qty: float
    cost_or_proceeds: float
    new_spot_price: float
    wallet: float
    holding: float
    status: str
