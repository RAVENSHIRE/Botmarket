"""Factor library endpoints.

Factor reads need no account and no credentials, so these endpoints work on a
fresh install against paper data — which is the point: a strategy should be
explorable before anything is at stake.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from botmarket.api.schemas import (
    FactorDetail,
    FactorEvaluation,
    FactorInfo,
    MarketRow,
)
from botmarket.services import factor_service

router = APIRouter(prefix="/factors", tags=["factors"])

DEFAULT_WATCHLIST = ("BTC", "ETH", "SOL")


@router.get("", response_model=list[FactorInfo])
def list_factors():
    """List every registered factor."""
    return factor_service.library()


@router.get("/market", response_model=list[MarketRow])
def market(
    symbols: str = Query(
        default=",".join(DEFAULT_WATCHLIST),
        description="Comma-separated symbols, e.g. BTC,ETH.",
    ),
    venue: str = Query(default="paper"),
    environment: str = Query(default="paper"),
    interval: str = Query(default="1h"),
):
    """Return one signal row per symbol, for a watchlist view."""
    wanted = [s.strip() for s in symbols.split(",") if s.strip()]
    return factor_service.market_overview(
        wanted, venue=venue, environment=environment, interval=interval
    )


@router.get("/{symbol}", response_model=FactorEvaluation)
def evaluate(
    symbol: str,
    venue: str = Query(default="paper"),
    environment: str = Query(default="paper"),
    interval: str = Query(default="1h"),
    horizon: int = Query(default=6, ge=1, le=48),
    limit: int = Query(default=200, ge=50, le=500),
):
    """Score every factor for ``symbol`` and blend the significant ones."""
    return factor_service.evaluate_symbol(
        symbol,
        venue=venue,
        environment=environment,
        interval=interval,
        horizon=horizon,
        limit=limit,
    )


@router.get("/{symbol}/{name}", response_model=FactorDetail)
def evaluate_one(
    symbol: str,
    name: str,
    venue: str = Query(default="paper"),
    environment: str = Query(default="paper"),
    interval: str = Query(default="1h"),
    horizon: int = Query(default=6, ge=1, le=48),
):
    """Return one factor's current value and score for ``symbol``."""
    return factor_service.evaluate_one(
        name,
        symbol,
        venue=venue,
        environment=environment,
        interval=interval,
        horizon=horizon,
    )
