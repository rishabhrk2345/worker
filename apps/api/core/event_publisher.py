"""
apps/api/core/event_publisher.py

Phase 2 — EventPublisher: the ONLY sanctioned path for publishing workforce events.

Order of operations (ADR-002):
1. Persist to the immutable event_journal (durable record, replay source).
2. Publish to the EventBusPort for real-time fan-out (optimistic delivery).

Idempotency and deduplication are enforced by unique constraints on
event_journal.idempotency_key and event_journal.dedupe_key.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal
from .event_bus import EventBusPort, InMemoryEventBus

logger = structlog.get_logger(__name__)

# Module-level default bus so that the WebSocket layer and simulation engine
# observe the same stream the publisher writes to.
_default_bus: Optional[EventBusPort] = None


def get_default_bus() -> EventBusPort:
    global _default_bus
    if _default_bus is None:
        _default_bus = InMemoryEventBus()
    return _default_bus


def set_default_bus(bus: EventBusPort) -> None:
    """Replace the process-wide default bus (used by app startup / tests)."""
    global _default_bus
    _default_bus = bus


class EventPublisher:
    """
    Journal-first event publisher with idempotency + deduplication.

    Usage:
        publisher = EventPublisher(db_session)
        stored = await publisher.publish(event_dict)
        # stored is False when the event was a duplicate (idempotency/dedupe hit)
    """

    def __init__(self, session: Optional[AsyncSession] = None, bus: Optional[EventBusPort] = None) -> None:
        self._session = session
        self._bus = bus or get_default_bus()

    async def publish(self, event: Dict[str, Any]) -> bool:
        """
        Persist event to the journal, then fan out on the bus.
        Returns True if stored, False if rejected as duplicate.
        """
        # Envelope normalization & defaults
        event.setdefault("schema_version", "1.0")
        event.setdefault("metadata", {})
        event.setdefault("payload", {})
        if "event_id" not in event or not event["event_id"]:
            event["event_id"] = str(uuid.uuid4())
        if "occurred_at" not in event or not event["occurred_at"]:
            event["occurred_at"] = datetime.now(timezone.utc).isoformat()
        for required in ("event_type", "worker_id", "worker_run_id", "correlation_id", "idempotency_key"):
            if required not in event or event[required] is None:
                raise ValueError(f"WorkerEvent envelope missing required field: {required}")

        row = EventJournal(
            id=event["event_id"],
            organization_id=event["organization_id"],
            event_type=event["event_type"],
            schema_version=event.get("schema_version", "1.0"),
            worker_id=event["worker_id"],
            worker_run_id=event["worker_run_id"],
            mission_id=event.get("mission_id"),
            task_id=event.get("task_id"),
            parent_task_id=event.get("parent_task_id"),
            correlation_id=event["correlation_id"],
            causation_id=event.get("causation_id"),
            trace_id=event.get("trace_id"),
            span_id=event.get("span_id"),
            source_connection_id=event.get("source_connection_id"),
            entity_id=event.get("entity_id"),
            product_id=event.get("product_id"),
            logical_zone=event.get("logical_zone"),
            logical_station=event.get("logical_station"),
            dedupe_key=event.get("dedupe_key"),
            idempotency_key=event["idempotency_key"],
            sequence=event.get("sequence", 0),
            payload=event.get("payload") or {},
            metadata_json=event.get("metadata") or {},
            occurred_at=_parse_dt(event["occurred_at"]),
        )

        session = self._session
        if session is None:
            # Publisher owns a short-lived session/transaction
            async with AsyncSessionLocal() as owned_session:
                return await self._persist_and_publish(owned_session, row, event)
        return await self._persist_and_publish(session, row, event)

    async def _persist_and_publish(
        self, session: AsyncSession, row: EventJournal, event: Dict[str, Any]
    ) -> bool:
        # SAVEPOINT: a duplicate (unique-constraint hit) must not poison the
        # caller's outer transaction — only the savepoint rolls back.
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            logger.info(
                "event_duplicate_rejected",
                event_type=event["event_type"],
                idempotency_key=event["idempotency_key"],
                dedupe_key=event.get("dedupe_key"),
            )
            return False

        channel = f"org:{event['organization_id']}"
        await self._bus.publish(channel, event)
        logger.info(
            "event_published",
            event_type=event["event_type"],
            event_id=event["event_id"],
            sequence=event.get("sequence", 0),
        )
        return True

    async def replay_events(
        self,
        organization_id: str,
        mission_id: Optional[str] = None,
        worker_run_id: Optional[str] = None,
        after: Optional[datetime] = None,
        limit: int = 1000,
    ):
        """Read events from the journal in (occurred_at, sequence) order — replay source of truth."""
        session = self._session or AsyncSessionLocal()
        try:
            stmt = select(EventJournal).where(EventJournal.organization_id == organization_id)
            if mission_id:
                stmt = stmt.where(EventJournal.mission_id == mission_id)
            if worker_run_id:
                stmt = stmt.where(EventJournal.worker_run_id == worker_run_id)
            if after:
                stmt = stmt.where(EventJournal.occurred_at > after)
            stmt = stmt.order_by(EventJournal.occurred_at.asc(), EventJournal.sequence.asc()).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()
        finally:
            if not self._session:
                await session.close()


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


# Imported late to avoid a circular import at module load time
from models.event_journal import EventJournal  # noqa: E402
