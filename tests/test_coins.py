"""API tests for the memecoin bonding-curve endpoints."""

from __future__ import annotations


def _agent(client, name="Pepe", kind="meme", wallet=1000.0):
    """Create an agent and return its id."""
    resp = client.post(
        "/agents", json={"name": name, "agent_type": kind, "wallet": wallet}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _launch(client, agent_id, name="DogeSim", symbol="DOGE"):
    resp = client.post(
        f"/agents/{agent_id}/coins", json={"name": name, "symbol": symbol}
    )
    return resp


def test_launch_coin_appears_in_list(client):
    aid = _agent(client)
    resp = _launch(client, aid)
    assert resp.status_code == 201
    body = resp.json()
    assert body["symbol"] == "DOGE"
    assert body["status"] == "active"

    coins = client.get("/coins").json()
    assert any(c["symbol"] == "DOGE" for c in coins)


def test_launch_by_unknown_agent_404(client):
    resp = client.post("/agents/999/coins", json={"name": "X", "symbol": "X"})
    assert resp.status_code == 404


def test_duplicate_symbol_rejected(client):
    aid = _agent(client)
    assert _launch(client, aid, symbol="DUP").status_code == 201
    dup = _launch(client, aid, name="Other", symbol="DUP")
    assert dup.status_code == 400


def test_buy_moves_wallet_holding_and_price(client):
    aid = _agent(client, wallet=1000.0)
    coin_id = _launch(client, aid).json()["id"]

    buy = client.post(f"/coins/{coin_id}/buy", json={"agent_id": aid, "qty": 100})
    assert buy.status_code == 200
    body = buy.json()
    # cost for 100 tokens from supply 0 with base=1, slope=0.01 is 150.
    assert body["cost_or_proceeds"] == 150.0
    assert body["wallet"] == 850.0
    assert body["holding"] == 100.0
    assert body["new_spot_price"] == 2.0  # 1 + 0.01*100


def test_sell_reverses_a_buy(client):
    aid = _agent(client, wallet=1000.0)
    coin_id = _launch(client, aid).json()["id"]
    client.post(f"/coins/{coin_id}/buy", json={"agent_id": aid, "qty": 100})

    sell = client.post(f"/coins/{coin_id}/sell", json={"agent_id": aid, "qty": 100})
    assert sell.status_code == 200
    body = sell.json()
    assert body["holding"] == 0.0
    # Linear curve is lossless on a full round-trip: wallet back to 1000.
    assert body["wallet"] == 1000.0


def test_buy_insufficient_funds_400(client):
    aid = _agent(client, wallet=1000.0)
    coin_id = _launch(client, aid).json()["id"]
    # Buying 1000 tokens would cost far more than a 1000 wallet.
    resp = client.post(f"/coins/{coin_id}/buy", json={"agent_id": aid, "qty": 1000})
    assert resp.status_code == 400


def test_buy_unknown_coin_404(client):
    aid = _agent(client)
    resp = client.post("/coins/999/buy", json={"agent_id": aid, "qty": 10})
    assert resp.status_code == 404


def test_coin_graduates_when_reserve_crosses_threshold(client):
    # Rich agent so it can afford a graduating buy.
    aid = _agent(client, name="Whale", wallet=1_000_000.0)
    coin_id = _launch(client, aid, symbol="MOON").json()["id"]

    # reserve for 1500 tokens = 1500 + 0.01*1500^2/2 = 12750 >= 10000 threshold.
    buy = client.post(f"/coins/{coin_id}/buy", json={"agent_id": aid, "qty": 1500})
    assert buy.status_code == 200
    assert buy.json()["status"] == "graduated"

    detail = client.get(f"/coins/{coin_id}").json()
    assert detail["status"] == "graduated"
    assert detail["holders"][0]["agent_id"] == aid


def test_initial_buy_seeds_creator_holding(client):
    aid = _agent(client, wallet=1000.0)
    resp = client.post(
        f"/agents/{aid}/coins",
        json={"name": "SeedCoin", "symbol": "SEED", "initial_buy": 50},
    )
    assert resp.status_code == 201
    assert resp.json()["supply"] == 50.0
    detail = client.get(f"/coins/{resp.json()['id']}").json()
    assert detail["holders"][0]["balance"] == 50.0
