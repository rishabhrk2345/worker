"""
apps/api/tests/test_phase2_events.py

Phase 2 verification (plan Part 10):
- Publish same idempotency_key twice -> 1 journal row
- Same dedupe_key -> second event rejected
- Events retrieved in sequence order per worker
- Bus receives exactly one delivery per accepted event
- Server-side subscription filtering (plan L-2)
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.event_bus import InMemoryEventBus
from core.event_publisher import EventPublisher
from models import EventJournal, Organization


def make_event(**overrides) -> dict:
    base = {
        "event_type": "worker.state_changed",
        "organization_id": "00000000-0000-0000-0000-000000000001",
        "worker_id": str(uuid.uuid4()),
        "worker_run_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "idempotency_key": f"idem-{uuid.uuid4()}",
        "sequence": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {"to_state": "SEARCHING"},
    }
    base.update(overrides)
    return base


@pytest.fixture
async def bus():
    bus = InMemoryEventBus()
    yield bus
    await bus.close()


@pytest.mark.asyncio
async def test_event_idempotency_single_journal_row(test_db: AsyncSession, bus):
    """Publish same idempotency_key twice -> journal has exactly 1 row."""
    org = Organization(id="00000000-0000-0000-0000-000000000001", name="T", slug="t")
    test_db.add(org)
    await test_db.flush()

    publisher = EventPublisher(test_db, bus=bus)
    event = make_event()

    first = await publisher.publish(event)
    second = await publisher.publish(dict(event))  # same idempotency_key

    assert first is True
    assert second is False

    from sqlalchemy import select, func
    count = (
        await test_db.execute(
            select(func.count()).select_from(EventJournal).where(
                EventJournal.idempotency_key == event["idempotency_key"]
            )
        )
    ).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_duplicate_dedupe_key_rejected(test_db: AsyncSession, bus):
    """Same dedupe_key (different idempotency keys) -> second rejected."""
    org = Organization(id="00000000-0000-0000-0000-000000000002", name="T2", slug="t2")
    test_db.add(org)
    await test_db.flush()

    publisher = EventPublisher(test_db, bus=bus)
    dedupe = "sha256:same-work-same-run"
    e1 = make_event(organization_id=org.id, dedupe_key=dedupe)
    e2 = make_event(organization_id=org.id, dedupe_key=dedupe)

    assert await publisher.publish(e1) is True
    assert await publisher.publish(e2) is False


@pytest.mark.asyncio
async def test_bus_receives_one_delivery_per_accepted_event(test_db: AsyncSession, bus):
    """Accepted event -> exactly one bus delivery; duplicate -> zero."""
    org = Organization(id="00000000-0000-0000-0000-000000000003", name="T3", slug="t3")
    test_db.add(org)
    await test_db.flush()

    delivered = []
    await bus.subscribe("org:00000000-0000-0000-0000-000000000003", lambda e: delivered.append(e))

    publisher = EventPublisher(test_db, bus=bus)
    event = make_event(organization_id=org.id)
    await publisher.publish(event)
    await publisher.publish(dict(event))

    assert len(delivered) == 1
    assert delivered[0]["idempotency_key"] == event["idempotency_key"]


@pytest.mark.asyncio
async def test_journal_ordering_by_sequence(test_db: AsyncSession, bus):
    """Events retrieved in (occurred_at, sequence) order per worker run."""
    org = Organization(id="00000000-0000-0000-0000-000000000004", name="T4", slug="t4")
    test_db.add(org)
    await test_db.flush()

    publisher = EventPublisher(test_db, bus=bus)
    run_id = str(uuid.uuid4())
    for seq in [3, 1, 2]:
        await publisher.publish(
            make_event(
                organization_id=org.id,
                worker_run_id=run_id,
                sequence=seq,
                occurred_at=datetime(2026, 1, 1, 12, 0, seq, tzinfo=timezone.utc).isoformat(),
            )
        )

    rows = await publisher.replay_events(org.id, worker_run_id=run_id)
    sequences = [r.sequence for r in rows]
    assert sequences == sorted(sequences)
    assert set(sequences) == {1, 2, 3}


@pytest.mark.asyncio
async def test_subscription_filtering_mission_scope(bus):
    """A subscription filtered to mission A never receives mission B events."""
    delivered = []
    await bus.subscribe(
        "org:x",
        lambda e: delivered.append(e),
        filters={"mission_ids": ["mission-A"]},
    )

    await bus.publish("org:x", {"mission_id": "mission-A", "worker_id": "w"})
    await bus.publish("org:x", {"mission_id": "mission-B", "worker_id": "w"})
    await bus.publish("org:x", {"mission_id": None, "worker_id": "w"})

    assert len(delivered) == 1
    assert delivered[0]["mission_id"] == "mission-A"


@pytest.mark.asyncio
async def test_missing_required_field_raises(test_db: AsyncSession, bus):
    publisher = EventPublisher(test_db, bus=bus)
    bad = make_event()
    bad.pop("worker_id")
    with pytest.raises(ValueError):
        await publisher.publish(bad)
