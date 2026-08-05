"""Translation of domain errors into HTTP responses.

Registering these handlers is what lets the service layer raise plain domain
exceptions: routers never need try/except, and every failure mode gets one
consistent status code and body shape across the whole API.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from botmarket.domain.errors import (
    Conflict,
    DomainError,
    InsufficientFunds,
    InvalidAction,
    NotFound,
)
from botmarket.domain.risk import RiskViolation

# Most specific first — the first matching class wins.
STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (NotFound, status.HTTP_404_NOT_FOUND),
    (Conflict, status.HTTP_409_CONFLICT),
    (InsufficientFunds, status.HTTP_402_PAYMENT_REQUIRED),
    (InvalidAction, status.HTTP_422_UNPROCESSABLE_ENTITY),
]


def status_for(exc: DomainError) -> int:
    """Return the HTTP status that represents ``exc``."""
    for error_type, code in STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return code
    return status.HTTP_400_BAD_REQUEST


def install(app: FastAPI) -> None:
    """Register the domain-error handlers on ``app``."""

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=status_for(exc),
            content={"detail": str(exc), "error": type(exc).__name__},
        )

    @app.exception_handler(RiskViolation)
    async def _handle_risk_violation(_: Request, exc: RiskViolation) -> JSONResponse:
        """Report a pre-trade refusal, naming the rule that stopped it.

        The rule is part of the contract rather than prose in the message: an
        agent deciding whether to retry smaller or stop entirely needs to tell
        ``above_max_order_value`` from ``trading_disabled``.
        """
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": str(exc),
                "error": "RiskViolation",
                "rule": exc.rule,
            },
        )
