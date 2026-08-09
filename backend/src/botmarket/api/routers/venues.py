"""Live trading endpoints: venue accounts, orders and the risk envelope.

Order placement is nested under the account that will bear the risk, so a caller
cannot place an order without having named whose money is at stake.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response, status

from botmarket.api.deps import CallerAgent, DbSession, require_self
from botmarket.api.schemas import (
    PositionOut,
    RiskLimitsOut,
    VenueAccountCreate,
    VenueAccountOut,
    VenueInfo,
    VenueOrderCreate,
    VenueOrderOut,
    VenueOrderRow,
)
from botmarket.config import get_settings
from botmarket.domain.errors import Forbidden
from botmarket.services import live as live_service
from botmarket.venues import registry

router = APIRouter(tags=["live"])


@router.get("/venues", response_model=list[VenueInfo])
def list_venues():
    """Describe the venues this deployment can trade on."""
    return registry.describe_venues()


@router.get("/venues/limits", response_model=RiskLimitsOut)
def risk_limits():
    """Return the risk envelope every order is checked against."""
    limits = live_service.limits_from(get_settings())
    return RiskLimitsOut(
        trading_enabled=limits.trading_enabled,
        max_leverage=limits.max_leverage,
        min_order_value=float(limits.min_order_value),
        max_order_value=float(limits.max_order_value),
        max_position_value=float(limits.max_position_value),
        max_gross_notional=float(limits.max_gross_notional),
        max_daily_loss=float(limits.max_daily_loss),
        allow_mainnet=limits.allow_mainnet,
    )


@router.get("/agents/{agent_id}/venues", response_model=list[VenueAccountOut])
def list_agent_venues(agent_id: int, db: DbSession):
    """List an agent's venue accounts, without contacting any exchange."""
    return [
        live_service.describe_account(account)
        for account in live_service.accounts_for(db, agent_id)
    ]


@router.post(
    "/agents/{agent_id}/venues",
    response_model=VenueAccountOut,
    status_code=status.HTTP_201_CREATED,
)
def link_venue(
    agent_id: int, payload: VenueAccountCreate, db: DbSession, caller: CallerAgent
):
    """Link an agent to a venue. Any secret is encrypted before storage."""
    require_self(caller, agent_id)
    account = live_service.link_account(
        db,
        agent_id=agent_id,
        venue=payload.venue,
        environment=payload.environment,
        label=payload.label,
        wallet_address=payload.wallet_address,
        secret=payload.secret,
    )
    return live_service.describe_account(account)


@router.get("/venue-accounts/{account_id}", response_model=VenueAccountOut)
def get_venue_account(account_id: int, db: DbSession):
    """Return an account with live balances and positions from its venue."""
    snapshot = live_service.snapshot(db, account_id)
    return live_service.describe_account(snapshot["account"], snapshot["state"])


@router.get("/venue-accounts/{account_id}/positions", response_model=list[PositionOut])
def get_positions(account_id: int, db: DbSession):
    """Return the account's open positions."""
    snapshot = live_service.snapshot(db, account_id)
    return live_service.describe_account(snapshot["account"], snapshot["state"])["positions"]


@router.get("/venue-accounts/{account_id}/orders", response_model=list[VenueOrderRow])
def get_order_history(
    account_id: int, db: DbSession, limit: int = Query(default=50, ge=1, le=200)
):
    """Return the audit trail, including orders refused by a risk rule."""
    return live_service.order_history(db, account_id, limit=limit)


@router.post("/venue-accounts/{account_id}/orders", response_model=VenueOrderOut)
def place_order(
    account_id: int, payload: VenueOrderCreate, db: DbSession, caller: CallerAgent
):
    """Place an order after risk checks. Mainnet requires explicit confirmation."""
    _require_owner(db, account_id, caller)
    return live_service.place_order(
        db,
        account_id=account_id,
        symbol=payload.symbol,
        side=payload.side,
        size=payload.size,
        order_type=payload.order_type,
        limit_price=payload.limit_price,
        leverage=payload.leverage,
        reduce_only=payload.reduce_only,
        confirm_real_money=payload.confirm_real_money,
    )


@router.post("/venue-accounts/{account_id}/close/{symbol}", response_model=VenueOrderOut)
def close_position(account_id: int, symbol: str, db: DbSession, caller: CallerAgent):
    """Flatten the account's position in ``symbol``."""
    _require_owner(db, account_id, caller)
    return live_service.close_position(db, account_id=account_id, symbol=symbol)


@router.post("/venue-accounts/{account_id}/active", response_model=VenueAccountOut)
def set_active(
    account_id: int, db: DbSession, caller: CallerAgent, active: bool = Query(...)
):
    """Enable or disable one account's trading."""
    _require_owner(db, account_id, caller)
    return live_service.describe_account(
        live_service.set_active(db, account_id, active=active)
    )


@router.delete(
    "/venue-accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def unlink_venue(account_id: int, db: DbSession, caller: CallerAgent) -> Response:
    """Delete an account and the credential stored with it."""
    _require_owner(db, account_id, caller)
    live_service.unlink_account(db, account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _require_owner(db, account_id: int, caller) -> None:
    """Assert the caller owns the venue account it is about to act on.

    A venue account is somebody's money. Knowing its id is not authority over
    it, so ownership is checked rather than inferred from the URL.
    """
    account = live_service.require_account(db, account_id)
    if account.agent_id != caller.id:
        raise Forbidden(
            f"Venue account {account_id} belongs to agent {account.agent_id}, "
            f"not agent {caller.id}"
        )
