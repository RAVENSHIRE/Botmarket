"""HTTP routers, grouped by resource, combined into one application router."""

from fastapi import APIRouter

from botmarket.api.routers import (
    agents,
    coins,
    governance,
    market,
    simulation,
    social,
    system,
)

router = APIRouter()

for module in (system, agents, social, market, coins, governance, simulation):
    router.include_router(module.router)

__all__ = ["router"]
