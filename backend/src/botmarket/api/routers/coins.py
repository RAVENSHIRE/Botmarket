"""Memecoin endpoints.

Launching lives on the creating agent (``POST /agents/{id}/coins``); the coin
itself is traded here, against its bonding curve.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from botmarket.api.deps import DbSession
from botmarket.api.schemas import CoinOut, CoinTradeCreate, CoinTradeOut
from botmarket.repositories import coins as coins_repo
from botmarket.services import coins as coins_service

router = APIRouter(prefix="/coins", tags=["coins"])


@router.get("", response_model=list[CoinOut])
def list_coins(
    db: DbSession,
    status: str | None = Query(default=None, description="Filter: live or graduated."),
):
    """List every launched memecoin, newest first."""
    return [coins_service.describe(db, coin) for coin in coins_repo.list_all(db, status=status)]


@router.get("/{coin_id}", response_model=CoinOut)
def get_coin(coin_id: int, db: DbSession):
    """Fetch one memecoin with its current curve figures."""
    return coins_service.describe(db, coins_service.require(db, coin_id))


@router.post("/{coin_id}/buy", response_model=CoinTradeOut)
def buy_coin(coin_id: int, payload: CoinTradeCreate, db: DbSession):
    """Mint units of a coin, paying the bonding curve's price."""
    return coins_service.buy(
        db, coin_id=coin_id, agent_id=payload.agent_id, quantity=payload.quantity
    )


@router.post("/{coin_id}/sell", response_model=CoinTradeOut)
def sell_coin(coin_id: int, payload: CoinTradeCreate, db: DbSession):
    """Burn units of a coin, refunding credits from its reserve."""
    return coins_service.sell(
        db, coin_id=coin_id, agent_id=payload.agent_id, quantity=payload.quantity
    )
