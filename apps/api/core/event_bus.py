"""
apps/api/core/event_bus.py

Phase 2 — Event Bus abstraction (ADR-002).

EventBusPort is the ONLY interface business logic may depend on. The
RedisStreamsEventBus implementation can later be swapped for a KafkaEventBus
with zero business logic changes (plan Part 1, audit item A-3).
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)


class EventBusPort(ABC):
    """
    Port (interface) for real-time event delivery. Delivery is optimistic:
    the permanent record lives in the event_journal table, not on the bus.
    """

    @abstractmethod
    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        """Publish a serialized event dict to a channel/stream."""

    @abstractmethod
    async def subscribe(
        self,
        channel: str,
        callback,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Register a subscription. Returns a subscription id.

        filters (server-side fan-out filtering, plan L-2):
          - mission_ids: List[str]   -> event.mission_id must be in list
          - worker_ids: List[str]    -> event.worker_id must be in list
          - zones: List[str]         -> event.logical_zone must be in list
        """

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a previously registered subscription."""

    @abstractmethod
    async def close(self) -> None:
        """Flush and release bus resources."""


class InMemoryEventBus(EventBusPort):
    """
    In-process pub/sub bus used for tests, local development without Redis,
    and the simulation engine. Deterministic: subscribers receive events in
    publish order within the same event loop.
    """

    def __init__(self) -> None:
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._channel_subs: Dict[str, Set[str]] = defaultdict(set)
        self._seq = 0
        self._history: Deque[Dict[str, Any]] = deque(maxlen=5000)

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        self._history.append({"channel": channel, "event": event, "ts": time.time()})
        dead_subs: List[str] = []
        for sub_id in list(self._channel_subs.get(channel, set())):
            sub = self._subscriptions.get(sub_id)
            if not sub:
                continue
            if not self._matches_filters(event, sub.get("filters")):
                continue
            try:
                result = sub["callback"](event)
                # Support both sync and async callbacks
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                dead_subs.append(sub_id)
                logger.exception("event_bus_subscriber_failed", subscription_id=sub_id)
        for sub_id in dead_subs:
            await self.unsubscribe(sub_id)

    @staticmethod
    def _matches_filters(event: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
        if not filters:
            return True
        mission_ids = filters.get("mission_ids")
        if mission_ids and event.get("mission_id") not in mission_ids:
            return False
        worker_ids = filters.get("worker_ids")
        if worker_ids and event.get("worker_id") not in worker_ids:
            return False
        zones = filters.get("zones")
        if zones and event.get("logical_zone") not in zones:
            return False
        return True

    async def subscribe(
        self,
        channel: str,
        callback,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        self._seq += 1
        sub_id = f"sub-{self._seq}"
        self._subscriptions[sub_id] = {
            "channel": channel,
            "callback": callback,
            "filters": filters or {},
        }
        self._channel_subs[channel].add(sub_id)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        sub = self._subscriptions.pop(subscription_id, None)
        if sub:
            self._channel_subs[sub["channel"]].discard(subscription_id)

    async def close(self) -> None:
        self._subscriptions.clear()
        self._channel_subs.clear()

    @property
    def history(self) -> Deque[Dict[str, Any]]:
        """Recent deliveries, for tests and debugging."""
        return self._history


class RedisStreamsEventBus(EventBusPort):
    """
    Redis Streams implementation of EventBusPort (Phase 0-11 per plan).
    Streams provide at-least-once delivery with consumer groups; the event
    journal remains the durable source of truth (ADR-002).
    """

    def __init__(self, redis_url: str, stream_prefix: str = "events") -> None:
        self._redis_url = redis_url
        self._stream_prefix = stream_prefix
        self._redis = None
        self._subscriptions: Dict[str, Dict[str, Any]] = {}
        self._seq = 0

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis  # lazy import: optional dependency
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _stream_name(self, channel: str) -> str:
        return f"{self._stream_prefix}:{channel}"

    async def publish(self, channel: str, event: Dict[str, Any]) -> None:
        redis = await self._get_redis()
        await redis.xadd(
            self._stream_name(channel),
            {"payload": json.dumps(event, default=str)},
        )

    async def subscribe(
        self,
        channel: str,
        callback,
        filters: Optional[Dict[str, Any]] = None,
    ) -> str:
        # Real Redis fan-out with consumer groups is handled by the WebSocket
        # layer reading XREAD; direct callbacks are only wired for the
        # in-memory bus. Subscription ids are still issued for API symmetry.
        self._seq += 1
        sub_id = f"redis-sub-{self._seq}"
        self._subscriptions[sub_id] = {
            "channel": channel,
            "callback": callback,
            "filters": filters or {},
        }
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        self._subscriptions.pop(subscription_id, None)

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def read_since(self, channel: str, last_id: str = "0", count: int = 100) -> List[Dict[str, Any]]:
        """Read events from the stream after last_id (reconnect reconciliation helper)."""
        redis = await self._get_redis()
        rows = await redis.xread({self._stream_name(channel): last_id}, count=count, block=0)
        events: List[Dict[str, Any]] = []
        for _stream, entries in rows:
            for _entry_id, fields in entries:
                try:
                    events.append(json.loads(fields.get("payload", "{}")))
                except json.JSONDecodeError:
                    logger.warning("event_bus_malformed_payload", channel=channel)
        return events


async def get_event_bus() -> EventBusPort:
    """
    Bus factory. Uses Redis Streams when REDIS_URL is configured, the redis
    package is installed, AND the server answers a ping; otherwise falls back
    to the in-memory bus so tests and offline development remain functional.
    Must be awaited from a running event loop (app startup).
    """
    from .config import settings

    if settings.REDIS_URL:
        try:
            import redis.asyncio  # noqa: F401
        except ImportError:
            logger.warning("redis_package_missing_falling_back_to_inmemory_bus")
            return InMemoryEventBus()

        bus = RedisStreamsEventBus(settings.REDIS_URL)

        async def _ping() -> bool:
            redis = await bus._get_redis()
            return await redis.ping()

        try:
            await asyncio.wait_for(_ping(), timeout=1.5)
            return bus
        except Exception as exc:  # connection refused, timeout, DNS, etc.
            logger.warning(
                "redis_unreachable_falling_back_to_inmemory_bus", error=str(exc)
            )
            return InMemoryEventBus()
    return InMemoryEventBus()
