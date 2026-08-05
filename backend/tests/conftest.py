"""Shared pytest fixtures.

A temporary SQLite database is configured *before* the application package is
imported, so tests never touch a developer's real ``botmarket.db``. Each test
gets a clean schema.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_tmp_db = Path(tempfile.gettempdir()) / "botmarket_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from botmarket.db.session import Base, SessionLocal, engine, init_db  # noqa: E402
from botmarket.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_db():
    """Drop and recreate all tables around every test for isolation."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Provide a database session bound to the test engine."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """Provide a FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_agent(client):
    """Return a factory that registers an agent over the API and returns its id."""

    def _make(name: str, agent_type: str = "trader", wallet: float | None = None) -> int:
        body: dict = {"name": name, "agent_type": agent_type}
        if wallet is not None:
            body["wallet"] = wallet
        resp = client.post("/agents", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    return _make
