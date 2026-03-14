"""Application startup and shutdown lifecycle."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run on startup, yield, then run on shutdown."""
    logger.info("Pivota starting up")
    # TODO: initialise DB connection pools, Redis, Celery beat healthcheck
    yield
    logger.info("Pivota shutting down")
    # TODO: gracefully close connection pools
