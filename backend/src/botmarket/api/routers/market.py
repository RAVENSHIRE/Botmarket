"""The native $BOT market and the agent leaderboard."""

from __future__ import annotations

from fastapi import APIRouter, Query

from botmarket.api.deps import DbSession
from botmarket.api.schemas import LeaderRow, MarketOut
from botmarket.services import agents as agents_service
from botmarket.services import market as market_service

router = APIRouter(tags=["market"])


@router.get("/market", response_model=MarketOut)
def market(db: DbSession):
    """Return the current $BOT price, trend and recent history."""
    return market_service.snapshot(db)


@router.get("/leaderboard", response_model=list[LeaderRow])
def leaderboard(db: DbSession, limit: int = Query(default=10, ge=1, le=100)):
    """Return the top agents ranked by net worth."""
    return agents_service.leaderboard(db, limit=limit)
