"""Social post persistence.

Keeping these in a dedicated module (rather than inline in the API) means the
simulation engine and the HTTP layer share one code path for writing the feed.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from botmarket.db.models import Post


def add(db: Session, *, author_id: int, content: str, kind: str = "post", tick: int = 0) -> Post:
    """Persist a new post and return it with its primary key assigned."""
    post = Post(author_id=author_id, content=content, kind=kind, tick=tick)
    db.add(post)
    db.flush()
    return post


def feed(db: Session, *, limit: int = 50, kind: str | None = None) -> list[Post]:
    """Return the most recent posts, newest first, optionally filtered by kind."""
    stmt = select(Post).order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)
    if kind:
        stmt = stmt.where(Post.kind == kind)
    return list(db.scalars(stmt))


def by_author(db: Session, author_id: int, *, limit: int = 20) -> list[Post]:
    """Return one agent's most recent posts, newest first."""
    stmt = (
        select(Post)
        .where(Post.author_id == author_id)
        .order_by(Post.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
