"""Tests for $BOT trading and peer-to-peer tipping over the API."""

from __future__ import annotations

import pytest

# With no ticks run, the market sits at its opening price.
OPENING_PRICE = 100.0
FEE_RATE = 0.003


def trade(client, agent, **body):
    """Place a $BOT trade as ``agent``."""
    return client.post(
        f"/agents/{agent.id}/trade", json=body, headers=agent.headers
    )


def test_buy_moves_credits_into_tokens(client, make_agent):
    buyer = make_agent("Buyer")

    resp = trade(client, buyer, side="buy", quantity=5)
    assert resp.status_code == 200
    body = resp.json()

    gross = 5 * OPENING_PRICE
    assert body["price"] == OPENING_PRICE
    assert body["fee"] == pytest.approx(gross * FEE_RATE)
    assert body["tokens"] == 5
    assert body["wallet"] == pytest.approx(1000 - gross - gross * FEE_RATE)


def test_sell_returns_credits(client, make_agent):
    seller = make_agent("Seller")
    trade(client, seller, side="buy", quantity=5)

    resp = trade(client, seller, side="sell", quantity=5)
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokens"] == 0
    # Round-tripping costs exactly two fees.
    assert body["wallet"] == pytest.approx(1000 - 2 * 5 * OPENING_PRICE * FEE_RATE)


def test_buying_beyond_the_wallet_is_refused(client, make_agent):
    broke = make_agent("Broke", wallet=50)
    resp = trade(client, broke, side="buy", quantity=10)
    assert resp.status_code == 402
    assert resp.json()["error"] == "InsufficientFunds"
    # Nothing was written.
    assert client.get(f"/agents/{broke.id}").json()["wallet"] == 50


def test_selling_tokens_you_do_not_hold_is_refused(client, make_agent):
    naked = make_agent("Naked")
    assert trade(client, naked, side="sell", quantity=1).status_code == 402


@pytest.mark.parametrize(
    "body", [{"side": "buy", "quantity": 0}, {"side": "hodl", "quantity": 1}]
)
def test_malformed_trades_rejected(client, make_agent, body):
    fuzzer = make_agent("Fuzzer")
    assert trade(client, fuzzer, **body).status_code == 422


def test_trading_needs_your_own_key(client, make_agent):
    owner = make_agent("Owner")
    intruder = make_agent("Intruder")
    resp = client.post(
        f"/agents/{owner.id}/trade",
        json={"side": "buy", "quantity": 1},
        headers=intruder.headers,
    )
    assert resp.status_code == 403
    assert client.get(f"/agents/{owner.id}").json()["tokens"] == 0


def test_tip_transfers_credits_and_standing(client, make_agent):
    sender = make_agent("Patron")
    recipient = make_agent("Artist", "meme")

    resp = client.post(
        f"/agents/{sender.id}/tip",
        json={"to_agent_id": recipient.id, "amount": 200, "note": "great post"},
        headers=sender.headers,
    )
    assert resp.status_code == 200
    assert resp.json()["wallet"] == 800

    assert client.get(f"/agents/{recipient.id}").json()["wallet"] == 1200
    # The recipient gains more standing than the sender.
    recipient_rep = client.get(f"/agents/{recipient.id}").json()["reputation"]
    sender_rep = client.get(f"/agents/{sender.id}").json()["reputation"]
    assert recipient_rep > sender_rep > 0

    # The note is published to the feed.
    assert any("great post" in p["content"] for p in client.get("/feed").json())


def test_tip_beyond_the_wallet_is_refused(client, make_agent):
    sender = make_agent("Poor", wallet=10)
    recipient = make_agent("Rich")
    resp = client.post(
        f"/agents/{sender.id}/tip",
        json={"to_agent_id": recipient.id, "amount": 500},
        headers=sender.headers,
    )
    assert resp.status_code == 402
    assert client.get(f"/agents/{recipient.id}").json()["wallet"] == 1000


def test_self_tipping_is_refused(client, agent):
    resp = client.post(
        f"/agents/{agent.id}/tip",
        json={"to_agent_id": agent.id, "amount": 10},
        headers=agent.headers,
    )
    assert resp.status_code == 422


def test_tipping_an_unknown_agent_404s(client, agent):
    resp = client.post(
        f"/agents/{agent.id}/tip",
        json={"to_agent_id": 9999, "amount": 10},
        headers=agent.headers,
    )
    assert resp.status_code == 404
