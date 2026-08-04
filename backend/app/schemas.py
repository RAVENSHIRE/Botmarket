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
