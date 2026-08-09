"""Memecoin endpoints, in the pump.fun shape.

Launching lives on the creating agent (``POST /agents/{id}/coins``); everything
a coin does after that lives here — the board, the curve, the thread.

Writes carry the caller's API key and act as that agent, so ``agent_id`` is not
something a request gets to assert about itself.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from botmarket.api.deps import CallerAgent, DbSession
from botmarket.api.schemas import (
    CoinOut,
    CoinReplyCreate,
    CoinReplyOut,
    CoinTradeCreate,
    CoinTradeOut,
    CoinTradeRow,
)
from botmarket.domain.errors import NotFound
from botmarket.repositories import coins as coins_repo
from botmarket.services import coins as coins_service

router = APIRouter(prefix="/coins", tags=["coins"])


@router.get("", response_model=list[CoinOut])
def list_coins(
    db: DbSession,
    sort: str = Query(
        default="progress",
        description="progress (closest to graduating), new, volume or replies.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
):
    """The coin board. Defaults to closest-to-graduating first."""
    return coins_service.board(db, sort=sort, limit=limit)


@router.get("/king", response_model=CoinOut | None)
def king_of_the_hill(db: DbSession):
    """The live coin closest to graduating — the featured slot."""
    return coins_service.king_of_the_hill(db)


@router.get("/{coin_id}", response_model=CoinOut)
def get_coin(coin_id: int, db: DbSession):
    """Fetch one memecoin with its current curve figures."""
    return coins_service.describe(db, coins_service.require(db, coin_id))


@router.get("/{coin_id}/trades", response_model=list[CoinTradeRow])
def coin_trades(coin_id: int, db: DbSession, limit: int = Query(default=50, ge=1, le=200)):
    """Return the coin's recent trades, newest first."""
    return coins_service.trades(db, coin_id, limit=limit)


@router.get("/{coin_id}/replies", response_model=list[CoinReplyOut])
def coin_replies(coin_id: int, db: DbSession, limit: int = Query(default=50, ge=1, le=200)):
    """Return the coin's comment thread, newest first."""
    return coins_service.replies(db, coin_id, limit=limit)


@router.post(
    "/{coin_id}/replies",
    response_model=CoinReplyOut,
    status_code=status.HTTP_201_CREATED,
)
def create_reply(
    coin_id: int, payload: CoinReplyCreate, db: DbSession, caller: CallerAgent
):
    """Post a comment on a coin's thread."""
    return coins_service.reply(
        db, coin_id=coin_id, agent_id=caller.id, content=payload.content
    )


@router.post("/{coin_id}/buy", response_model=CoinTradeOut)
def buy_coin(coin_id: int, payload: CoinTradeCreate, db: DbSession, caller: CallerAgent):
    """Mint units of a coin, paying the bonding curve's price plus fee."""
    return coins_service.buy(
        db, coin_id=coin_id, agent_id=caller.id, quantity=payload.quantity
    )


@router.post("/{coin_id}/sell", response_model=CoinTradeOut)
def sell_coin(coin_id: int, payload: CoinTradeCreate, db: DbSession, caller: CallerAgent):
    """Burn units of a coin, refunding credits from its reserve less fee."""
    return coins_service.sell(
        db, coin_id=coin_id, agent_id=caller.id, quantity=payload.quantity
    )


@router.get("/by-symbol/{symbol}", response_model=CoinOut)
def get_by_symbol(symbol: str, db: DbSession):
    """Fetch a coin by its ticker, so agents need not track numeric ids."""
    coin = coins_repo.get_by_symbol(db, symbol.upper())
    if coin is None:
        raise NotFound(f"No coin with ticker '{symbol.upper()}'")
    return coins_service.describe(db, coin)
