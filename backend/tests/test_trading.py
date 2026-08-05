"""Tests for $BOT trading and peer-to-peer tipping over the API."""

from __future__ import annotations

import pytest

# With no ticks run, the market sits at its opening price.
OPENING_PRICE = 100.0
FEE_RATE = 0.003


def test_buy_moves_credits_into_tokens(client, make_agent):
    agent_id = make_agent("Buyer")

    resp = client.post(f"/agents/{agent_id}/trade", json={"side": "buy", "quantity": 5})
    assert resp.status_code == 200
    body = resp.json()

    gross = 5 * OPENING_PRICE
    assert body["price"] == OPENING_PRICE
    assert body["fee"] == pytest.approx(gross * FEE_RATE)
    assert body["tokens"] == 5
    assert body["wallet"] == pytest.approx(1000 - gross - gross * FEE_RATE)


def test_sell_returns_credits(client, make_agent):
    agent_id = make_agent("Seller")
    client.post(f"/agents/{agent_id}/trade", json={"side": "buy", "quantity": 5})

    resp = client.post(f"/agents/{agent_id}/trade", json={"side": "sell", "quantity": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tokens"] == 0
    # Round-tripping costs exactly two fees.
    assert body["wallet"] == pytest.approx(1000 - 2 * 5 * OPENING_PRICE * FEE_RATE)


def test_buying_beyond_the_wallet_is_refused(client, make_agent):
    agent_id = make_agent("Broke", wallet=50)
    resp = client.post(f"/agents/{agent_id}/trade", json={"side": "buy", "quantity": 10})
    assert resp.status_code == 402
    assert resp.json()["error"] == "InsufficientFunds"
    # Nothing was written.
    assert client.get(f"/agents/{agent_id}").json()["wallet"] == 50


def test_selling_tokens_you_do_not_hold_is_refused(client, make_agent):
    agent_id = make_agent("Naked")
    resp = client.post(f"/agents/{agent_id}/trade", json={"side": "sell", "quantity": 1})
    assert resp.status_code == 402


@pytest.mark.parametrize(
    "payload", [{"side": "buy", "quantity": 0}, {"side": "hodl", "quantity": 1}]
)
def test_malformed_trades_rejected(client, make_agent, payload):
    agent_id = make_agent("Fuzzer")
    assert client.post(f"/agents/{agent_id}/trade", json=payload).status_code == 422


def test_tip_transfers_credits_and_standing(client, make_agent):
    sender = make_agent("Patron")
    recipient = make_agent("Artist", "meme")

    resp = client.post(
        f"/agents/{sender}/tip",
        json={"to_agent_id": recipient, "amount": 200, "note": "great post"},
    )
    assert resp.status_code == 200
    assert resp.json()["wallet"] == 800

    assert client.get(f"/agents/{recipient}").json()["wallet"] == 1200
    # The recipient gains more standing than the sender.
    recipient_rep = client.get(f"/agents/{recipient}").json()["reputation"]
    sender_rep = client.get(f"/agents/{sender}").json()["reputation"]
    assert recipient_rep > sender_rep > 0

    # The note is published to the feed.
    assert any("great post" in p["content"] for p in client.get("/feed").json())


def test_tip_beyond_the_wallet_is_refused(client, make_agent):
    sender = make_agent("Poor", wallet=10)
    recipient = make_agent("Rich")
    resp = client.post(f"/agents/{sender}/tip", json={"to_agent_id": recipient, "amount": 500})
    assert resp.status_code == 402
    assert client.get(f"/agents/{recipient}").json()["wallet"] == 1000


def test_self_tipping_is_refused(client, make_agent):
    agent_id = make_agent("Narcissus")
    resp = client.post(f"/agents/{agent_id}/tip", json={"to_agent_id": agent_id, "amount": 10})
    assert resp.status_code == 422


def test_tipping_an_unknown_agent_404s(client, make_agent):
    agent_id = make_agent("Sender")
    resp = client.post(f"/agents/{agent_id}/tip", json={"to_agent_id": 9999, "amount": 10})
    assert resp.status_code == 404
