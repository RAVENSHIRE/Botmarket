"""Social posts service.

Thin persistence helpers for creating and reading agent posts. Keeping these
in a dedicated module (rather than inline in the API) means the simulation
engine and the API share one code path for writing the feed.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Post


def create_post(
    db: Session, *, author_id: int, content: str, kind: str = "post", tick: int = 0
) -> Post:
    """Persist a new post and return it."""
    post = Post(author_id=author_id, content=content, kind=kind, tick=tick)
    db.add(post)
    db.flush()  # assign PK without committing the outer transaction
    return post


def get_feed(db: Session, *, limit: int = 50) -> list[Post]:
    """Return the most recent posts, newest first."""
    stmt = select(Post).order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)
    return list(db.scalars(stmt))
