"""Pre-trade risk checks.

An autonomous agent placing real perpetual orders is exactly the situation where
a bug costs money, so every order passes through :func:`check_order` before any
venue sees it. The checks are pure functions over an :class:`OrderRequest` and an
:class:`AccountState`: no I/O, no clock, no hidden state, which is what makes
them exhaustively testable.

The ordering of the checks is deliberate — the cheapest and most categorical
refusals come first, so a disabled kill switch or an unconfirmed mainnet order
is rejected before anything looks at balances.

Two rules are worth calling out because they are the ones that stop a runaway
agent rather than a malformed one:

* **Mainnet requires explicit confirmation.** A real-money order is refused
  unless the caller sets ``confirm_real_money``. Nothing infers consent from
  configuration alone — a misplaced env var must not be sufficient to move real
  funds.
* **The daily loss cap is a hard stop.** Once realised losses for the day exceed
  the cap, only position-reducing orders are allowed through.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from botmarket.domain.venue import (
    AccountState,
    Environment,
    Instrument,
    OrderRequest,
    Side,
)


class RiskViolation(Exception):
    """An order was refused before it reached the venue.

    Attributes:
        rule: Machine-readable identifier of the rule that refused the order.
    """

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule


@dataclass(frozen=True)
class RiskLimits:
    """The envelope an agent is allowed to trade inside.

    Attributes:
        trading_enabled: Global kill switch. When false nothing gets through,
            including position-reducing orders — use it to stop the world.
        max_leverage: Highest leverage an order may request.
        min_order_value: Orders worth less than this are refused as dust.
        max_order_value: Largest notional for a single order.
        max_position_value: Largest notional for one symbol after the order.
        max_gross_notional: Largest summed notional across every position.
        max_daily_loss: Realised loss for the day past which only reducing
            orders are permitted. Zero disables the cap.
        allow_mainnet: Whether real-money orders may be placed at all.
    """

    trading_enabled: bool = True
    max_leverage: int = 5
    min_order_value: Decimal = Decimal("10")
    max_order_value: Decimal = Decimal("1000")
    max_position_value: Decimal = Decimal("5000")
    max_gross_notional: Decimal = Decimal("25000")
    max_daily_loss: Decimal = Decimal("500")
    allow_mainnet: bool = False


def check_order(
    request: OrderRequest,
    *,
    account: AccountState,
    instrument: Instrument,
    limits: RiskLimits,
    reference_price: Decimal,
    realised_loss_today: Decimal = Decimal(0),
    confirm_real_money: bool = False,
) -> None:
    """Raise :class:`RiskViolation` if ``request`` may not be placed.

    Args:
        request: The order an agent wants to place.
        account: Balances and positions as the venue currently reports them.
        instrument: Venue trading rules for the symbol.
        limits: The envelope to enforce.
        reference_price: Price used to value the order — the quote mid for a
            market order, the limit price for a limit order.
        realised_loss_today: Losses already booked today, as a positive number.
        confirm_real_money: Explicit operator consent for a mainnet order.

    Raises:
        RiskViolation: If any rule refuses the order.
    """
    _check_kill_switch(limits)
    _check_environment(account.environment, limits, confirm_real_money)
    _check_shape(request, reference_price)
    _check_leverage(request, instrument, limits)
    _check_daily_loss(request, limits, realised_loss_today)
    _check_notional(request, instrument, limits, reference_price)
    _check_exposure(request, account, limits, reference_price)
    _check_margin(request, account, reference_price)


# --- Individual rules ----------------------------------------------------


def _check_kill_switch(limits: RiskLimits) -> None:
    """Refuse everything while trading is switched off."""
    if not limits.trading_enabled:
        raise RiskViolation(
            "trading_disabled",
            "Trading is disabled by the kill switch; no orders are accepted",
        )


def _check_environment(
    environment: Environment, limits: RiskLimits, confirm_real_money: bool
) -> None:
    """Gate real-money trading behind configuration *and* explicit consent."""
    if not environment.is_real_money:
        return
    if not limits.allow_mainnet:
        raise RiskViolation(
            "mainnet_not_allowed",
            "This deployment is not configured for mainnet trading",
        )
    if not confirm_real_money:
        raise RiskViolation(
            "confirmation_required",
            "Mainnet orders require explicit confirmation of real-money intent",
        )


def _check_shape(request: OrderRequest, reference_price: Decimal) -> None:
    """Reject orders that are malformed before pricing them."""
    if request.size <= 0:
        raise RiskViolation("invalid_size", "Order size must be greater than zero")
    if reference_price <= 0:
        raise RiskViolation("invalid_price", "Reference price must be greater than zero")


def _check_leverage(request: OrderRequest, instrument: Instrument, limits: RiskLimits) -> None:
    """Keep leverage inside both the venue's and the operator's ceiling."""
    if request.leverage < 1:
        raise RiskViolation("invalid_leverage", "Leverage must be at least 1")
    ceiling = min(limits.max_leverage, instrument.max_leverage)
    if request.leverage > ceiling:
        raise RiskViolation(
            "leverage_exceeded",
            f"Leverage {request.leverage}x exceeds the {ceiling}x ceiling "
            f"for {request.symbol}",
        )


def _check_daily_loss(
    request: OrderRequest, limits: RiskLimits, realised_loss_today: Decimal
) -> None:
    """Once the day's loss cap is hit, only let the agent get smaller."""
    if limits.max_daily_loss <= 0 or realised_loss_today < limits.max_daily_loss:
        return
    if request.reduce_only:
        return
    raise RiskViolation(
        "daily_loss_cap",
        f"Daily loss of {realised_loss_today} has reached the "
        f"{limits.max_daily_loss} cap; only reducing orders are allowed",
    )


