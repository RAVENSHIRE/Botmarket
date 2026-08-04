"""Agent-launched memecoins traded against a bonding curve.

Every coin is its own automated market maker: buying mints new supply and pays
credits into the coin's reserve, selling burns supply and pays credits back
out. Because both sides use the same curve integral, the reserve always covers
the outstanding supply exactly — a coin can never fail to honour a sell.

When a coin's reserve reaches the graduation threshold it stops minting. The
curve is then closed: holders can still exit, but no new supply enters.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.config import get_settings
from botmarket.db.models import Coin
from botmarket.domain.bonding import Curve
from botmarket.domain.errors import Conflict, InsufficientFunds, InvalidAction, NotFound
from botmarket.repositories import agents as agents_repo
from botmarket.repositories import coins as coins_repo
from botmarket.repositories import events as events_repo
from botmarket.repositories import posts as posts_repo
from botmarket.repositories import transactions as tx_repo
from botmarket.services import agents as agents_service
from botmarket.services import market as market_service


def _curve(coin: Coin) -> Curve:
    """Return the bonding curve for a coin."""
    return Curve(base_price=coin.base_price, slope=coin.slope)


def require(db: Session, coin_id: int) -> Coin:
    """Return a coin or raise :class:`NotFound`."""
    coin = coins_repo.get(db, coin_id)
    if coin is None:
        raise NotFound(f"Coin {coin_id} not found")
    return coin


def launch(db: Session, *, agent_id: int, symbol: str, name: str) -> Coin:
    """Launch a new memecoin, burning the launch fee from the creator's wallet.

    Raises:
        Conflict: If the ticker symbol is taken.
        InsufficientFunds: If the creator cannot pay the launch fee.
        NotFound: If the creator does not exist.
    """
    agent = agents_service.require(db, agent_id)
    settings = get_settings()
    symbol = symbol.strip().upper()

    if coins_repo.get_by_symbol(db, symbol) is not None:
        raise Conflict(f"Ticker '{symbol}' is already taken")
    if agent.wallet < settings.coin_launch_fee:
        raise InsufficientFunds(
            f"Launching costs {settings.coin_launch_fee:.0f} credits "
            f"but the agent holds {agent.wallet:.2f}"
        )

    tick = market_service.next_tick(db)
    agent.wallet = round(agent.wallet - settings.coin_launch_fee, 6)

    coin = coins_repo.add(
        db,
        Coin(
            symbol=symbol,
            name=name,
            creator_id=agent_id,
            supply=0.0,
            reserve=0.0,
            base_price=settings.coin_base_price,
            slope=settings.coin_slope,
            status="live",
            created_tick=tick,
        ),
    )
    tx_repo.add(
        db,
        agent_id=agent_id,
        kind="coin_launch",
        amount=-settings.coin_launch_fee,
        coin_id=coin.id,
        tick=tick,
    )
    posts_repo.add(
        db,
        author_id=agent_id,
        content=f"launched ${symbol} — {name}. bonding curve is live.",
        kind="launch",
        tick=tick,
    )
    events_repo.add(
        db,
        tick=tick,
        kind="launch",
        description=f"{agent.name} launched ${symbol}",
        magnitude=0.5,
    )
    db.commit()
    db.refresh(coin)
    return coin


def buy(db: Session, *, coin_id: int, agent_id: int, quantity: float) -> dict:
    """Mint ``quantity`` units of a coin, paying the curve's price.

    Raises:
        InvalidAction: If the quantity is not positive or the coin has graduated.
        InsufficientFunds: If the buyer cannot pay the cost.
        NotFound: If the coin or agent does not exist.
    """
    coin = require(db, coin_id)
    agent = agents_service.require(db, agent_id)
    if coin.status != "live":
        raise InvalidAction(f"${coin.symbol} has graduated and no longer mints new supply")

    cost = _curve(coin).cost_to_mint(coin.supply, quantity)
    if agent.wallet < cost:
        raise InsufficientFunds(
            f"Buying {quantity} ${coin.symbol} costs {cost:.2f} credits "
            f"but the agent holds {agent.wallet:.2f}"
        )

    tick = market_service.next_tick(db)
    agent.wallet = round(agent.wallet - cost, 6)
    coin.supply = round(coin.supply + quantity, 6)
    coin.reserve = round(coin.reserve + cost, 6)
    coins_repo.upsert_holding(db, agent_id=agent_id, coin_id=coin_id, delta=quantity)
    tx_repo.add(
        db,
        agent_id=agent_id,
        kind="coin_buy",
        amount=-cost,
        quantity=quantity,
        coin_id=coin_id,
        tick=tick,
    )

    graduated = _maybe_graduate(db, coin, tick)
    db.commit()
    db.refresh(coin)

    return {
        "coin_id": coin_id,
        "symbol": coin.symbol,
        "quantity": quantity,
        "cost": round(cost, 2),
        "spot_price": round(_curve(coin).spot_price(coin.supply), 4),
        "supply": coin.supply,
        "reserve": round(coin.reserve, 2),
        "graduated": graduated,
        "wallet": round(agent.wallet, 2),
        "tick": tick,
    }


def sell(db: Session, *, coin_id: int, agent_id: int, quantity: float) -> dict:
    """Burn ``quantity`` units of a coin, refunding from its reserve.

    Selling stays available after graduation so holders always have an exit.

    Raises:
        InvalidAction: If the quantity is not positive or exceeds supply.
        InsufficientFunds: If the seller does not hold that many units.
        NotFound: If the coin or agent does not exist.
    """
    coin = require(db, coin_id)
    agent = agents_service.require(db, agent_id)

    holding = coins_repo.get_holding(db, agent_id=agent_id, coin_id=coin_id)
    held = holding.quantity if holding else 0.0
    if held < quantity:
        raise InsufficientFunds(
            f"Selling {quantity} ${coin.symbol} requires that many units "
            f"but the agent holds {held:.4f}"
        )

    refund = _curve(coin).refund_for_burn(coin.supply, quantity)
    tick = market_service.next_tick(db)
    agent.wallet = round(agent.wallet + refund, 6)
    coin.supply = round(coin.supply - quantity, 6)
    coin.reserve = round(coin.reserve - refund, 6)
    coins_repo.upsert_holding(db, agent_id=agent_id, coin_id=coin_id, delta=-quantity)
    tx_repo.add(
        db,
        agent_id=agent_id,
        kind="coin_sell",
        amount=refund,
        quantity=quantity,
        coin_id=coin_id,
        tick=tick,
    )
    db.commit()
    db.refresh(coin)

    return {
        "coin_id": coin_id,
        "symbol": coin.symbol,
        "quantity": quantity,
        "refund": round(refund, 2),
        "spot_price": round(_curve(coin).spot_price(coin.supply), 4),
        "supply": coin.supply,
        "reserve": round(coin.reserve, 2),
        "wallet": round(agent.wallet, 2),
        "tick": tick,
    }


def describe(db: Session, coin: Coin) -> dict:
    """Return a coin with its derived curve figures, for API responses."""
    curve = _curve(coin)
    settings = get_settings()
    return {
        "id": coin.id,
        "symbol": coin.symbol,
        "name": coin.name,
        "creator_id": coin.creator_id,
        "creator_name": coin.creator.name if coin.creator else None,
        "supply": round(coin.supply, 4),
        "reserve": round(coin.reserve, 2),
        "spot_price": round(curve.spot_price(coin.supply), 4),
        "market_cap": curve.market_cap(coin.supply),
        "status": coin.status,
        "graduation_reserve": settings.coin_graduation_reserve,
        "progress": round(
            min(1.0, coin.reserve / settings.coin_graduation_reserve)
            if settings.coin_graduation_reserve > 0
            else 0.0,
            4,
        ),
        "holders": len(coins_repo.holders(db, coin.id)),
        "created_tick": coin.created_tick,
    }


def _maybe_graduate(db: Session, coin: Coin, tick: int) -> bool:
    """Graduate a coin whose reserve has reached the threshold.

    Returns:
        ``True`` if this call graduated the coin.
    """
    settings = get_settings()
    if coin.status != "live" or coin.reserve < settings.coin_graduation_reserve:
        return False

    coin.status = "graduated"
    events_repo.add(
        db,
        tick=tick,
        kind="graduation",
        description=f"${coin.symbol} graduated with a {coin.reserve:.0f} credit reserve",
        magnitude=2.0,
    )
    posts_repo.add(
        db,
        author_id=coin.creator_id,
        content=f"${coin.symbol} just graduated. the curve is closed.",
        kind="launch",
        tick=tick,
    )
    agents_repo.record_reputation(
        db,
        agent_id=coin.creator_id,
        delta=1.0,
        reason=f"${coin.symbol} graduated",
        tick=tick,
    )
    return True
