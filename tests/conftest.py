"""Shared pytest fixtures."""

import pytest
import fakeredis.aioredis


@pytest.fixture
async def redis():
    """Fake Redis for unit tests."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)
