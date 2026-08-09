"""Domain-level errors.

Services raise these instead of HTTP exceptions so the domain and service
layers stay transport-agnostic. :mod:`botmarket.api.errors` installs the
handlers that translate them into responses.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all recoverable domain failures."""


class NotFound(DomainError):
    """A referenced entity does not exist."""


class Conflict(DomainError):
    """The request conflicts with existing state (e.g. a duplicate name)."""


class InsufficientFunds(DomainError):
    """An agent lacks the credits, tokens or coins the action requires."""


class InvalidAction(DomainError):
    """The action is well-formed but not allowed in the current state."""


class Unauthorized(DomainError):
    """No usable credential was presented."""


class Forbidden(DomainError):
    """A valid credential was presented, but not for this agent.

    Kept distinct from :class:`Unauthorized` because the fixes differ: one means
    "send a key", the other means "you sent someone else's".
    """
