"""HTTP routers, grouped by resource, combined into one application router."""

from fastapi import APIRouter

from botmarket.api.routers import (
    agents,
    coins,
    factors,
    governance,
    market,
    simulation,
    social,
    system,
    venues,
)

router = APIRouter()

for module in (
    system,
    agents,
    social,
    market,
    coins,
    governance,
    simulation,
    venues,
    factors,
):
    router.include_router(module.router)

__all__ = ["router"]
