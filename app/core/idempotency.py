"""
Redis SET NX idempotency primitive.

Every MoMo transaction write must call check_and_set() first. See CLAUDE.md Rule 2.
"""

import json
from dataclasses import dataclass
from typing import Optional

from redis.asyncio import Redis


@dataclass
class IdempotencyResult:
    is_new: bool
    cached_response: Optional[dict]  # type: ignore[type-arg]


async def check_and_set(
    key: str,
    redis: Redis,  # type: ignore[type-arg]
    ttl_seconds: int = 86400,
) -> IdempotencyResult:
    """
    Atomically check if key exists and set it if not.

    Returns IdempotencyResult(is_new=True) on first call.
    Returns IdempotencyResult(is_new=False, cached_response=...) on repeat calls.

    Usage:
        result = await check_and_set(f"momo:{tx_id}", redis)
        if not result.is_new:
            return result.cached_response
        # process ...
        await mark_complete(f"momo:{tx_id}", redis, response=your_response)
    """
    full_key = f"idempotency:{key}"
    was_set = await redis.set(full_key, "processing", nx=True, ex=ttl_seconds)

    if was_set:
        return IdempotencyResult(is_new=True, cached_response=None)

    value = await redis.get(full_key)
    if value and value != b"processing":
        try:
            cached = json.loads(value)
            return IdempotencyResult(is_new=False, cached_response=cached)
        except json.JSONDecodeError:
            pass

    return IdempotencyResult(is_new=False, cached_response=None)


async def mark_complete(
    key: str,
    redis: Redis,  # type: ignore[type-arg]
    response: dict,  # type: ignore[type-arg]
    ttl_seconds: int = 86400,
) -> None:
    """Store the final response for the idempotency key."""
    full_key = f"idempotency:{key}"
    await redis.set(full_key, json.dumps(response), ex=ttl_seconds)
