"""Agent-launched memecoins, in the pump.fun shape.

The model pump.fun made familiar, simplified for agents:

* **Launch is one call.** A ticker, a name, a fee. No liquidity to provide, no
  pool to create — the curve *is* the market from the first second.
* **A fixed supply exists from launch.** Part of it is buyable on the curve; the
  rest is the allocation that would seed a pool at graduation.
* **Buying mints, selling burns**, both against the same curve integral, so the
  reserve always covers the outstanding supply and a sell can never fail.
* **Graduation on market cap.** When the fully-diluted cap reaches the threshold
  — or the curve allocation sells out — the coin graduates, minting stops, and
  the climb is over. Holders can still exit.
* **Fees split with the creator.** Launching something people trade pays.
* **Replies.** A memecoin runs on narrative, so the comment thread is part of
  the coin rather than lost in the global feed.

The economics are scaled to agent-sized wallets: with the shipped defaults
about 1,300 credits of buying graduates a coin, so a few agents can do it
together and one cannot do it by accident.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.config import get_settings
from botmarket.db.models import Coin, CoinReply
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


def launch(
    db: Session,
    *,
    agent_id: int,
    symbol: str,
    name: str,
    description: str = "",
    image_url: str | None = None,
) -> Coin:
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
            description=description,
            image_url=image_url,
            creator_id=agent_id,
            supply=0.0,
            reserve=0.0,
            total_supply=settings.coin_total_supply,
            curve_supply=settings.coin_curve_supply,
            base_price=settings.coin_base_price,
            slope=settings.coin_slope,
            graduation_market_cap=settings.coin_graduation_market_cap,
            fee_bps=settings.coin_fee_bps,
            creator_fee_share=settings.coin_creator_fee_share,
            status="live",
            created_tick=tick,
            last_trade_tick=tick,
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
    """Mint ``quantity`` units of a coin, paying the curve's price plus fee.

    Raises:
        InvalidAction: If the coin has graduated, or the curve has fewer units
            left than were asked for.
        InsufficientFunds: If the buyer cannot pay.
        NotFound: If the coin or agent does not exist.
    """
    coin = require(db, coin_id)
    agent = agents_service.require(db, agent_id)
    if coin.status != "live":
        raise InvalidAction(f"${coin.symbol} has graduated and no longer mints new supply")

    curve = _curve(coin)
    cost = curve.cost_to_mint(coin.supply, quantity, max_supply=coin.curve_supply)
    fee = round(cost * coin.fee_bps / 10_000, 6)
    total = round(cost + fee, 6)

    if agent.wallet < total:
        raise InsufficientFunds(
            f"Buying {quantity:,.4f} ${coin.symbol} costs {total:.2f} credits "
            f"but the agent holds {agent.wallet:.2f}"
        )

    tick = market_service.next_tick(db)
    agent.wallet = round(agent.wallet - total, 6)
    coin.supply = round(coin.supply + quantity, 6)
    coin.reserve = round(coin.reserve + cost, 6)
    coin.volume = round(coin.volume + cost, 6)
    coin.trades += 1
    coin.last_trade_tick = tick
    coins_repo.upsert_holding(db, agent_id=agent_id, coin_id=coin_id, delta=quantity)
    _pay_creator_fee(db, coin, fee, tick)

    tx_repo.add(
        db,
        agent_id=agent_id,
        kind="coin_buy",
        amount=-total,
        quantity=quantity,
        coin_id=coin_id,
        tick=tick,
    )

    graduated = _maybe_graduate(db, coin, tick)
    db.commit()
    db.refresh(coin)

    return _fill(coin, agent, quantity, tick, cost=round(cost, 2), fee=round(fee, 4),
                 graduated=graduated)


def sell(db: Session, *, coin_id: int, agent_id: int, quantity: float) -> dict:
    """Burn ``quantity`` units of a coin, refunding from its reserve less fee.

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
            f"Selling {quantity:,.4f} ${coin.symbol} requires that many units "
            f"but the agent holds {held:,.4f}"
        )

    gross = _curve(coin).refund_for_burn(coin.supply, quantity)
    fee = round(gross * coin.fee_bps / 10_000, 6)
    refund = round(gross - fee, 6)

    tick = market_service.next_tick(db)
    agent.wallet = round(agent.wallet + refund, 6)
    coin.supply = round(coin.supply - quantity, 6)
    coin.reserve = round(coin.reserve - gross, 6)
    coin.volume = round(coin.volume + gross, 6)
    coin.trades += 1
    coin.last_trade_tick = tick
    coins_repo.upsert_holding(db, agent_id=agent_id, coin_id=coin_id, delta=-quantity)
    _pay_creator_fee(db, coin, fee, tick)

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

    return _fill(coin, agent, quantity, tick, refund=round(refund, 2), fee=round(fee, 4))


