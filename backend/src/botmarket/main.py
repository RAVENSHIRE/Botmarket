"""BOTMARKET FastAPI application entrypoint.

Wires configuration, database initialisation, CORS, domain-error handling and
the API router into a single ASGI app. Run locally with::

    uvicorn botmarket.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from botmarket import __version__
from botmarket.api import errors
from botmarket.api.routers import router
from botmarket.config import get_settings
from botmarket.db.session import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "An autonomous agent economy: agents trade the native $BOT token, "
        "launch memecoins on bonding curves, tip each other, and govern the "
        "simulation through funded proposals."
    ),
    version=__version__,
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

errors.install(app)
app.include_router(router)
