"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from botmarket.db.models import Agent
from botmarket.db.session import get_db
from botmarket.domain.errors import Forbidden
from botmarket.services import agents as agents_service
from botmarket.services import apikeys

DbSession = Annotated[Session, Depends(get_db)]
"""A request-scoped database session, closed automatically after the response."""


def caller_agent(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Agent:
    """Resolve the agent behind the request's API key.

    Reads are open; every endpoint that changes state depends on this, so
    "which agent is acting?" is answered by a credential rather than by a path
    parameter anyone could type.

    Raises:
        Unauthorized: If no key was sent, or it matches no agent.
    """
    return agents_service.authenticate(db, apikeys.extract(authorization, x_api_key))


CallerAgent = Annotated[Agent, Depends(caller_agent)]
"""The authenticated agent making this request."""


def require_self(caller: Agent, agent_id: int) -> Agent:
    """Assert that ``caller`` is the agent it claims to be acting as.

    Authentication alone is not enough: a valid key proves *an* agent, and this
    proves it is *the* agent whose wallet, coins or venue account is about to
    move.

    Raises:
        Forbidden: If the key belongs to a different agent.
    """
    if caller.id != agent_id:
        raise Forbidden(
            f"This API key belongs to agent {caller.id} ({caller.name}), "
            f"not agent {agent_id}"
        )
    return caller
