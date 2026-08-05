"""Tests for the live-trading service and its HTTP surface.

Everything here runs on the paper venue, which shares the whole code path with a
real exchange: same risk checks, same audit trail, same responses. The only
difference is which object sits at the end of it.
"""

from __future__ import annotations

import pytest

from botmarket.config import get_settings
from botmarket.services import credentials


@pytest.fixture(autouse=True)
def _reset_settings():
    """Clear the settings cache so per-test env overrides take effect."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def agent_id(make_agent):
    """A registered agent."""
    return make_agent("Quant", "trader")


@pytest.fixture
def account(client, agent_id):
    """A linked paper account."""
    resp = client.post(
        f"/agents/{agent_id}/venues",
        json={"venue": "paper", "environment": "paper", "label": "sim"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def order(client, account_id, **overrides):
    """Place an order with sensible defaults."""
    body = {"symbol": "BTC", "side": "buy", "size": 0.01}
    body.update(overrides)
    return client.post(f"/venue-accounts/{account_id}/orders", json=body)


# --- Venue discovery -----------------------------------------------------


def test_venues_are_advertised(client):
    venues = {v["name"]: v for v in client.get("/venues").json()}
    assert venues["paper"]["available"] is True
    assert venues["paper"]["requires_credentials"] is False
    assert venues["hyperliquid"]["requires_credentials"] is True


def test_risk_limits_are_visible(client):
    limits = client.get("/venues/limits").json()
    assert limits["trading_enabled"] is True
    # The safe default: real money is off until an operator turns it on.
    assert limits["allow_mainnet"] is False
    assert limits["max_leverage"] >= 1


# --- Linking -------------------------------------------------------------


def test_linking_a_paper_account_needs_no_credentials(account):
    assert account["venue"] == "paper"
    assert account["has_credentials"] is False
    assert account["is_real_money"] is False
    assert account["active"] is True


def test_one_account_per_venue_and_environment(client, agent_id, account):
    duplicate = client.post(
        f"/agents/{agent_id}/venues",
        json={"venue": "paper", "environment": "paper"},
    )
    assert duplicate.status_code == 409


def test_a_venue_cannot_run_in_the_wrong_environment(client, agent_id):
    resp = client.post(
        f"/agents/{agent_id}/venues",
        json={"venue": "paper", "environment": "testnet"},
    )
    assert resp.status_code == 422


def test_mainnet_is_refused_while_disabled(client, agent_id):
    resp = client.post(
        f"/agents/{agent_id}/venues",
        json={
            "venue": "hyperliquid",
            "environment": "mainnet",
            "wallet_address": "0xabc",
        },
    )
    assert resp.status_code == 422
    assert "mainnet is disabled" in resp.json()["detail"].lower()


def test_a_live_venue_needs_a_wallet_address(client, agent_id, monkeypatch):
    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", credentials.generate_key())
    get_settings.cache_clear()
    resp = client.post(
        f"/agents/{agent_id}/venues",
        json={"venue": "hyperliquid", "environment": "testnet"},
    )
    assert resp.status_code == 422
    assert "wallet address" in resp.json()["detail"].lower()


def test_linking_an_unknown_agent_404s(client):
    resp = client.post(
        "/agents/9999/venues", json={"venue": "paper", "environment": "paper"}
    )
    assert resp.status_code == 404


# --- Credentials ---------------------------------------------------------


def test_a_secret_is_never_returned(client, agent_id, monkeypatch):
    """The whole point of the credential store: it is write-only."""
    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", credentials.generate_key())
    get_settings.cache_clear()

    created = client.post(
        f"/agents/{agent_id}/venues",
        json={
            "venue": "hyperliquid",
            "environment": "testnet",
            "wallet_address": "0xabc",
            "secret": "0xdeadbeefcafe",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["has_credentials"] is True
    assert "0xdeadbeefcafe" not in created.text
    assert "secret" not in body

    listed = client.get(f"/agents/{agent_id}/venues")
    assert "0xdeadbeefcafe" not in listed.text


def test_storing_a_secret_without_a_key_is_refused(client, agent_id, monkeypatch):
    """Refusing to save is the safe failure; saving it in plaintext is not."""
    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", "")
    get_settings.cache_clear()

    resp = client.post(
        f"/agents/{agent_id}/venues",
        json={
            "venue": "hyperliquid",
            "environment": "testnet",
            "wallet_address": "0xabc",
            "secret": "0xdeadbeef",
        },
    )
    assert resp.status_code == 422
    assert "VENUE_ENCRYPTION_KEY" in resp.json()["detail"]


def test_seal_and_open_round_trip(monkeypatch):
    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", credentials.generate_key())
    get_settings.cache_clear()
    sealed = credentials.seal("super-secret")
    assert sealed != "super-secret"
    assert credentials.open_secret(sealed) == "super-secret"


def test_a_changed_key_is_reported_not_guessed(monkeypatch):
    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", credentials.generate_key())
    get_settings.cache_clear()
    sealed = credentials.seal("super-secret")

    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", credentials.generate_key())
    get_settings.cache_clear()
    with pytest.raises(credentials.CredentialError, match="VENUE_ENCRYPTION_KEY changed"):
        credentials.open_secret(sealed)


def test_a_passphrase_is_accepted_as_a_key(monkeypatch):
    """An operator who set a plain string must not silently lose their data."""
    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", "not-a-valid-fernet-key")
    get_settings.cache_clear()
    assert credentials.open_secret(credentials.seal("abc")) == "abc"


def test_empty_secrets_are_rejected(monkeypatch):
    monkeypatch.setenv("VENUE_ENCRYPTION_KEY", credentials.generate_key())
    get_settings.cache_clear()
    with pytest.raises(credentials.CredentialError):
        credentials.seal("   ")


def test_fingerprints_identify_without_revealing():
    secret = "0xdeadbeef"
    tag = credentials.fingerprint(secret)
    assert len(tag) == 8
    assert secret not in tag
    assert tag == credentials.fingerprint(secret)


# --- Orders --------------------------------------------------------------


def test_an_order_fills_and_opens_a_position(client, account):
    resp = order(client, account["id"], size=0.01)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["accepted"] is True
    assert body["filled_size"] == pytest.approx(0.01)
    assert body["is_real_money"] is False

    detail = client.get(f"/venue-accounts/{account['id']}").json()
    assert detail["positions"][0]["symbol"] == "BTC"


def test_a_dust_order_is_refused_by_risk(client, account):
    resp = order(client, account["id"], size=0.00001)
    assert resp.status_code == 422
    assert resp.json()["rule"] == "below_min_notional"


def test_an_oversized_order_is_refused(client, account):
    resp = order(client, account["id"], size=5)
    assert resp.status_code == 422
    assert resp.json()["rule"] == "above_max_order_value"


def test_excess_leverage_is_refused(client, account):
    resp = order(client, account["id"], size=0.01, leverage=40)
    assert resp.status_code == 422
    assert resp.json()["rule"] == "leverage_exceeded"


def test_refusals_are_recorded_in_the_audit_trail(client, account):
    """A silent agent and a blocked agent must be distinguishable."""
    order(client, account["id"], size=5)
    history = client.get(f"/venue-accounts/{account['id']}/orders").json()
    assert history[0]["status"] == "refused"
    assert "above_max_order_value" in history[0]["reason"]


def test_fills_are_recorded_too(client, account):
    order(client, account["id"], size=0.01)
    history = client.get(f"/venue-accounts/{account['id']}/orders").json()
    assert history[0]["status"] == "filled"


def test_the_kill_switch_stops_orders(client, account, monkeypatch):
    monkeypatch.setenv("TRADING_ENABLED", "false")
    get_settings.cache_clear()
    resp = order(client, account["id"], size=0.01)
    assert resp.status_code == 422
    assert resp.json()["rule"] == "trading_disabled"


def test_a_deactivated_account_cannot_trade(client, account):
    client.post(f"/venue-accounts/{account['id']}/active", params={"active": False})
    resp = order(client, account["id"], size=0.01)
    assert resp.status_code == 422
    assert "deactivated" in resp.json()["detail"].lower()


def test_reactivating_restores_trading(client, account):
    client.post(f"/venue-accounts/{account['id']}/active", params={"active": False})
    client.post(f"/venue-accounts/{account['id']}/active", params={"active": True})
    assert order(client, account["id"], size=0.01).status_code == 200


def test_closing_a_position(client, account):
    # 0.01 BTC sits under the default $1000 per-order ceiling; 0.02 would not.
    assert order(client, account["id"], size=0.01).json()["accepted"] is True
    resp = client.post(f"/venue-accounts/{account['id']}/close/BTC")
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True

    detail = client.get(f"/venue-accounts/{account['id']}").json()
    assert detail["positions"] == []


def test_closing_nothing_reports_why(client, account):
    resp = client.post(f"/venue-accounts/{account['id']}/close/ETH")
    assert resp.status_code == 200
    assert resp.json()["accepted"] is False


def test_orders_on_an_unknown_account_404(client):
    resp = order(client, 9999, size=0.01)
    assert resp.status_code == 404


def test_unlinking_removes_the_account(client, account, agent_id):
    assert client.delete(f"/venue-accounts/{account['id']}").status_code == 204
    assert client.get(f"/agents/{agent_id}/venues").json() == []
    assert client.get(f"/venue-accounts/{account['id']}").status_code == 404


# --- Factors over a venue ------------------------------------------------


def test_the_factor_library_is_listed(client):
    names = {f["name"] for f in client.get("/factors").json()}
    assert "momentum_12" in names
    assert all(f["description"] for f in client.get("/factors").json())


def test_a_symbol_can_be_scored(client):
    body = client.get("/factors/BTC").json()
    assert body["symbol"] == "BTC"
    assert body["candles"] > 0
    assert len(body["scores"]) == len(client.get("/factors").json())
    assert -1.0 <= body["signal"] <= 1.0


def test_one_factor_can_be_scored(client):
    body = client.get("/factors/BTC/momentum_12").json()
    assert body["factor"]["name"] == "momentum_12"
    assert "ic" in body["score"]


def test_an_unknown_factor_404s(client):
    assert client.get("/factors/BTC/not_a_factor").status_code == 404


def test_the_market_overview_covers_the_watchlist(client):
    rows = client.get("/factors/market", params={"symbols": "BTC,ETH"}).json()
    assert [r["symbol"] for r in rows] == ["BTC", "ETH"]
    assert all(r["price"] > 0 for r in rows)


def test_an_unpriceable_symbol_is_reported_not_dropped(client):
    """A watchlist typo should be visible, not silently missing."""
    rows = client.get("/factors/market", params={"symbols": "BTC,NOPE"}).json()
    assert len(rows) == 2
    assert rows[1]["symbol"] == "NOPE"
