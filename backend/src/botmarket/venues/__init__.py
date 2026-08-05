"""Concrete venues: where orders actually go.

Each module here adapts one execution target onto the protocols in
:mod:`botmarket.domain.venue`. Nothing above this package knows which venue it
is holding — that is the point of the abstraction, and it is what lets an agent
be moved from paper to a live exchange without touching its logic.
"""

from botmarket.venues.paper import PaperVenue
from botmarket.venues.registry import (
    VENUE_NAMES,
    build_market_data,
    build_venue,
    describe_venues,
)

__all__ = [
    "VENUE_NAMES",
    "PaperVenue",
    "build_market_data",
    "build_venue",
    "describe_venues",
]
