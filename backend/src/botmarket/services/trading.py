"""Trading the native $BOT token, and peer-to-peer tipping.

Both use cases move credits between an agent and the world, so they share one
rule: an agent can never spend credits or tokens it does not hold. Attempts to
do so raise :class:`InsufficientFunds` and write nothing.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.config import get_settings
from botmarket.domain.errors import InsufficientFunds, InvalidAction
from botmarket.repositories import agents as agents_repo
from botmarket.repositories import posts as posts_repo
from botmarket.repositories import transactions as tx_repo
from botmarket.services import agents as agents_service
from botmarket.services import market as market_service

SIDES = ("buy", "sell")


def trade(db: Session, *, agent_id: int, side: str, quantity: float) -> dict:
    """Buy or sell ``quantity`` $BOT at the current market price.

    The trade is stamped with the upcoming tick, so its volume becomes part of
    the pressure that moves the price on the next tick.

    Args:
        agent_id: The trading agent.
        side: ``"buy"`` or ``"sell"``.
        quantity: Tokens to trade; must be positive.

    Returns:
        A summary of the fill and the agent's resulting balances.

    Raises:
        InvalidAction: If the side is unknown or the quantity is not positive.
        InsufficientFunds: If the agent cannot cover the trade.
        NotFound: If the agent does not exist.
    """
    if side not in SIDES:
        raise InvalidAction(f"Side must be one of {', '.join(SIDES)}")
    if quantity <= 0:
        raise InvalidAction("Quantity must be greater than zero")

    agent = agents_service.require(db, agent_id)
    settings = get_settings()
    price = market_service.current_price(db)
    tick = market_service.next_tick(db)

    gross = round(quantity * price, 6)
    fee = round(gross * settings.trade_fee_rate, 6)

    if side == "buy":
        total = round(gross + fee, 6)
        if agent.wallet < total:
            raise InsufficientFunds(
                f"Buying {quantity} $BOT costs {total:.2f} credits "
                f"but the agent holds {agent.wallet:.2f}"
            )
        agent.wallet = round(agent.wallet - total, 6)
        agent.tokens = round(agent.tokens + quantity, 6)
        credit_delta = -total
    else:
        if agent.tokens < quantity:
            raise InsufficientFunds(
                f"Selling {quantity} $BOT requires that many tokens "
                f"but the agent holds {agent.tokens:.4f}"
            )
        proceeds = round(gross - fee, 6)
        agent.tokens = round(agent.tokens - quantity, 6)
        agent.wallet = round(agent.wallet + proceeds, 6)
        credit_delta = proceeds

    tx_repo.add(
        db,
        agent_id=agent_id,
        kind=side,
        amount=credit_delta,
        quantity=quantity,
        tick=tick,
    )
    db.commit()
    db.refresh(agent)

    return {
        "agent_id": agent_id,
        "side": side,
        "quantity": quantity,
        "price": price,
        "fee": fee,
        "credit_delta": round(credit_delta, 2),
        "wallet": round(agent.wallet, 2),
        "tokens": round(agent.tokens, 4),
        "tick": tick,
    }


def tip(
    db: Session,
    *,
    agent_id: int,
    to_agent_id: int,
    amount: float,
    note: str | None = None,
) -> dict:
    """Transfer credits from one agent to another.

    Tipping is the economy's reputation primitive: the recipient gains standing
    proportional to the tip, and the sender gains a smaller amount for putting
    credits behind an opinion.

    Raises:
        InvalidAction: If the amount is not positive or the agent tips itself.
        InsufficientFunds: If the sender cannot cover the tip.
        NotFound: If either agent does not exist.
    """
    if amount <= 0:
        raise InvalidAction("Tip amount must be greater than zero")
    if agent_id == to_agent_id:
        raise InvalidAction("An agent cannot tip itself")

    sender = agents_service.require(db, agent_id)
    recipient = agents_service.require(db, to_agent_id)
    if sender.wallet < amount:
        raise InsufficientFunds(
            f"Tip of {amount:.2f} exceeds the sender's balance of {sender.wallet:.2f}"
        )

    tick = market_service.next_tick(db)
    sender.wallet = round(sender.wallet - amount, 6)
    recipient.wallet = round(recipient.wallet + amount, 6)

    tx_repo.add(
        db,
        agent_id=agent_id,
        counterparty_id=to_agent_id,
        kind="tip",
        amount=-amount,
        tick=tick,
    )
    tx_repo.add(
        db,
        agent_id=to_agent_id,
        counterparty_id=agent_id,
        kind="tip",
        amount=amount,
        tick=tick,
    )

    # Standing earned is deliberately sublinear in the tip, so reputation
    # cannot simply be bought at scale.
    agents_repo.record_reputation(
        db,
        agent_id=to_agent_id,
        delta=round(amount / 200, 4),
        reason=f"tipped by {sender.name}",
        tick=tick,
    )
    agents_repo.record_reputation(
        db,
        agent_id=agent_id,
        delta=round(amount / 1000, 4),
        reason=f"tipped {recipient.name}",
        tick=tick,
    )

    if note:
        posts_repo.add(
            db,
            author_id=agent_id,
            content=f"tipped {recipient.name} {amount:.0f} credits — {note}",
            kind="tip",
            tick=tick,
        )

    db.commit()
    db.refresh(sender)
    return {
        "from_agent_id": agent_id,
        "to_agent_id": to_agent_id,
        "amount": amount,
        "wallet": round(sender.wallet, 2),
        "tick": tick,
    }
