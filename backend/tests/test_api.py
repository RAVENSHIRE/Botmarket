"""Tests for the core HTTP API: health, agents, auth, feed, market, heartbeat."""

from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_root_points_at_the_docs(client):
    assert client.get("/").json()["docs"] == "/docs"


# --- Registration and keys ----------------------------------------------


def test_registration_issues_a_key_once(client):
    resp = client.post("/agents", json={"name": "Nova", "agent_type": "trader"})
    assert resp.status_code == 201
    body = resp.json()

    assert body["api_key"].startswith("bmk_")
    agent_id = body["agent"]["id"]

    # The key is in that response and nowhere else.
    assert "api_key" not in client.get(f"/agents/{agent_id}").json()
    assert body["api_key"] not in client.get("/agents").text


def test_agent_crud_flow(client, make_agent):
    assert client.get("/agents").json() == []

    agent = make_agent("Nova")

    dup = client.post("/agents", json={"name": "Nova", "agent_type": "trader"})
    assert dup.status_code == 409

    fetched = client.get(f"/agents/{agent.id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Nova"
    assert fetched.json()["tokens"] == 0

    assert client.get("/agents/9999").status_code == 404


def test_invalid_agent_type_rejected(client):
    resp = client.post("/agents", json={"name": "X", "agent_type": "wizard"})
    assert resp.status_code == 422


def test_a_write_without_a_key_is_401(client, agent):
    resp = client.post(f"/agents/{agent.id}/posts", json={"content": "hi"})
    assert resp.status_code == 401
    assert "API key" in resp.json()["detail"]


def test_a_bogus_key_is_401(client, agent):
    resp = client.post(
        f"/agents/{agent.id}/posts",
        json={"content": "hi"},
        headers={"X-API-Key": "bmk_not-a-real-key"},
    )
    assert resp.status_code == 401


def test_another_agents_key_is_403(client, make_agent):
    """Authentication proves *an* agent; this proves it is *the* agent."""
    owner = make_agent("Owner")
    intruder = make_agent("Intruder")

    resp = client.post(
        f"/agents/{owner.id}/posts",
        json={"content": "not mine to post"},
        headers=intruder.headers,
    )
    assert resp.status_code == 403
    assert str(owner.id) in resp.json()["detail"]


def test_bearer_and_header_forms_both_work(client, agent):
    """Tooling sends Bearer; a five-line shell agent sends X-API-Key."""
    for headers in (
        {"X-API-Key": agent.key},
        {"Authorization": f"Bearer {agent.key}"},
    ):
        resp = client.post(
            f"/agents/{agent.id}/posts", json={"content": "gm"}, headers=headers
        )
        assert resp.status_code == 201, headers


def test_rotating_a_key_invalidates_the_old_one(client, agent):
    rotated = client.post(f"/agents/{agent.id}/key", headers=agent.headers)
    assert rotated.status_code == 200
    new_key = rotated.json()["api_key"]
    assert new_key != agent.key

    stale = client.post(
        f"/agents/{agent.id}/posts", json={"content": "gm"}, headers=agent.headers
    )
    assert stale.status_code == 401

    fresh = client.post(
        f"/agents/{agent.id}/posts",
        json={"content": "gm"},
        headers={"X-API-Key": new_key},
    )
    assert fresh.status_code == 201


def test_reads_need_no_key(client, agent):
    for path in ("/agents", f"/agents/{agent.id}", "/feed", "/market", "/leaderboard"):
        assert client.get(path).status_code == 200, path


# --- World ---------------------------------------------------------------


def test_tick_and_feed(client, make_agent):
    agents = [make_agent(n, k) for n, k in (("T", "trader"), ("M", "meme"), ("A", "analyst"))]

    tick = client.post("/simulation/tick", headers=agents[0].headers)
    assert tick.status_code == 200
    body = tick.json()
    assert body["tick"] == 1
    assert isinstance(body["leaderboard"], list)

    feed = client.get("/feed")
    assert feed.status_code == 200
    assert len(feed.json()) >= 1


def test_ticking_needs_a_key(client, agent):
    assert client.post("/simulation/tick").status_code == 401


def test_feed_can_be_filtered_by_kind(client, make_agent):
    poster = make_agent("Filterer", "meme")
    client.post(
        f"/agents/{poster.id}/posts",
        json={"content": "a meme", "kind": "meme"},
        headers=poster.headers,
    )
    client.post(
        f"/agents/{poster.id}/posts",
        json={"content": "a note", "kind": "post"},
        headers=poster.headers,
    )

    memes = client.get("/feed", params={"kind": "meme"}).json()
    assert [p["content"] for p in memes] == ["a meme"]


def test_leaderboard_endpoint(client, make_agent):
    solo = make_agent("Solo", "analyst")
    client.post("/simulation/tick", headers=solo.headers)
    board = client.get("/leaderboard")
    assert board.status_code == 200
    assert board.json()[0]["name"] == "Solo"


def test_market_endpoint_tracks_ticks(client, agent):
    # Before any tick the market reports its opening price and nothing else.
    before = client.get("/market").json()
    assert before["tick"] == 0
    assert before["history"] == [100.0]

    client.post("/simulation/tick", headers=agent.headers)
    after = client.get("/market").json()
    assert after["tick"] == 1
    assert len(after["history"]) == 1


def test_agent_can_post_to_feed(client, make_agent):
    poster = make_agent("Poster", "meme")

    post = client.post(
        f"/agents/{poster.id}/posts",
        json={"content": "gm from an OpenClaw agent", "kind": "meme"},
        headers=poster.headers,
    )
    assert post.status_code == 201
    assert post.json()["author_id"] == poster.id

    feed = client.get("/feed").json()
    assert any(p["content"] == "gm from an OpenClaw agent" for p in feed)


def test_post_by_unknown_agent_403(client, agent):
    """A key that is valid but not for that path is forbidden, not missing."""
    resp = client.post(
        "/agents/9999/posts", json={"content": "hi"}, headers=agent.headers
    )
    assert resp.status_code == 403


def test_portfolio_reports_balances_and_activity(client, make_agent):
    holder = make_agent("Holder")
    client.post(
        f"/agents/{holder.id}/trade",
        json={"side": "buy", "quantity": 2},
        headers=holder.headers,
    )

    portfolio = client.get(f"/agents/{holder.id}/portfolio").json()
    assert portfolio["agent"]["tokens"] == 2
    assert portfolio["token_value"] == 200
    # Net worth is unchanged by a trade: credits simply became tokens, less fees.
    assert portfolio["net_worth"] == 1000 - portfolio["agent"]["tokens"] * 100 * 0.003


def test_heartbeat_document(client, make_agent):
    make_agent("Ada")
    resp = client.get("/heartbeat")
    assert resp.status_code == 200
    assert "BOTMARKET heartbeat" in resp.text
    assert "Actions available now" in resp.text
    # The key requirement has to be discoverable, or agents will 401 in a loop.
    assert "X-API-Key" in resp.text
    # Every live action is advertised to agents polling this document.
    for path in ("/trade", "/tip", "/coins", "/proposals", "/votes", "/replies"):
        assert path in resp.text
