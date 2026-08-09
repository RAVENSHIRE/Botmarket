"""Tests for funded proposals and token-weighted voting."""

from __future__ import annotations

PROPOSAL_COST = 250.0
VOTING_TICKS = 3


def propose(client, agent, **overrides) -> dict:
    """Submit a proposal as ``agent``."""
    body = {"title": "Ship the arena", "effect": "stimulus", "magnitude": 2.0}
    body.update(overrides)
    resp = client.post(
        f"/agents/{agent.id}/proposals", json=body, headers=agent.headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def vote(client, agent, proposal_id: int, support: bool = True):
    """Cast a vote as ``agent``."""
    return client.post(
        f"/proposals/{proposal_id}/votes",
        json={"support": support},
        headers=agent.headers,
    )


def buy_tokens(client, agent, quantity: float):
    """Give an agent voting weight by buying $BOT."""
    return client.post(
        f"/agents/{agent.id}/trade",
        json={"side": "buy", "quantity": quantity},
        headers=agent.headers,
    )


def run_until_resolved(client, agent, limit: int = VOTING_TICKS + 1) -> dict:
    """Advance the world until a proposal resolves, returning that tick."""
    result: dict = {}
    for _ in range(limit):
        result = client.post("/simulation/tick", headers=agent.headers).json()
        if result["proposals_resolved"]:
            break
    return result


# --- Submitting ----------------------------------------------------------


def test_proposing_burns_the_fee_and_opens_voting(client, make_agent):
    author = make_agent("Author", "analyst")
    proposal = propose(client, author)

    assert proposal["status"] == "open"
    assert proposal["closes_tick"] == proposal["created_tick"] + VOTING_TICKS
    assert client.get(f"/agents/{author.id}").json()["wallet"] == 1000 - PROPOSAL_COST
    assert any("proposal #" in p["content"] for p in client.get("/feed").json())


def test_proposing_without_the_fee_is_refused(client, make_agent):
    skint = make_agent("Skint", "analyst", wallet=10)
    resp = client.post(
        f"/agents/{skint.id}/proposals",
        json={"title": "Free lunch"},
        headers=skint.headers,
    )
    assert resp.status_code == 402


def test_unknown_effect_rejected(client, make_agent):
    author = make_agent("Author", "analyst")
    resp = client.post(
        f"/agents/{author.id}/proposals",
        json={"title": "Chaos", "effect": "explode"},
        headers=author.headers,
    )
    assert resp.status_code == 422


def test_proposing_needs_your_own_key(client, make_agent):
    owner = make_agent("Owner", "analyst")
    intruder = make_agent("Intruder", "analyst")
    resp = client.post(
        f"/agents/{owner.id}/proposals",
        json={"title": "Not mine"},
        headers=intruder.headers,
    )
    assert resp.status_code == 403


# --- Voting --------------------------------------------------------------


def test_voting_weight_grows_with_tokens(client, make_agent):
    author = make_agent("Author", "analyst")
    whale = make_agent("Whale", "trader", wallet=100_000)
    proposal = propose(client, author)

    small = vote(client, author, proposal["id"], True).json()
    assert small["weight"] >= 1.0

    buy_tokens(client, whale, 50)
    large = vote(client, whale, proposal["id"], False).json()
    assert large["weight"] > small["weight"]
    assert large["weight_against"] > large["weight_for"]


def test_a_vote_is_cast_as_the_key_owner(client, make_agent):
    """An agent cannot vote another agent's weight by naming it in the body."""
    author = make_agent("Author", "analyst")
    whale = make_agent("Whale", "trader", wallet=100_000)
    proposal = propose(client, author)
    buy_tokens(client, whale, 50)

    cast = vote(client, author, proposal["id"], True).json()
    assert cast["agent_id"] == author.id
    assert cast["weight"] < 10  # the author's own weight, not the whale's


def test_voting_without_a_key_is_401(client, make_agent):
    author = make_agent("Author", "analyst")
    proposal = propose(client, author)
    assert client.post(
        f"/proposals/{proposal['id']}/votes", json={"support": True}
    ).status_code == 401


def test_an_agent_votes_only_once(client, make_agent):
    author = make_agent("Author", "analyst")
    proposal = propose(client, author)

    assert vote(client, author, proposal["id"]).status_code == 200
    assert vote(client, author, proposal["id"]).status_code == 409


# --- Resolution ----------------------------------------------------------


def test_a_supported_proposal_passes_and_moves_the_market(client, make_agent):
    author = make_agent("Author", "analyst")
    backer = make_agent("Backer", "analyst")
    proposal = propose(client, author, effect="stimulus", magnitude=3.0)

    for voter in (author, backer):
        vote(client, voter, proposal["id"], True)

    result = run_until_resolved(client, author)
    assert result["proposals_resolved"][0]["status"] == "passed"
    assert result["proposals_resolved"][0]["pressure"] == 3.0
    assert client.get(f"/proposals/{proposal['id']}").json()["status"] == "passed"


def test_an_opposed_proposal_is_rejected(client, make_agent):
    author = make_agent("Author", "analyst")
    critic = make_agent("Critic", "trader", wallet=100_000)
    proposal = propose(client, author)

    buy_tokens(client, critic, 50)
    vote(client, author, proposal["id"], True)
    vote(client, critic, proposal["id"], False)

    result = run_until_resolved(client, author)
    assert result["proposals_resolved"][0]["status"] == "rejected"
    assert result["proposals_resolved"][0]["pressure"] == 0.0


def test_an_unvoted_proposal_fails_quorum(client, make_agent):
    author = make_agent("Author", "analyst")
    proposal = propose(client, author)

    result = run_until_resolved(client, author)
    assert result["proposals_resolved"][0]["status"] == "rejected"
    rejected = client.get("/proposals", params={"status": "rejected"}).json()
    assert rejected[0]["id"] == proposal["id"]


def test_voting_closes_after_resolution(client, make_agent):
    author = make_agent("Author", "analyst")
    latecomer = make_agent("Latecomer", "meme")
    proposal = propose(client, author)

    run_until_resolved(client, author)
    assert vote(client, latecomer, proposal["id"], True).status_code == 422


def test_unknown_proposal_404s(client, agent):
    assert client.get("/proposals/9999").status_code == 404
    assert vote(client, agent, 9999).status_code == 404
