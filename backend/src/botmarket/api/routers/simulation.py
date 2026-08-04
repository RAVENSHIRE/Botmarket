"""Simulation control: advance the world, or read it without changing it."""

from __future__ import annotations

from fastapi import APIRouter

from botmarket.api.deps import DbSession
from botmarket.api.schemas import SimulationState, TickResult
from botmarket.services import simulation as simulation_service

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/tick", response_model=TickResult)
def tick(db: DbSession):
    """Advance the simulation one tick and return what happened."""
    return simulation_service.run_tick(db)


@router.get("/state", response_model=SimulationState)
def state(db: DbSession):
    """Return the current world snapshot without advancing it."""
    return simulation_service.state(db)
