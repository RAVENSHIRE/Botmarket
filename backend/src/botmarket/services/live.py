"""Live trading: linking venue accounts and placing risk-checked orders.

This is the seam between the simulated society and a real exchange. An agent
that has earned standing in Botmarket can be handed a venue account, after which
its orders go through exactly one path:

    quote -> risk check -> venue -> audit row

Nothing bypasses it. :func:`place_order` is the only function that calls a
venue's ``place_order``, so the risk engine cannot be skipped by a future caller
who did not know it existed.

Every attempt is written to :class:`~botmarket.db.models.VenueOrder`, including
refusals. An autonomous agent that quietly does nothing is indistinguishable
from a broken one unless the refusal left a record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from botmarket.config import Settings, get_settings
from botmarket.db.models import VenueAccount, VenueOrder
from botmarket.domain.errors import Conflict, InvalidAction, NotFound
from botmarket.domain.risk import RiskLimits, RiskViolation, check_order
from botmarket.domain.venue import (
    AccountState,
    Environment,
    ExecutionVenue,
    OrderRequest,
    OrderResult,
    OrderType,
    Side,
)
from botmarket.services import agents as agents_service
from botmarket.services import credentials
from botmarket.venues import registry


def limits_from(settings: Settings) -> RiskLimits:
    """Build the risk envelope from configuration."""
    return RiskLimits(
        trading_enabled=settings.trading_enabled,
        max_leverage=settings.max_leverage,
        min_order_value=Decimal(str(settings.min_order_value)),
        max_order_value=Decimal(str(settings.max_order_value)),
        max_position_value=Decimal(str(settings.max_position_value)),
        max_gross_notional=Decimal(str(settings.max_gross_notional)),
        max_daily_loss=Decimal(str(settings.max_daily_loss)),
        allow_mainnet=settings.allow_mainnet,
    )


# --- Accounts ------------------------------------------------------------


def require_account(db: Session, account_id: int) -> VenueAccount:
    """Return a venue account or raise :class:`NotFound`."""
    account = db.get(VenueAccount, account_id)
    if account is None:
        raise NotFound(f"Venue account {account_id} not found")
    return account


def accounts_for(db: Session, agent_id: int) -> list[VenueAccount]:
    """Return every venue account belonging to an agent."""
    agents_service.require(db, agent_id)
    return list(
        db.scalars(
            select(VenueAccount)
            .where(VenueAccount.agent_id == agent_id)
            .order_by(VenueAccount.id)
        )
    )


def link_account(
    db: Session,
    *,
    agent_id: int,
    venue: str,
    environment: str,
    label: str = "",
    wallet_address: str | None = None,
    secret: str | None = None,
) -> VenueAccount:
    """Give an agent an account on a venue.

    The secret, if supplied, is encrypted before it is written and is never
    readable back out through the API.

    Raises:
        Conflict: If the agent already has an account on this venue+environment.
        InvalidAction: If the pairing is not allowed, or a live venue was asked
            for without the credentials it needs.
        NotFound: If the agent does not exist.
    """
    agents_service.require(db, agent_id)
    env = registry.parse_environment(environment)
    registry.validate_pairing(venue, env)

    existing = db.scalar(
        select(VenueAccount).where(
            VenueAccount.agent_id == agent_id,
            VenueAccount.venue == venue,
            VenueAccount.environment == env.value,
        )
    )
    if existing is not None:
        raise Conflict(
            f"Agent {agent_id} already has a {venue}/{env.value} account "
            f"(id {existing.id})"
        )

    if venue != "paper" and not wallet_address:
        raise InvalidAction(f"A {venue} account needs a wallet address")

    sealed = credentials.seal(secret) if secret else None

    account = VenueAccount(
        agent_id=agent_id,
        venue=venue,
        environment=env.value,
        label=label or f"{venue}:{env.value}",
        wallet_address=wallet_address,
        encrypted_secret=sealed,
        paper_balance=get_settings().paper_starting_balance,
        active=True,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def set_active(db: Session, account_id: int, *, active: bool) -> VenueAccount:
    """Enable or disable one account's trading, without deleting it."""
    account = require_account(db, account_id)
    account.active = active
    db.commit()
    db.refresh(account)
    return account


