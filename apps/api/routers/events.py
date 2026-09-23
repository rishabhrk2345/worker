"""
apps/api/routers/events.py

Phase 2/8 — Event journal APIs:
- GET /api/events         : query the journal (replay source of truth)
- GET /api/events/{id}    : single event by id
- GET /api/replay/{mission_run_id} : ordered replay feed (plan N-1/N-2)

Replay speed control (0.5x/1x/2x/10x) is a frontend concern; this endpoint
returns the ordered raw event stream with original timestamps.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.rbac import TenantContext, get_tenant_context
from models import EventJournal

router = APIRouter(prefix="/api", tags=["Events"])


def _event_dict(e: EventJournal) -> dict:
    return {
        "id": e.id,
        "organization_id": e.organization_id,
        "event_type": e.event_type,
        "schema_version": e.schema_version,
        "worker_id": e.worker_id,
        "worker_run_id": e.worker_run_id,
        "mission_id": e.mission_id,
        "task_id": e.task_id,
        "parent_task_id": e.parent_task_id,
        "correlation_id": e.correlation_id,
        "causation_id": e.causation_id,
        "trace_id": e.trace_id,
        "source_connection_id": e.source_connection_id,
        "entity_id": e.entity_id,
        "product_id": e.product_id,
        "logical_zone": e.logical_zone,
        "logical_station": e.logical_station,
        "dedupe_key": e.dedupe_key,
        "idempotency_key": e.idempotency_key,
        "sequence": e.sequence,
        "payload": e.payload,
        "metadata": e.metadata_json,
        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        "processed_at": e.processed_at.isoformat() if e.processed_at else None,
    }


@router.get("/events")
async def query_events(
    mission_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    worker_run_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    event_type: Optional[str] = None,
    after: Optional[datetime] = None,
    limit: int = Query(default=200, le=2000),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Queries the permanent event journal. Replay and debugging read from here,
    never from Redis (plan N-1: journal is the immutable store).
    """
    stmt = select(EventJournal).where(EventJournal.organization_id == ctx.organization_id)
    if mission_id:
        stmt = stmt.where(EventJournal.mission_id == mission_id)
    if worker_id:
        stmt = stmt.where(EventJournal.worker_id == worker_id)
    if worker_run_id:
        stmt = stmt.where(EventJournal.worker_run_id == worker_run_id)
    if correlation_id:
        stmt = stmt.where(EventJournal.correlation_id == correlation_id)
    if event_type:
        stmt = stmt.where(EventJournal.event_type == event_type)
    if after:
        stmt = stmt.where(EventJournal.occurred_at > after)

    stmt = stmt.order_by(EventJournal.occurred_at.asc(), EventJournal.sequence.asc()).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()
    return [_event_dict(e) for e in events]


@router.get("/events/{event_id}")
async def get_event(
    event_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(EventJournal).where(
        EventJournal.id == event_id,
        EventJournal.organization_id == ctx.organization_id,
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _event_dict(event)


@router.get("/replay/{mission_run_id}")
async def replay_mission_run(
    mission_run_id: str,
    speed: float = Query(default=1.0, description="Replay speed hint (0.5x-10x); timing applied client-side"),
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the ordered event stream for a mission run, with original
    timestamps preserved so the frontend ReplayController can pace playback
    at 0.5x / 1x / 2x / 10x (plan N-2).
    """
    stmt = (
        select(EventJournal)
        .where(
            EventJournal.mission_id == mission_run_id,
            EventJournal.organization_id == ctx.organization_id,
        )
        .order_by(EventJournal.occurred_at.asc(), EventJournal.sequence.asc())
        .limit(5000)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    first_ts = events[0].occurred_at if events else None
    last_ts = events[-1].occurred_at if events else None
    return {
        "mission_run_id": mission_run_id,
        "event_count": len(events),
        "started_at": first_ts.isoformat() if first_ts else None,
        "ended_at": last_ts.isoformat() if last_ts else None,
        "speed_hint": speed,
        "events": [_event_dict(e) for e in events],
    }
