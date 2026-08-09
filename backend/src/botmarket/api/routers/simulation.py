"""Simulation control: advance the world, or read it without changing it."""

from __future__ import annotations

from fastapi import APIRouter

from botmarket.api.deps import CallerAgent, DbSession
from botmarket.api.schemas import SimulationState, TickResult
from botmarket.services import simulation as simulation_service

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/tick", response_model=TickResult)
def tick(db: DbSession, caller: CallerAgent):  # noqa: ARG001 - identity is the point
    """Advance the simulation one tick and return what happened.

    Any registered agent may advance the world, but it takes a key: a tick
    moves every wallet in the economy, so it is not something an anonymous
    caller should be able to trigger in a loop.
    """
    return simulation_service.run_tick(db)


@router.get("/state", response_model=SimulationState)
def state(db: DbSession):
    """Return the current world snapshot without advancing it."""
    return simulation_service.state(db)
