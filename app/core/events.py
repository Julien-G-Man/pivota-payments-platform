"""Redis Streams publisher for inter-domain events."""

import json
from datetime import datetime, timezone

from redis.asyncio import Redis

# Streams used across the application
STREAM_TRANSACTIONS = "transactions"
STREAM_COMPLIANCE = "compliance"
STREAM_REPORTS = "reports"
STREAM_AUTH = "auth"
STREAM_DLQ = "dlq:events"


async def publish(
    stream: str,
    event_type: str,
    payload: dict,  # type: ignore[type-arg]
    redis: Redis,  # type: ignore[type-arg]
) -> None:
    """
    Publish an event to a Redis Stream.

    Streams:
      - "transactions" → event_type: "transaction.created"
      - "compliance"   → event_type: "aml.flagged", "kyc.approved", "kyc.rejected"
      - "reports"      → event_type: "report.ready"
      - "auth"         → event_type: "login.failed", "password.reset"
      - "dlq:events"   → event_type: "job.failed"
    """
    event = {
        "event_type": event_type,
        "payload": json.dumps(payload),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await redis.xadd(stream, event)