def _check_notional(
    request: OrderRequest,
    instrument: Instrument,
    limits: RiskLimits,
    reference_price: Decimal,
) -> None:
    """Hold a single order between the dust floor and the size ceiling."""
    notional = request.notional_at(reference_price)
    floor = max(limits.min_order_value, instrument.min_notional)
    if notional < floor:
        raise RiskViolation(
            "below_min_notional",
            f"Order value {notional:.2f} is below the {floor} minimum",
        )
    if notional > limits.max_order_value:
        raise RiskViolation(
            "above_max_order_value",
            f"Order value {notional:.2f} exceeds the "
            f"{limits.max_order_value} per-order limit",
        )


def _check_exposure(
    request: OrderRequest,
    account: AccountState,
    limits: RiskLimits,
    reference_price: Decimal,
) -> None:
    """Bound exposure per symbol and across the whole account.

    A reducing order can never breach an exposure ceiling, so it skips both
    checks — refusing one would trap an agent in a position it is trying to
    get out of.
    """
    if request.reduce_only:
        return

    order_notional = request.notional_at(reference_price)
    existing = account.position(request.symbol)

    # Adding to a position grows exposure; opposing it nets down against it.
    if existing is not None and existing.side is not request.side:
        projected_symbol = abs(existing.notional - order_notional)
    else:
        projected_symbol = (existing.notional if existing else Decimal(0)) + order_notional

    if projected_symbol > limits.max_position_value:
        raise RiskViolation(
            "position_limit",
            f"Position in {request.symbol} would reach {projected_symbol:.2f}, "
            f"over the {limits.max_position_value} limit",
        )

    projected_gross = account.gross_notional + order_notional
    if projected_gross > limits.max_gross_notional:
        raise RiskViolation(
            "gross_exposure",
            f"Gross exposure would reach {projected_gross:.2f}, over the "
            f"{limits.max_gross_notional} limit",
        )


def _check_margin(
    request: OrderRequest, account: AccountState, reference_price: Decimal
) -> None:
    """Refuse an order the account cannot post margin for."""
    if request.reduce_only:
        return
    required = request.notional_at(reference_price) / Decimal(request.leverage)
    available = account.balance().available
    if required > available:
        raise RiskViolation(
            "insufficient_margin",
            f"Order needs {required:.2f} margin but only {available:.2f} is available",
        )


def clamp_to_limits(
    request: OrderRequest,
    *,
    instrument: Instrument,
    limits: RiskLimits,
    reference_price: Decimal,
) -> OrderRequest:
    """Return ``request`` shrunk to the largest size the limits would allow.

    This is a convenience for callers that would rather trade smaller than not
    at all. It only ever reduces size, and the result is still not trusted:
    :func:`check_order` must be run on it, because clamping cannot fix a
    leverage breach, an empty account, or a tripped kill switch.
    """
    if reference_price <= 0 or request.size <= 0:
        return request

    ceiling = min(limits.max_order_value, limits.max_position_value)
    max_size = ceiling / reference_price
    if request.size <= max_size:
        return request

    return OrderRequest(
        symbol=request.symbol,
        side=request.side,
        size=instrument.round_size(max_size),
        order_type=request.order_type,
        limit_price=request.limit_price,
        leverage=request.leverage,
        reduce_only=request.reduce_only,
        client_id=request.client_id,
    )


def close_request(position_side: Side, size: Decimal, symbol: str) -> OrderRequest:
    """Build the reducing order that flattens a position."""
    return OrderRequest(
        symbol=symbol,
        side=position_side.opposite,
        size=abs(size),
        reduce_only=True,
    )
