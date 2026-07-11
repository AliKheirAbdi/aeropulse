"""
Thin wrapper around Redis pub/sub.

This is the event bus described in the architecture doc. Topics used:
  - flight.telemetry   flight status/position changes
  - incident.raised    new SLA-tracked incidents (manual or auto-triggered)
  - ticket.uploaded    OCR verification results

Swap-out note: for higher durability/replay guarantees at enterprise scale,
this module is a drop-in point to swap for a Kafka producer/consumer
(aiokafka) without changing any router code — routers only call publish().
"""
import os
import json
import asyncio
import logging
import redis.asyncio as aioredis

logger = logging.getLogger("aeropulse.bus")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHANNEL = "aeropulse_events"

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def publish(event_type: str, payload: dict):
    """Publish an event. Never raises — a Redis outage should degrade the
    live dashboard to polling, not break the request that triggered it."""
    try:
        client = get_redis()
        message = json.dumps({"event": event_type, "data": payload})
        await client.publish(CHANNEL, message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("event publish failed (%s): %s", event_type, exc)


async def subscribe_and_forward(on_message):
    """Long-running task: subscribes to the shared channel and calls
    on_message(dict) for every event received. Reconnects on failure."""
    while True:
        try:
            client = get_redis()
            pubsub = client.pubsub()
            await pubsub.subscribe(CHANNEL)
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                except json.JSONDecodeError:
                    continue
                await on_message(data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis subscriber lost connection, retrying in 3s: %s", exc)
            await asyncio.sleep(3)
