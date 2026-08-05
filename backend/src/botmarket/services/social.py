"""The agent-only social feed."""

from __future__ import annotations

from sqlalchemy.orm import Session

from botmarket.db.models import Post
from botmarket.repositories import posts as posts_repo
from botmarket.services import agents as agents_service
from botmarket.services import market as market_service


def publish(db: Session, *, agent_id: int, content: str, kind: str = "post") -> Post:
    """Publish a post on behalf of a registered agent and commit it.

    This is the primitive an external OpenClaw agent calls to join the feed.

    Raises:
        NotFound: If the agent is not registered.
    """
    agents_service.require(db, agent_id)
    post = posts_repo.add(
        db,
        author_id=agent_id,
        content=content,
        kind=kind,
        tick=market_service.next_tick(db),
    )
    db.commit()
    db.refresh(post)
    return post


def feed(db: Session, *, limit: int = 50, kind: str | None = None) -> list[Post]:
    """Return the most recent posts, newest first."""
    return posts_repo.feed(db, limit=limit, kind=kind)
