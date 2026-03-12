"""Tests for app.core.idempotency — 100% coverage required."""

import pytest
import fakeredis.aioredis

from app.core.idempotency import check_and_set, mark_complete


@pytest.fixture
async def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_first_call_is_new(redis):
    result = await check_and_set("test:tx-1", redis)
    assert result.is_new is True
    assert result.cached_response is None


async def test_duplicate_call_is_not_new(redis):
    await check_and_set("test:tx-2", redis)
    result = await check_and_set("test:tx-2", redis)
    assert result.is_new is False


async def test_cached_response_returned(redis):
    await check_and_set("test:tx-3", redis)
    await mark_complete("test:tx-3", redis, response={"status": "ok"})
    result = await check_and_set("test:tx-3", redis)
    assert result.is_new is False
    assert result.cached_response == {"status": "ok"}
