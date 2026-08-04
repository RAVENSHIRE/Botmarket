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


def test_agent_can_post_to_feed(client):
    created = client.post("/agents", json={"name": "Poster", "agent_type": "meme"})
    agent_id = created.json()["id"]

    post = client.post(
        f"/agents/{agent_id}/posts",
        json={"content": "gm from an OpenClaw agent", "kind": "meme"},
    )
    assert post.status_code == 201
    assert post.json()["author_id"] == agent_id

    feed = client.get("/feed").json()
    assert any(p["content"] == "gm from an OpenClaw agent" for p in feed)


def test_post_by_unknown_agent_404(client):
    resp = client.post("/agents/9999/posts", json={"content": "hi"})
    assert resp.status_code == 404


def test_heartbeat_document(client):
    client.post("/agents", json={"name": "Ada", "agent_type": "trader"})
    resp = client.get("/heartbeat")
    assert resp.status_code == 200
    assert "BOTMARKET heartbeat" in resp.text
    assert "Actions available now" in resp.text
