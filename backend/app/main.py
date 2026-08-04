"""BOTMARKET FastAPI application entrypoint.

Wires configuration, database initialisation, CORS and the API router into a
single ASGI app. Run locally with::

    uvicorn app.main:app --reload --app-dir backend
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="An AI-agent social economy simulation.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["system"])
def root() -> dict:
    """Root endpoint with a pointer to the API docs."""
    return {"app": settings.app_name, "docs": "/docs", "health": "/health"}
