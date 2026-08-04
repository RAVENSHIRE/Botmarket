"""Tests for the core HTTP API: health, agents, feed, market and heartbeat."""

from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_root_points_at_the_docs(client):
    assert client.get("/").json()["docs"] == "/docs"


def test_agent_crud_flow(client, make_agent):
    assert client.get("/agents").json() == []

    agent_id = make_agent("Nova")

    # Duplicate name rejected.
    dup = client.post("/agents", json={"name": "Nova", "agent_type": "trader"})
    assert dup.status_code == 409

    fetched = client.get(f"/agents/{agent_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Nova"
    assert fetched.json()["tokens"] == 0

    assert client.get("/agents/9999").status_code == 404


def test_invalid_agent_type_rejected(client):
    resp = client.post("/agents", json={"name": "X", "agent_type": "wizard"})
    assert resp.status_code == 422


def test_tick_and_feed(client, make_agent):
    for name, kind in [("T", "trader"), ("M", "meme"), ("A", "analyst")]:
        make_agent(name, kind)

    tick = client.post("/simulation/tick")
    assert tick.status_code == 200
    body = tick.json()
    assert body["tick"] == 1
    assert isinstance(body["leaderboard"], list)

    feed = client.get("/feed")
    assert feed.status_code == 200
    assert len(feed.json()) >= 1


def test_feed_can_be_filtered_by_kind(client, make_agent):
    agent_id = make_agent("Filterer", "meme")
    client.post(f"/agents/{agent_id}/posts", json={"content": "a meme", "kind": "meme"})
    client.post(f"/agents/{agent_id}/posts", json={"content": "a note", "kind": "post"})

    memes = client.get("/feed", params={"kind": "meme"}).json()
    assert [p["content"] for p in memes] == ["a meme"]


def test_leaderboard_endpoint(client, make_agent):
    make_agent("Solo", "analyst")
    client.post("/simulation/tick")
    board = client.get("/leaderboard")
    assert board.status_code == 200
    assert board.json()[0]["name"] == "Solo"


def test_market_endpoint_tracks_ticks(client, make_agent):
    make_agent("Ticker", "analyst")
    # Before any tick the market reports its opening price and nothing else.
    before = client.get("/market").json()
    assert before["tick"] == 0
    assert before["history"] == [100.0]

    client.post("/simulation/tick")
    after = client.get("/market").json()
    assert after["tick"] == 1
    # One tick, one recorded close.
    assert len(after["history"]) == 1


def test_agent_can_post_to_feed(client, make_agent):
    agent_id = make_agent("Poster", "meme")

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


def test_portfolio_reports_balances_and_activity(client, make_agent):
    agent_id = make_agent("Holder")
    client.post(f"/agents/{agent_id}/trade", json={"side": "buy", "quantity": 2})

    portfolio = client.get(f"/agents/{agent_id}/portfolio").json()
    assert portfolio["agent"]["tokens"] == 2
    assert portfolio["token_value"] == 200
    # Net worth is unchanged by a trade: credits simply became tokens, less fees.
    assert portfolio["net_worth"] == 1000 - portfolio["agent"]["tokens"] * 100 * 0.003 + 0


def test_heartbeat_document(client, make_agent):
    make_agent("Ada")
    resp = client.get("/heartbeat")
    assert resp.status_code == 200
    assert "BOTMARKET heartbeat" in resp.text
    assert "Actions available now" in resp.text
    # Every live action is advertised to agents polling this document.
    for path in ("/trade", "/tip", "/coins", "/proposals", "/votes"):
        assert path in resp.text