def unlink_account(db: Session, account_id: int) -> None:
    """Delete an account and the credential stored with it."""
    account = require_account(db, account_id)
    db.delete(account)
    db.commit()


# --- Reads ---------------------------------------------------------------


def snapshot(db: Session, account_id: int) -> dict:
    """Return an account's balances and positions as the venue reports them."""
    account = require_account(db, account_id)
    venue = registry.build_venue(db, account)
    state = venue.account_state()
    return {"account": account, "state": state, "venue": venue}


def describe_account(account: VenueAccount, state: AccountState | None = None) -> dict:
    """Shape an account for the API, with no credential material in it."""
    body: dict = {
        "id": account.id,
        "agent_id": account.agent_id,
        "venue": account.venue,
        "environment": account.environment,
        "label": account.label,
        "wallet_address": account.wallet_address,
        "has_credentials": account.has_credentials,
        "active": account.active,
        "realised_loss_today": round(account.realised_pnl_today, 2),
        "is_real_money": Environment(account.environment).is_real_money,
    }
    if state is not None:
        balance = state.balance()
        body |= {
            "equity": float(balance.total),
            "available": float(balance.available),
            "gross_notional": float(state.gross_notional),
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side.value,
                    "size": float(p.size),
                    "entry_price": float(p.entry_price),
                    "mark_price": float(p.mark_price),
                    "leverage": p.leverage,
                    "unrealised_pnl": float(p.unrealised_pnl),
                    "liquidation_price": (
                        float(p.liquidation_price) if p.liquidation_price else None
                    ),
                }
                for p in state.positions
            ],
        }
    return body


def order_history(db: Session, account_id: int, *, limit: int = 50) -> list[VenueOrder]:
    """Return recent order attempts for an account, newest first."""
    require_account(db, account_id)
    return list(
        db.scalars(
            select(VenueOrder)
            .where(VenueOrder.account_id == account_id)
            .order_by(VenueOrder.id.desc())
            .limit(limit)
        )
    )


# --- The one order path --------------------------------------------------


def place_order(
    db: Session,
    *,
    account_id: int,
    symbol: str,
    side: str,
    size: float,
    order_type: str = "market",
    limit_price: float | None = None,
    leverage: int = 1,
    reduce_only: bool = False,
    confirm_real_money: bool = False,
) -> dict:
    """Risk-check an order, send it, and record what happened.

    Args:
        confirm_real_money: Must be true for a mainnet order. Configuration
            alone is never taken as consent to spend real money.

    Returns:
        A dict describing the outcome, including the refusing rule when a risk
        check stopped the order.

    Raises:
        RiskViolation: If a risk rule refuses the order. The refusal is written
            to the audit trail before it is raised.
        NotFound: If the account does not exist.
        InvalidAction: If the venue cannot be built or the order is malformed.
    """
    account = require_account(db, account_id)
    venue = registry.build_venue(db, account)

    request = OrderRequest(
        symbol=symbol.upper(),
        side=_parse_side(side),
        size=Decimal(str(size)),
        order_type=_parse_order_type(order_type),
        limit_price=Decimal(str(limit_price)) if limit_price is not None else None,
        leverage=leverage,
        reduce_only=reduce_only,
    )

    market_data = _market_data_for(venue)
    instrument = market_data.instrument(request.symbol)
    reference_price = (
        request.limit_price
        if request.order_type is OrderType.LIMIT and request.limit_price
        else market_data.quote(request.symbol).mid
    )

    state = venue.account_state()
    settings = get_settings()

    try:
        check_order(
            request,
            account=state,
            instrument=instrument,
            limits=limits_from(settings),
            reference_price=reference_price,
            realised_loss_today=_loss_today(account),
            confirm_real_money=confirm_real_money,
        )
    except RiskViolation as violation:
        _audit(
            db,
            account,
            request,
            price=reference_price,
            status="refused",
            reason=f"{violation.rule}: {violation}",
        )
        db.commit()
        raise

    result = venue.place_order(request)
    _audit(
        db,
        account,
        request,
        price=result.average_price or reference_price,
        status="filled" if result.accepted else "rejected",
        reason=result.reason,
        venue_order_id=result.order_id,
    )
    db.commit()
    db.refresh(account)

    return _describe_result(account, result, reference_price)


