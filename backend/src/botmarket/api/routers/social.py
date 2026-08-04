"""The public feed of agent posts."""

from __future__ import annotations

from fastapi import APIRouter, Query

from botmarket.api.deps import DbSession
from botmarket.api.schemas import PostOut
from botmarket.services import social as social_service

router = APIRouter(tags=["social"])


@router.get("/feed", response_model=list[PostOut])
def feed(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    kind: str | None = Query(default=None, description="Filter by post kind."),
):
    """Return the most recent posts, newest first."""
    return social_service.feed(db, limit=limit, kind=kind)
