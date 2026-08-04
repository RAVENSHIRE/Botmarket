"""Tests for the HTTP API endpoints."""

from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_agent_crud_flow(client):
    # Empty to start.
    assert client.get("/agents").json() == []

    created = client.post("/agents", json={"name": "Nova", "agent_type": "trader"})
    assert created.status_code == 201
    agent_id = created.json()["id"]

    # Duplicate name rejected.
    dup = client.post("/agents", json={"name": "Nova", "agent_type": "trader"})
    assert dup.status_code == 409

    # Fetchable by id.
    fetched = client.get(f"/agents/{agent_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Nova"

    # 404 for unknown id.
    assert client.get("/agents/9999").status_code == 404


def test_invalid_agent_type_rejected(client):
    resp = client.post("/agents", json={"name": "X", "agent_type": "wizard"})
    assert resp.status_code == 422


def test_tick_and_feed(client):
    for name, kind in [("T", "trader"), ("M", "meme"), ("A", "analyst")]:
        client.post("/agents", json={"name": name, "agent_type": kind})

    tick = client.post("/simulation/tick")
    assert tick.status_code == 200
    body = tick.json()
    assert body["tick"] == 1
    assert isinstance(body["leaderboard"], list)

    feed = client.get("/feed")
    assert feed.status_code == 200
    assert len(feed.json()) >= 1


def test_leaderboard_endpoint(client):
    client.post("/agents", json={"name": "Solo", "agent_type": "analyst"})
    client.post("/simulation/tick")
    board = client.get("/leaderboard")
    assert board.status_code == 200
    assert board.json()[0]["name"] == "Solo"
