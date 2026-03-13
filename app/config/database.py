"""SQLAlchemy async engine and session factory configuration."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import settings

engine_primary = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    echo=settings.debug,
)

engine_replica = create_async_engine(
    settings.database_replica_url or settings.database_url,
    pool_size=10,
    pool_pre_ping=True,
)

engine_ai_readonly = create_async_engine(
    settings.database_url.replace("pivota_app", "pivota_ai")
    if settings.database_url
    else "",
    pool_size=5,
    pool_pre_ping=True,
)

AsyncSessionPrimary: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine_primary, expire_on_commit=False
)
AsyncSessionReplica: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine_replica, expire_on_commit=False
)
AsyncSessionAI: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine_ai_readonly, expire_on_commit=False
)
