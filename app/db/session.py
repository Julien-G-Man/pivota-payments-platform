"""Database session dependencies for FastAPI injection."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionPrimary, AsyncSessionReplica, AsyncSessionAI


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Primary DB — use for all writes."""
    async with AsyncSessionPrimary() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Read replica — analytics, AI context, reports. Never use for writes."""
    async with AsyncSessionReplica() as session:
        yield session


async def get_ai_db() -> AsyncGenerator[AsyncSession, None]:
    """AI readonly role — pgvector queries only. SELECT-only Postgres role."""
    async with AsyncSessionAI() as session:
        yield session
