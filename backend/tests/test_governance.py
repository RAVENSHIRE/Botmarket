"""Tests for funded proposals and token-weighted voting."""

from __future__ import annotations

PROPOSAL_COST = 250.0
VOTING_TICKS = 3


def _propose(client, agent_id: int, **overrides) -> dict:
    body = {"title": "Ship the arena", "effect": "stimulus", "magnitude": 2.0}
    body.update(overrides)
    resp = client.post(f"/agents/{agent_id}/proposals", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_proposing_burns_the_fee_and_opens_voting(client, make_agent):
    agent_id = make_agent("Author", "analyst")
    proposal = _propose(client, agent_id)

    assert proposal["status"] == "open"
    assert proposal["closes_tick"] == proposal["created_tick"] + VOTING_TICKS
    assert client.get(f"/agents/{agent_id}").json()["wallet"] == 1000 - PROPOSAL_COST
    assert any("proposal #" in p["content"] for p in client.get("/feed").json())


def test_proposing_without_the_fee_is_refused(client, make_agent):
    agent_id = make_agent("Skint", "analyst", wallet=10)
    resp = client.post(f"/agents/{agent_id}/proposals", json={"title": "Free lunch"})
    assert resp.status_code == 402


def test_unknown_effect_rejected(client, make_agent):
    agent_id = make_agent("Author", "analyst")
    resp = client.post(
        f"/agents/{agent_id}/proposals", json={"title": "Chaos", "effect": "explode"}
    )
    assert resp.status_code == 422


def test_voting_weight_grows_with_tokens(client, make_agent):
    author = make_agent("Author", "analyst")
    whale = make_agent("Whale", "trader", wallet=100_000)
    proposal = _propose(client, author)

    small = client.post(
        f"/proposals/{proposal['id']}/votes", json={"agent_id": author, "support": True}
    ).json()
    assert small["weight"] >= 1.0

    client.post(f"/agents/{whale}/trade", json={"side": "buy", "quantity": 50})
    large = client.post(
        f"/proposals/{proposal['id']}/votes", json={"agent_id": whale, "support": False}
    ).json()
    assert large["weight"] > small["weight"]
    assert large["weight_against"] > large["weight_for"]


def test_an_agent_votes_only_once(client, make_agent):
    author = make_agent("Author", "analyst")
    proposal = _propose(client, author)
    body = {"agent_id": author, "support": True}

    assert client.post(f"/proposals/{proposal['id']}/votes", json=body).status_code == 200
    assert client.post(f"/proposals/{proposal['id']}/votes", json=body).status_code == 409


def test_a_supported_proposal_passes_and_moves_the_market(client, make_agent):
    author = make_agent("Author", "analyst")
    backer = make_agent("Backer", "analyst")
    proposal = _propose(client, author, effect="stimulus", magnitude=3.0)

    for voter in (author, backer):
        client.post(f"/proposals/{proposal['id']}/votes", json={"agent_id": voter, "support": True})

    # Run out the voting window; the proposal resolves inside a tick.
    for _ in range(VOTING_TICKS + 1):
        result = client.post("/simulation/tick").json()
        if result["proposals_resolved"]:
            break

    assert result["proposals_resolved"][0]["status"] == "passed"
    assert result["proposals_resolved"][0]["pressure"] == 3.0
    assert client.get(f"/proposals/{proposal['id']}").json()["status"] == "passed"


def test_an_opposed_proposal_is_rejected(client, make_agent):
    author = make_agent("Author", "analyst")
    critic = make_agent("Critic", "trader", wallet=100_000)
    proposal = _propose(client, author)

    client.post(f"/agents/{critic}/trade", json={"side": "buy", "quantity": 50})
    client.post(f"/proposals/{proposal['id']}/votes", json={"agent_id": author, "support": True})
    client.post(f"/proposals/{proposal['id']}/votes", json={"agent_id": critic, "support": False})

    for _ in range(VOTING_TICKS + 1):
        result = client.post("/simulation/tick").json()
        if result["proposals_resolved"]:
            break

    assert result["proposals_resolved"][0]["status"] == "rejected"
    assert result["proposals_resolved"][0]["pressure"] == 0.0


def test_an_unvoted_proposal_fails_quorum(client, make_agent):
    author = make_agent("Author", "analyst")
    proposal = _propose(client, author)

    for _ in range(VOTING_TICKS + 1):
        result = client.post("/simulation/tick").json()
        if result["proposals_resolved"]:
            break

    assert result["proposals_resolved"][0]["status"] == "rejected"
    assert client.get("/proposals", params={"status": "rejected"}).json()[0]["id"] == proposal["id"]


def test_voting_closes_after_resolution(client, make_agent):
    author = make_agent("Author", "analyst")
    latecomer = make_agent("Latecomer", "meme")
    proposal = _propose(client, author)

    for _ in range(VOTING_TICKS + 1):
        if client.post("/simulation/tick").json()["proposals_resolved"]:
            break

    resp = client.post(
        f"/proposals/{proposal['id']}/votes", json={"agent_id": latecomer, "support": True}
    )
    assert resp.status_code == 422


def test_unknown_proposal_404s(client, make_agent):
    agent_id = make_agent("Voter")
    assert client.get("/proposals/9999").status_code == 404
    assert (
        client.post("/proposals/9999/votes", json={"agent_id": agent_id})
    ).status_code == 404
