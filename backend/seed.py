"""Seed the database with a starter roster of agents.

Run from the repository root::

    python backend/seed.py

Idempotent: agents whose names already exist are skipped.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a plain script (``python backend/seed.py``).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Agent
from app.simulation.engine import SimulationEngine

STARTER_ROSTER = [
    ("trader", "Satoshi"),
    ("trader", "Ada"),
    ("meme", "Pepe"),
    ("meme", "Doge"),
    ("analyst", "Vitalik"),
    ("analyst", "Turing"),
]


def main() -> None:
    """Create the starter agents if they are not already present."""
    init_db()
    db = SessionLocal()
    engine = SimulationEngine(db)
    created = 0
    try:
        for agent_type, name in STARTER_ROSTER:
            if db.scalar(select(Agent).where(Agent.name == name)):
                continue
            engine.register_agent(agent_type=agent_type, name=name)
            created += 1
        db.commit()
    finally:
        db.close()
    print(f"Seed complete. Created {created} new agent(s).")


if __name__ == "__main__":
    main()
