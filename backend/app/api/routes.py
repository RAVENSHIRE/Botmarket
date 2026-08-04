"""HTTP API routes.

Exposes the MVP endpoints:

    GET  /health              - service health.
    GET  /agents              - list agents.
    POST /agents              - register a new agent.
    GET  /agents/{id}         - fetch a single agent.
    GET  /feed                - recent social posts.
    GET  /leaderboard         - ranked agents.
    POST /simulation/tick     - advance the simulation one tick.
    GET  /simulation/state    - current simulation snapshot.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Agent
from app.schemas import (
    AgentCreate,
    AgentOut,
    HealthOut,
    PostOut,
    TickResult,
)
from app.simulation.engine import SimulationEngine
from app.social.posts import get_feed

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["system"])
def health() -> HealthOut:
    """Return service liveness information."""
    settings = get_settings()
    return HealthOut(status="ok", app=settings.app_name, environment=settings.environment)


@router.get("/agents", response_model=list[AgentOut], tags=["agents"])
def list_agents(db: Session = Depends(get_db)) -> list[Agent]:
    """List all registered agents."""
    return list(db.scalars(select(Agent).order_by(Agent.id)))


@router.post(
    "/agents",
    response_model=AgentOut,
    status_code=status.HTTP_201_CREATED,
    tags=["agents"],
)
def create_agent_endpoint(payload: AgentCreate, db: Session = Depends(get_db)) -> Agent:
    """Register a new agent of the given type."""
    if db.scalar(select(Agent).where(Agent.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Agent name already exists")
    engine = SimulationEngine(db)
    row = engine.register_agent(
        agent_type=payload.agent_type, name=payload.name, wallet=payload.wallet
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/agents/{agent_id}", response_model=AgentOut, tags=["agents"])
def get_agent(agent_id: int, db: Session = Depends(get_db)) -> Agent:
    """Fetch a single agent by id."""
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    return agent


@router.get("/feed", response_model=list[PostOut], tags=["social"])
def feed(limit: int = 50, db: Session = Depends(get_db)):
    """Return the most recent social posts."""
    return get_feed(db, limit=limit)


@router.get("/leaderboard", tags=["simulation"])
def leaderboard(db: Session = Depends(get_db)) -> list[dict]:
    """Return the agent leaderboard."""
    return SimulationEngine(db).leaderboard()


@router.post("/simulation/tick", response_model=TickResult, tags=["simulation"])
def simulation_tick(db: Session = Depends(get_db)) -> dict:
    """Advance the simulation by one tick and return a summary."""
    return SimulationEngine(db).run_tick()


@router.get("/simulation/state", tags=["simulation"])
def simulation_state(db: Session = Depends(get_db)) -> dict:
    """Return the current simulation state snapshot."""
    return SimulationEngine(db).get_state()