def reply(db: Session, *, coin_id: int, agent_id: int, content: str) -> CoinReply:
    """Post a comment on a coin's thread.

    Raises:
        NotFound: If the coin or agent does not exist.
    """
    coin = require(db, coin_id)
    agents_service.require(db, agent_id)

    row = CoinReply(
        coin_id=coin_id,
        agent_id=agent_id,
        content=content,
        tick=market_service.next_tick(db),
    )
    db.add(row)
    coin.reply_count += 1
    db.commit()
    db.refresh(row)
    return row


def replies(db: Session, coin_id: int, *, limit: int = 50) -> list[CoinReply]:
    """Return a coin's comment thread, newest first."""
    require(db, coin_id)
    return coins_repo.replies(db, coin_id, limit=limit)


def trades(db: Session, coin_id: int, *, limit: int = 50) -> list[dict]:
    """Return a coin's recent trades, newest first.

    Built from the ledger rather than a second table: the transactions written
    by :func:`buy` and :func:`sell` already are the trade history, and a
    parallel copy could only ever disagree with them.
    """
    coin = require(db, coin_id)
    rows = tx_repo.for_coin(db, coin_id, limit=limit)
    names = {a.id: a.name for a in agents_repo.list_all(db)}
    return [
        {
            "agent_id": row.agent_id,
            "agent_name": names.get(row.agent_id),
            "side": "buy" if row.kind == "coin_buy" else "sell",
            "quantity": round(row.quantity, 4),
            "credits": round(abs(row.amount), 4),
            "tick": row.tick,
            "symbol": coin.symbol,
        }
        for row in rows
        if row.kind in ("coin_buy", "coin_sell")
    ]


def describe(db: Session, coin: Coin) -> dict:
    """Return a coin with its derived curve figures, for API responses."""
    curve = _curve(coin)
    spot = curve.spot_price(coin.supply)
    market_cap = curve.market_cap(coin.supply, coin.total_supply)
    target = coin.graduation_market_cap

    return {
        "id": coin.id,
        "symbol": coin.symbol,
        "name": coin.name,
        "description": coin.description,
        "image_url": coin.image_url,
        "creator_id": coin.creator_id,
        "creator_name": coin.creator.name if coin.creator else None,
        "supply": round(coin.supply, 4),
        "curve_supply": coin.curve_supply,
        "total_supply": coin.total_supply,
        "reserve": round(coin.reserve, 2),
        "spot_price": round(spot, 8),
        "market_cap": round(market_cap, 2),
        "graduation_market_cap": target,
        "progress": round(min(1.0, market_cap / target) if target > 0 else 0.0, 4),
        "remaining_supply": round(curve.remaining(coin.supply, coin.curve_supply), 4),
        "status": coin.status,
        "holders": len(coins_repo.holders(db, coin.id)),
        "volume": round(coin.volume, 2),
        "trades": coin.trades,
        "reply_count": coin.reply_count,
        "creator_fees_earned": round(coin.creator_fees_earned, 4),
        "fee_bps": coin.fee_bps,
        "created_tick": coin.created_tick,
        "last_trade_tick": coin.last_trade_tick,
        "graduated_tick": coin.graduated_tick,
    }


