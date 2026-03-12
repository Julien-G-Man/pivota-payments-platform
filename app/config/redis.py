"""Redis connection pools — one logical DB per concern."""

import redis.asyncio as aioredis

from app.config.settings import settings


def get_redis_pool(db: int) -> aioredis.Redis:  # type: ignore[type-arg]
    return aioredis.from_url(
        settings.redis_url,
        db=db,
        encoding="utf-8",
        decode_responses=True,
    )


cache_redis = get_redis_pool(settings.redis_db_cache)
idempotency_redis = get_redis_pool(settings.redis_db_idempotency)
rate_limit_redis = get_redis_pool(settings.redis_db_rate_limit)
session_redis = get_redis_pool(settings.redis_db_sessions)
