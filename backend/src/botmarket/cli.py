"""Command-line entrypoint for running the world without the HTTP API.

Installed as the ``botmarket`` command::

    botmarket seed          # create the starter roster of agents
    botmarket tick --count 10
    botmarket state
    botmarket reset         # drop every table and start over
    botmarket keygen        # print a VENUE_ENCRYPTION_KEY
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from botmarket.config import get_settings
from botmarket.db.session import Base, SessionLocal, engine, init_db
from botmarket.domain.errors import DomainError
from botmarket.repositories import agents as agents_repo
from botmarket.services import agents as agents_service
from botmarket.services import simulation as simulation_service


def _database_label() -> str:
    """Return the database this command will act on, resolved to a real path.

    The default ``DATABASE_URL`` is a *relative* SQLite path, so running the CLI
    from a different directory quietly targets a different database. Printing
    the resolved path turns that from a confusing no-op into an obvious one.
    """
    url = get_settings().database_url
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith(f"{prefix}/"):
        return f"{url}  ->  {Path(url[len(prefix):]).resolve()}"
    return url


STARTER_ROSTER: list[tuple[str, str]] = [
    ("trader", "Satoshi"),
    ("trader", "Ada"),
    ("meme", "Pepe"),
    ("meme", "Doge"),
    ("analyst", "Vitalik"),
    ("analyst", "Turing"),
]


def seed() -> int:
    """Create the starter agents. Idempotent: existing names are skipped."""
    init_db()
    created = 0
    with SessionLocal() as db:
        for agent_type, name in STARTER_ROSTER:
            if agents_repo.get_by_name(db, name) is not None:
                continue
            agents_service.register(db, agent_type=agent_type, name=name)
            created += 1
    print(f"Seed complete. Created {created} new agent(s).")
    print(f"Database: {_database_label()}")
    return 0


def tick(count: int) -> int:
    """Advance the simulation ``count`` ticks, printing a line per tick."""
    init_db()
    with SessionLocal() as db:
        if agents_repo.count(db) == 0:
            print("No agents registered — run `botmarket seed` first.", file=sys.stderr)
            return 1
        for _ in range(count):
            result = simulation_service.run_tick(db)
            event = result["event"]["description"] if result["event"] else "—"
            print(
                f"tick {result['tick']:>4} · $BOT {result['market_price']:>8.2f} · "
                f"{result['posts_created']} posts · {event}"
            )
    return 0


def state() -> int:
    """Print the current world snapshot."""
    init_db()
    with SessionLocal() as db:
        snapshot = simulation_service.state(db)
        print(
            f"tick {snapshot['tick']} · $BOT {snapshot['market_price']} · "
            f"trend {snapshot['market_trend']:+} · agents {snapshot['agents']}"
        )
        for i, row in enumerate(snapshot["leaderboard"][:5], start=1):
            print(f"  {i}. {row['name']:<12} net worth {row['net_worth']:>10.2f}")
    print(f"Database: {_database_label()}")
    return 0


def reset() -> int:
    """Drop and recreate every table."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    print(f"Reset complete. Database: {_database_label()}")
    return 0


def keygen() -> int:
    """Print a fresh encryption key for venue credentials.

    Printing rather than writing is deliberate: the operator decides where a
    key that protects trading credentials ends up, and a key silently appended
    to a file is a key nobody knows they need to back up. Losing it means
    re-linking every live account.
    """
    from botmarket.services.credentials import generate_key

    print(f"VENUE_ENCRYPTION_KEY={generate_key()}")
    print(
        "\nAdd this to your .env. Keep it safe and out of version control — "
        "it decrypts every stored exchange credential."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and dispatch to a subcommand."""
    parser = argparse.ArgumentParser(prog="botmarket", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("seed", help="create the starter roster of agents")
    tick_parser = sub.add_parser("tick", help="advance the simulation")
    tick_parser.add_argument("--count", type=int, default=1, help="number of ticks (default 1)")
    sub.add_parser("state", help="print the current world snapshot")
    sub.add_parser("reset", help="drop every table and start over")
    sub.add_parser("keygen", help="print a VENUE_ENCRYPTION_KEY for live trading")

    args = parser.parse_args(argv)
    try:
        if args.command == "seed":
            return seed()
        if args.command == "tick":
            return tick(args.count)
        if args.command == "state":
            return state()
        if args.command == "keygen":
            return keygen()
        return reset()
    except DomainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        # Something downstream stopped reading — `botmarket seed | head -1`, or
        # quitting a pager. That is a normal way to end a pipeline, not a
        # failure, so exit quietly instead of dumping a traceback.
        #
        # Python also flushes stdout at shutdown, which would raise a second
        # time and print "Exception ignored"; pointing the fd at /dev/null
        # gives that flush somewhere harmless to go.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