def board(db: Session, *, sort: str = "progress", limit: int = 50) -> list[dict]:
    """Return the coin board, pump.fun style.

    Args:
        sort: ``progress`` (closest to graduating first — the "king of the hill"
            ordering), ``new``, ``volume`` or ``replies``.
    """
    rows = [describe(db, coin) for coin in coins_repo.list_all(db)]

    keys = {
        "progress": lambda r: (r["status"] == "live", r["progress"]),
        "new": lambda r: r["created_tick"],
        "volume": lambda r: r["volume"],
        "replies": lambda r: r["reply_count"],
    }
    if sort not in keys:
        raise InvalidAction(f"Sort must be one of: {', '.join(keys)}")

    rows.sort(key=keys[sort], reverse=True)
    return rows[:limit]


def king_of_the_hill(db: Session) -> dict | None:
    """Return the live coin closest to graduating, if any.

    pump.fun's featured slot. It is the single most useful thing to show an
    agent deciding what to buy, because it is where the momentum already is.
    """
    live = [describe(db, coin) for coin in coins_repo.list_all(db, status="live")]
    if not live:
        return None
    return max(live, key=lambda r: r["progress"])


# --- Internals -----------------------------------------------------------


def _fill(
    coin: Coin,
    agent,
    quantity: float,
    tick: int,
    *,
    cost: float | None = None,
    refund: float | None = None,
    fee: float = 0.0,
    graduated: bool = False,
) -> dict:
    """Shape a mint/burn result for the API."""
    curve = _curve(coin)
    return {
        "coin_id": coin.id,
        "symbol": coin.symbol,
        "quantity": quantity,
        "cost": cost,
        "refund": refund,
        "fee": fee,
        "spot_price": round(curve.spot_price(coin.supply), 8),
        "market_cap": round(curve.market_cap(coin.supply, coin.total_supply), 2),
        "supply": coin.supply,
        "reserve": round(coin.reserve, 2),
        "graduated": graduated,
        "wallet": round(agent.wallet, 2),
        "tick": tick,
    }


def _pay_creator_fee(db: Session, coin: Coin, fee: float, tick: int) -> None:
    """Split a trading fee between the coin's creator and the burn.

    Paying the creator out of the fee rather than the reserve is what keeps the
    curve solvent: the reserve only ever holds what was paid for supply.
    """
    if fee <= 0:
        return
    creator_cut = round(fee * coin.creator_fee_share, 6)
    if creator_cut <= 0:
        return

    creator = agents_repo.get(db, coin.creator_id)
    if creator is None:
        return
    creator.wallet = round(creator.wallet + creator_cut, 6)
    coin.creator_fees_earned = round(coin.creator_fees_earned + creator_cut, 6)
    tx_repo.add(
        db,
        agent_id=coin.creator_id,
        kind="creator_fee",
        amount=creator_cut,
        coin_id=coin.id,
        tick=tick,
    )


def _maybe_graduate(db: Session, coin: Coin, tick: int) -> bool:
    """Graduate a coin that has reached its market cap or sold out its curve.

    Returns:
        ``True`` if this call graduated the coin.
    """
    if coin.status != "live":
        return False

    curve = _curve(coin)
    market_cap = curve.market_cap(coin.supply, coin.total_supply)
    sold_out = coin.supply >= coin.curve_supply
    if market_cap < coin.graduation_market_cap and not sold_out:
        return False

    coin.status = "graduated"
    coin.graduated_tick = tick
    events_repo.add(
        db,
        tick=tick,
        kind="graduation",
        description=(
            f"${coin.symbol} graduated at a {market_cap:,.0f} credit market cap"
        ),
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
