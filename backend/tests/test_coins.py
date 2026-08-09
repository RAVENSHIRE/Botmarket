"""Tests for the pump.fun-style memecoin platform.

The economics under test: a fixed supply with a fixed curve allocation, market
cap driving graduation, fees splitting with the creator, and a comment thread
attached to each coin.
"""

from __future__ import annotations

import pytest

LAUNCH_FEE = 100.0
GRADUATION_MCAP = 4_000.0
TOTAL_SUPPLY = 1_000_000.0
CURVE_SUPPLY = 800_000.0
FEE_BPS = 100.0


def launch(client, agent, symbol="WOOF", name="Woof Coin", **extra) -> dict:
    """Launch a coin as ``agent``."""
    body = {"symbol": symbol, "name": name, **extra}
    resp = client.post(f"/agents/{agent.id}/coins", json=body, headers=agent.headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def buy(client, agent, coin_id, quantity):
    """Buy on the curve as ``agent``."""
    return client.post(
        f"/coins/{coin_id}/buy", json={"quantity": quantity}, headers=agent.headers
    )


def sell(client, agent, coin_id, quantity):
    """Sell on the curve as ``agent``."""
    return client.post(
        f"/coins/{coin_id}/sell", json={"quantity": quantity}, headers=agent.headers
    )


# --- Launching -----------------------------------------------------------


def test_launch_burns_the_fee_and_opens_the_curve(client, make_agent):
    founder = make_agent("Founder", "meme")
    coin = launch(client, founder, description="a very good dog")

    assert coin["symbol"] == "WOOF"
    assert coin["description"] == "a very good dog"
    assert coin["supply"] == 0
    assert coin["status"] == "live"
    assert coin["total_supply"] == TOTAL_SUPPLY
    assert coin["curve_supply"] == CURVE_SUPPLY
    assert coin["remaining_supply"] == CURVE_SUPPLY
    assert client.get(f"/agents/{founder.id}").json()["wallet"] == 1000 - LAUNCH_FEE

    assert any("$WOOF" in p["content"] for p in client.get("/feed").json())


def test_a_fresh_coin_has_a_nonzero_market_cap(client, make_agent):
    """The whole supply exists from launch, so the cap is priced on all of it."""
    coin = launch(client, make_agent("Founder", "meme"))
    assert coin["market_cap"] == pytest.approx(coin["spot_price"] * TOTAL_SUPPLY)
    assert coin["market_cap"] > 0
    assert coin["progress"] < 1


def test_symbols_are_unique_and_normalised(client, make_agent):
    first = make_agent("One", "meme")
    second = make_agent("Two", "meme")
    launch(client, first, symbol="dupe")

    resp = client.post(
        f"/agents/{second.id}/coins",
        json={"symbol": "DUPE", "name": "Copy"},
        headers=second.headers,
    )
    assert resp.status_code == 409


def test_launch_without_the_fee_is_refused(client, make_agent):
    skint = make_agent("Skint", "meme", wallet=10)
    resp = client.post(
        f"/agents/{skint.id}/coins",
        json={"symbol": "NOPE", "name": "Nope"},
        headers=skint.headers,
    )
    assert resp.status_code == 402


def test_launching_needs_your_own_key(client, make_agent):
    owner = make_agent("Owner", "meme")
    intruder = make_agent("Intruder", "meme")
    resp = client.post(
        f"/agents/{owner.id}/coins",
        json={"symbol": "STEAL", "name": "Steal"},
        headers=intruder.headers,
    )
    assert resp.status_code == 403


# --- The curve -----------------------------------------------------------


def test_buying_mints_supply_and_raises_the_price(client, make_agent):
    degen = make_agent("Degen", "meme")
    coin = launch(client, degen)
    before = coin["spot_price"]

    resp = buy(client, degen, coin["id"], 100_000)
    assert resp.status_code == 200
    body = resp.json()

    assert body["supply"] == 100_000
    assert body["spot_price"] > before
    assert body["cost"] > 0
    assert body["fee"] == pytest.approx(body["cost"] * FEE_BPS / 10_000, rel=1e-3)


def test_a_late_buyer_pays_more_than_an_early_one(client, make_agent):
    early = make_agent("Early", "meme", wallet=50_000)
    late = make_agent("Late", "trader", wallet=50_000)
    coin = launch(client, early, symbol="FOMO", name="Fomo")

    first = buy(client, early, coin["id"], 100_000)
    second = buy(client, late, coin["id"], 100_000)
    assert second.json()["cost"] > first.json()["cost"]


def test_round_trip_costs_only_the_fees(client, make_agent):
    """The curve is exact; what a round trip loses is the two fees."""
    trader = make_agent("RoundTrip", "meme", wallet=50_000)
    coin = launch(client, trader, symbol="RT", name="Round Trip")
    before = client.get(f"/agents/{trader.id}").json()["wallet"]

    bought = buy(client, trader, coin["id"], 50_000).json()
    sold = sell(client, trader, coin["id"], 50_000).json()

    assert sold["supply"] == 0
    assert sold["reserve"] == pytest.approx(0, abs=1e-6)
    after = client.get(f"/agents/{trader.id}").json()["wallet"]
    # The creator is this same agent, so half of each fee comes straight back.
    expected_loss = (bought["fee"] + sold["fee"]) * 0.5
    assert after == pytest.approx(before - expected_loss, abs=0.01)


def test_selling_more_than_you_hold_is_refused(client, make_agent):
    holder = make_agent("Holder", "meme", wallet=10_000)
    coin = launch(client, holder, symbol="HOLD", name="Hold")
    buy(client, holder, coin["id"], 10_000)

    assert sell(client, holder, coin["id"], 50_000).status_code == 402


def test_the_curve_allocation_is_finite(client, make_agent):
    """Asking for more than exists is refused, not silently shrunk."""
    whale = make_agent("Whale", "trader", wallet=1_000_000)
    coin = launch(client, whale, symbol="CAP", name="Capped")

    resp = buy(client, whale, coin["id"], CURVE_SUPPLY + 1)
    assert resp.status_code == 422
    assert "remain on the curve" in resp.json()["detail"]


# --- Graduation ----------------------------------------------------------


def test_a_coin_graduates_on_market_cap(client, make_agent):
    whale = make_agent("Whale", "trader", wallet=100_000)
    coin = launch(client, whale, symbol="GRAD", name="Graduate")

    # ~1,300 credits of buying is enough with the shipped economics.
    resp = buy(client, whale, coin["id"], 640_000)
    assert resp.status_code == 200
    assert resp.json()["graduated"] is True
    assert resp.json()["market_cap"] >= GRADUATION_MCAP

    detail = client.get(f"/coins/{coin['id']}").json()
    assert detail["status"] == "graduated"
    assert detail["progress"] == 1.0
    assert detail["graduated_tick"] is not None


def test_graduation_closes_minting_but_not_exits(client, make_agent):
    whale = make_agent("Whale", "trader", wallet=100_000)
    coin = launch(client, whale, symbol="EXIT", name="Exit")
    buy(client, whale, coin["id"], 640_000)

    assert buy(client, whale, coin["id"], 1).status_code == 422
    assert sell(client, whale, coin["id"], 1000).status_code == 200


def test_graduation_pays_the_creator_reputation(client, make_agent):
    whale = make_agent("Whale", "trader", wallet=100_000)
    coin = launch(client, whale, symbol="REP", name="Rep")
    before = client.get(f"/agents/{whale.id}").json()["reputation"]

    buy(client, whale, coin["id"], 640_000)
    assert client.get(f"/agents/{whale.id}").json()["reputation"] > before


# --- Fees ----------------------------------------------------------------


def test_the_creator_earns_a_share_of_trading_fees(client, make_agent):
    creator = make_agent("Creator", "meme")
    trader = make_agent("Trader", "trader", wallet=50_000)
    coin = launch(client, creator, symbol="FEE", name="Fee")

    before = client.get(f"/agents/{creator.id}").json()["wallet"]
    fill = buy(client, trader, coin["id"], 100_000).json()
    after = client.get(f"/agents/{creator.id}").json()["wallet"]

    assert after > before
    assert after - before == pytest.approx(fill["fee"] * 0.5, rel=1e-3)
    assert client.get(f"/coins/{coin['id']}").json()["creator_fees_earned"] > 0


def test_fees_do_not_come_out_of_the_reserve(client, make_agent):
    """The reserve must only ever hold what was paid for supply."""
    creator = make_agent("Creator", "meme")
    trader = make_agent("Trader", "trader", wallet=50_000)
    coin = launch(client, creator, symbol="SOLV", name="Solvent")

    fill = buy(client, trader, coin["id"], 100_000).json()
    assert fill["reserve"] == pytest.approx(fill["cost"], rel=1e-6)

    # Everyone can still exit at the curve price.
    assert sell(client, trader, coin["id"], 100_000).status_code == 200


# --- The board -----------------------------------------------------------


def test_the_board_ranks_by_progress_by_default(client, make_agent):
    founder = make_agent("Founder", "meme", wallet=100_000)
    quiet = launch(client, founder, symbol="QUIET", name="Quiet")
    hot = launch(client, founder, symbol="HOT", name="Hot")
    buy(client, founder, hot["id"], 300_000)

    board = client.get("/coins").json()
    assert board[0]["symbol"] == "HOT"
    assert {c["symbol"] for c in board} == {"HOT", "QUIET"}
    assert quiet["progress"] < board[0]["progress"]


def test_the_board_can_be_sorted(client, make_agent):
    founder = make_agent("Founder", "meme", wallet=100_000)
    launch(client, founder, symbol="FIRST", name="First")
    launch(client, founder, symbol="SECOND", name="Second")

    newest = client.get("/coins", params={"sort": "new"}).json()
    assert newest[0]["symbol"] == "SECOND"

    assert client.get("/coins", params={"sort": "nonsense"}).status_code == 422


def test_king_of_the_hill_is_the_closest_to_graduating(client, make_agent):
    founder = make_agent("Founder", "meme", wallet=100_000)
    launch(client, founder, symbol="QUIET", name="Quiet")
    hot = launch(client, founder, symbol="HOT", name="Hot")
    buy(client, founder, hot["id"], 300_000)

    assert client.get("/coins/king").json()["symbol"] == "HOT"


def test_king_is_null_before_any_launch(client):
    assert client.get("/coins/king").json() is None


def test_a_coin_can_be_fetched_by_ticker(client, make_agent):
    launch(client, make_agent("Founder", "meme"), symbol="TICK", name="Tick")
    assert client.get("/coins/by-symbol/tick").json()["symbol"] == "TICK"
    assert client.get("/coins/by-symbol/nope").status_code == 404


# --- Tape and thread -----------------------------------------------------


def test_the_trade_feed_records_both_sides(client, make_agent):
    trader = make_agent("Trader", "meme", wallet=50_000)
    coin = launch(client, trader, symbol="TAPE", name="Tape")
    buy(client, trader, coin["id"], 20_000)
    sell(client, trader, coin["id"], 5_000)

    tape = client.get(f"/coins/{coin['id']}/trades").json()
    assert [row["side"] for row in tape] == ["sell", "buy"]
    assert tape[0]["agent_name"] == "Trader"
    assert all(row["symbol"] == "TAPE" for row in tape)


def test_agents_can_reply_to_a_coin(client, make_agent):
    creator = make_agent("Creator", "meme")
    commenter = make_agent("Commenter", "trader")
    coin = launch(client, creator, symbol="CHAT", name="Chat")

    resp = client.post(
        f"/coins/{coin['id']}/replies",
        json={"content": "this is going to graduate"},
        headers=commenter.headers,
    )
    assert resp.status_code == 201
    assert resp.json()["agent_id"] == commenter.id

    thread = client.get(f"/coins/{coin['id']}/replies").json()
    assert thread[0]["content"] == "this is going to graduate"
    assert client.get(f"/coins/{coin['id']}").json()["reply_count"] == 1


def test_replying_needs_a_key(client, make_agent):
    coin = launch(client, make_agent("Creator", "meme"), symbol="AUTH", name="Auth")
    resp = client.post(f"/coins/{coin['id']}/replies", json={"content": "anon"})
    assert resp.status_code == 401


# --- Portfolio integration ----------------------------------------------


def test_holdings_show_up_in_the_portfolio_and_net_worth(client, make_agent):
    collector = make_agent("Collector", "meme", wallet=10_000)
    coin = launch(client, collector, symbol="ART", name="Art")
    buy(client, collector, coin["id"], 100_000)

    portfolio = client.get(f"/agents/{collector.id}/portfolio").json()
    assert portfolio["holdings"][0]["symbol"] == "ART"
    assert portfolio["holdings"][0]["quantity"] == 100_000
    assert portfolio["net_worth"] > portfolio["agent"]["wallet"]


def test_unknown_coin_404s(client, agent):
    assert client.get("/coins/9999").status_code == 404
    assert buy(client, agent, 9999, 1).status_code == 404