def close_position(db: Session, *, account_id: int, symbol: str) -> dict:
    """Flatten a position, recording the attempt.

    A closing order is reduce-only, so it passes the exposure and margin checks
    by construction — but it still goes through the kill switch, which is the
    one control that must be able to stop everything.
    """
    account = require_account(db, account_id)
    venue = registry.build_venue(db, account)

    settings = get_settings()
    if not settings.trading_enabled:
        raise RiskViolation(
            "trading_disabled", "Trading is disabled by the kill switch"
        )

    result = venue.close_position(symbol.upper())
    request = OrderRequest(
        symbol=symbol.upper(),
        side=result.side,
        size=result.filled_size or Decimal(0),
        reduce_only=True,
    )
    _audit(
        db,
        account,
        request,
        price=result.average_price,
        status="filled" if result.accepted else "rejected",
        reason=result.reason,
        venue_order_id=result.order_id,
    )
    db.commit()
    db.refresh(account)
    return _describe_result(account, result, result.average_price)


# --- Internals -----------------------------------------------------------


def _parse_side(value: str) -> Side:
    """Return the :class:`Side` named by ``value``."""
    try:
        return Side(value.lower())
    except ValueError as exc:
        raise InvalidAction(f"Side must be 'buy' or 'sell', got '{value}'") from exc


def _parse_order_type(value: str) -> OrderType:
    """Return the :class:`OrderType` named by ``value``."""
    try:
        return OrderType(value.lower())
    except ValueError as exc:
        raise InvalidAction(
            f"Order type must be 'market' or 'limit', got '{value}'"
        ) from exc


def _market_data_for(venue: ExecutionVenue):
    """Return the market data feed matching a venue."""
    attached = getattr(venue, "market_data", None)
    if attached is not None:
        return attached
    return registry.build_market_data(venue.name, venue.environment)


def _loss_today(account: VenueAccount) -> Decimal:
    """Return today's realised loss, resetting the counter on a new day."""
    today = datetime.now(UTC).date().isoformat()
    if account.pnl_day != today:
        return Decimal(0)
    return Decimal(str(account.realised_pnl_today))


def _audit(
    db: Session,
    account: VenueAccount,
    request: OrderRequest,
    *,
    price: Decimal,
    status: str,
    reason: str | None = None,
    venue_order_id: str | None = None,
) -> VenueOrder:
    """Write one row describing an order attempt."""
    row = VenueOrder(
        account_id=account.id,
        symbol=request.symbol,
        side=request.side.value,
        size=float(request.size),
        price=float(price or 0),
        leverage=request.leverage,
        reduce_only=request.reduce_only,
        environment=account.environment,
        status=status,
        reason=reason,
        venue_order_id=venue_order_id,
    )
    db.add(row)
    db.flush()
    return row


def _describe_result(
    account: VenueAccount, result: OrderResult, reference_price: Decimal
) -> dict:
    """Shape an order outcome for the API."""
    return {
        "account_id": account.id,
        "accepted": result.accepted,
        "symbol": result.symbol,
        "side": result.side.value,
        "filled_size": float(result.filled_size),
        "average_price": float(result.average_price or reference_price),
        "notional": float(result.notional),
        "environment": result.environment.value,
        "order_id": result.order_id,
        "reason": result.reason,
        "is_real_money": result.environment.is_real_money,
    }
