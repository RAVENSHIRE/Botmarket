"""Building the right venue for an account.

This is the only place that maps a stored ``VenueAccount`` onto a live object.
Keeping it in one function means the rule "a mainnet account gets a mainnet
client, always" is written once and cannot drift between call sites.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.config import get_settings
from botmarket.db.models import VenueAccount
from botmarket.domain.errors import InvalidAction, NotFound
from botmarket.domain.venue import Environment, ExecutionVenue, MarketDataFeed
from botmarket.services import credentials
from botmarket.venues import alpaca as alp
from botmarket.venues import hyperliquid as hl
from botmarket.venues.paper import PaperMarketData, PaperVenue

VENUE_NAMES = ("paper", "hyperliquid", "alpaca")

#: Which environments each venue is allowed to run in.
VENUE_ENVIRONMENTS: dict[str, tuple[Environment, ...]] = {
    "paper": (Environment.PAPER,),
    "hyperliquid": (Environment.TESTNET, Environment.MAINNET),
    # Alpaca's own paper endpoint maps onto testnet, so it inherits the same
    # gating and `mainnet` stays the only setting that can lose money.
    "alpaca": (Environment.TESTNET, Environment.MAINNET),
}

#: What each venue calls the public half of its credential, for the UI.
CREDENTIAL_LABELS: dict[str, tuple[str, str]] = {
    "hyperliquid": ("Wallet address", "Private key"),
    "alpaca": ("API key ID", "API secret key"),
}


def parse_environment(value: str) -> Environment:
    """Return the :class:`Environment` named by ``value``.

    Raises:
        InvalidAction: If the name is not a known environment.
    """
    try:
        return Environment(value)
    except ValueError as exc:
        known = ", ".join(e.value for e in Environment)
        raise InvalidAction(f"Unknown environment '{value}'. Expected one of: {known}") from exc


def validate_pairing(venue: str, environment: Environment) -> None:
    """Check that ``venue`` can run in ``environment``.

    Raises:
        InvalidAction: If the pairing is impossible, or mainnet is disabled.
    """
    allowed = VENUE_ENVIRONMENTS.get(venue)
    if allowed is None:
        raise InvalidAction(
            f"Unknown venue '{venue}'. Expected one of: {', '.join(VENUE_NAMES)}"
        )
    if environment not in allowed:
        names = ", ".join(e.value for e in allowed)
        raise InvalidAction(f"Venue '{venue}' only supports: {names}")
    if environment.is_real_money and not get_settings().allow_mainnet:
        raise InvalidAction(
            "Mainnet is disabled in this deployment. Set ALLOW_MAINNET=true "
            "only when you intend to trade real money."
        )


def build_venue(db: Session, account: VenueAccount) -> ExecutionVenue:
    """Return a live venue object for ``account``.

    Raises:
        InvalidAction: If the account is deactivated, or its venue cannot be
            constructed (missing credentials, missing optional dependency).
    """
    if not account.active:
        raise InvalidAction(
            f"Venue account {account.id} is deactivated and cannot trade"
        )

    environment = parse_environment(account.environment)
    validate_pairing(account.venue, environment)

    if account.venue == "paper":
        return PaperVenue(db, account)

    if account.venue == "hyperliquid":
        if not account.wallet_address:
            raise InvalidAction("This Hyperliquid account has no wallet address")
        secret = (
            credentials.open_secret(account.encrypted_secret)
            if account.encrypted_secret
            else None
        )
        clients = hl.build_clients(
            environment=environment,
            address=account.wallet_address,
            secret_key=secret,
        )
        return hl.HyperliquidVenue(
            clients, environment=environment, address=account.wallet_address
        )

    if account.venue == "alpaca":
        if not account.wallet_address:
            raise InvalidAction("This Alpaca account has no API key ID")
        if not account.encrypted_secret:
            raise InvalidAction(
                "This Alpaca account has no secret key, so it cannot trade. "
                "Re-link it with both the key ID and the secret."
            )
        transport = alp.build_transport(
            key_id=account.wallet_address,
            secret_key=credentials.open_secret(account.encrypted_secret),
        )
        return alp.AlpacaVenue(transport, environment=environment)

    raise NotFound(f"No venue implementation for '{account.venue}'")


def build_market_data(venue: str, environment: Environment) -> MarketDataFeed:
    """Return a read-only market data feed for a venue and environment.

    Market data needs no credentials, so this works for a symbol nobody has
    linked an account to — which is what lets the factor library be explored
    before any account exists.
    """
    validate_pairing(venue, environment)

    if venue == "paper":
        return PaperMarketData()

    if venue == "alpaca":
        # Alpaca gates market data behind the same credentials as trading, so
        # there is no anonymous feed to hand back.
        raise InvalidAction(
            "Alpaca market data needs credentials; read it through a linked "
            "account rather than anonymously."
        )

    clients = hl.build_clients(environment=environment, address="", secret_key=None)
    return hl.HyperliquidMarketData(clients, environment=environment)


def describe_venues() -> list[dict]:
    """Describe the venues this deployment can use, for the API and dashboard."""
    settings = get_settings()
    return [
        {
            "name": name,
            "environments": [e.value for e in VENUE_ENVIRONMENTS[name]],
            "requires_credentials": name != "paper",
            "available": name == "paper" or credentials.is_configured(),
            "mainnet_allowed": settings.allow_mainnet,
            "public_label": CREDENTIAL_LABELS.get(name, ("", ""))[0],
            "secret_label": CREDENTIAL_LABELS.get(name, ("", ""))[1],
        }
        for name in VENUE_NAMES
    ]
