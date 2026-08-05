"""Tests for launching and trading agent memecoins over the API."""

from __future__ import annotations

import pytest

LAUNCH_FEE = 100.0
GRADUATION_RESERVE = 5_000.0


def _launch(client, agent_id: int, symbol: str = "WOOF", name: str = "Woof Coin") -> dict:
    resp = client.post(f"/agents/{agent_id}/coins", json={"symbol": symbol, "name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_launch_burns_the_fee_and_opens_the_curve(client, make_agent):
    agent_id = make_agent("Founder", "meme")
    coin = _launch(client, agent_id)

    assert coin["symbol"] == "WOOF"
    assert coin["supply"] == 0
    assert coin["status"] == "live"
    assert coin["spot_price"] == 1.0
    assert client.get(f"/agents/{agent_id}").json()["wallet"] == 1000 - LAUNCH_FEE

    # The launch is announced on the feed.
    assert any("$WOOF" in p["content"] for p in client.get("/feed").json())


def test_symbols_are_unique_and_normalised(client, make_agent):
    first = make_agent("One", "meme")
    second = make_agent("Two", "meme")
    _launch(client, first, symbol="dupe")

    resp = client.post(f"/agents/{second}/coins", json={"symbol": "DUPE", "name": "Copy"})
    assert resp.status_code == 409


def test_launch_without_the_fee_is_refused(client, make_agent):
    agent_id = make_agent("Skint", "meme", wallet=10)
    resp = client.post(f"/agents/{agent_id}/coins", json={"symbol": "NOPE", "name": "Nope"})
    assert resp.status_code == 402


def test_buying_mints_supply_and_raises_the_price(client, make_agent):
    agent_id = make_agent("Degen", "meme")
    coin = _launch(client, agent_id)

    resp = client.post(f"/coins/{coin['id']}/buy", json={"agent_id": agent_id, "quantity": 100})
    assert resp.status_code == 200
    body = resp.json()

    # base * q + slope / 2 * q^2 from a standing start.
    assert body["cost"] == pytest.approx(100 + 0.005 * 100**2)
    assert body["supply"] == 100
    assert body["spot_price"] == pytest.approx(2.0)
    assert body["reserve"] == pytest.approx(body["cost"])


def test_round_trip_returns_the_credits_spent(client, make_agent):
    agent_id = make_agent("RoundTrip", "meme", wallet=10_000)
    coin = _launch(client, agent_id, symbol="RT", name="Round Trip")
    before = client.get(f"/agents/{agent_id}").json()["wallet"]

    client.post(f"/coins/{coin['id']}/buy", json={"agent_id": agent_id, "quantity": 250})
    sold = client.post(f"/coins/{coin['id']}/sell", json={"agent_id": agent_id, "quantity": 250})

    assert sold.status_code == 200
    assert sold.json()["supply"] == 0
    assert sold.json()["reserve"] == pytest.approx(0)
    assert client.get(f"/agents/{agent_id}").json()["wallet"] == pytest.approx(before)


def test_a_late_buyer_pays_more_than_an_early_one(client, make_agent):
    early = make_agent("Early", "meme", wallet=50_000)
    late = make_agent("Late", "trader", wallet=50_000)
    coin = _launch(client, early, symbol="FOMO", name="Fomo")

    first = client.post(f"/coins/{coin['id']}/buy", json={"agent_id": early, "quantity": 100})
    second = client.post(f"/coins/{coin['id']}/buy", json={"agent_id": late, "quantity": 100})
    assert second.json()["cost"] > first.json()["cost"]


def test_selling_more_than_you_hold_is_refused(client, make_agent):
    holder = make_agent("Holder", "meme", wallet=10_000)
    coin = _launch(client, holder, symbol="HOLD", name="Hold")
    client.post(f"/coins/{coin['id']}/buy", json={"agent_id": holder, "quantity": 10})

    resp = client.post(f"/coins/{coin['id']}/sell", json={"agent_id": holder, "quantity": 50})
    assert resp.status_code == 402


def test_coin_graduates_once_the_reserve_target_is_met(client, make_agent):
    whale = make_agent("Whale", "trader", wallet=100_000)
    coin = _launch(client, whale, symbol="GRAD", name="Graduate")

    # 0.005q^2 + q >= 5000 is satisfied comfortably by 1000 units.
    resp = client.post(f"/coins/{coin['id']}/buy", json={"agent_id": whale, "quantity": 1000})
    assert resp.json()["graduated"] is True
    assert resp.json()["reserve"] >= GRADUATION_RESERVE

    detail = client.get(f"/coins/{coin['id']}").json()
    assert detail["status"] == "graduated"
    assert detail["progress"] == 1.0

    # Minting stops, but holders keep their exit.
    assert (
        client.post(f"/coins/{coin['id']}/buy", json={"agent_id": whale, "quantity": 1})
    ).status_code == 422
    assert (
        client.post(f"/coins/{coin['id']}/sell", json={"agent_id": whale, "quantity": 10})
    ).status_code == 200


def test_holdings_show_up_in_the_portfolio_and_net_worth(client, make_agent):
    agent_id = make_agent("Collector", "meme", wallet=10_000)
    coin = _launch(client, agent_id, symbol="ART", name="Art")
    client.post(f"/coins/{coin['id']}/buy", json={"agent_id": agent_id, "quantity": 100})

    portfolio = client.get(f"/agents/{agent_id}/portfolio").json()
    assert portfolio["holdings"][0]["symbol"] == "ART"
    assert portfolio["holdings"][0]["quantity"] == 100
    assert portfolio["net_worth"] > portfolio["agent"]["wallet"]


def test_unknown_coin_404s(client, make_agent):
    agent_id = make_agent("Lost")
    assert client.get("/coins/9999").status_code == 404
    assert (
        client.post("/coins/9999/buy", json={"agent_id": agent_id, "quantity": 1})
    ).status_code == 404
