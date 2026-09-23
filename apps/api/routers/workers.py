"""
apps/api/routers/workers.py

REST API endpoints for Worker fleet management and real-time state inspection.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.rbac import TenantContext, get_tenant_context, require_permission
from core.worker_state_machine import WorkerStateMachine, WorkerStateTransitionError
from models import Worker, WorkerType, WorkerRun

router = APIRouter(prefix="/api/workers", tags=["Workers"])


class WorkerTransitionRequest(BaseModel):
    target_state: str = Field(min_length=2, max_length=50)
    reason: Optional[str] = None

@router.get("")
async def list_workers(
    zone: Optional[str] = None,
    status_filter: Optional[str] = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all workers within the caller's organization, optionally filtered by zone or status.
    """
    query = select(Worker).where(Worker.organization_id == ctx.organization_id)
    if zone:
        query = query.where(Worker.logical_zone == zone)
    if status_filter:
        query = query.where(Worker.status == status_filter)

    result = await db.execute(query)
    workers = result.scalars().all()

    return [
        {
            "id": w.id,
            "name": w.name,
            "worker_type_id": w.worker_type_id,
            "status": w.status,
            "logical_zone": w.logical_zone,
            "logical_station": w.logical_station,
            "current_source": w.current_source,
            "current_url": w.current_url,
            "autonomy_level": w.autonomy_level,
            "current_mission_id": w.current_mission_id,
            "current_task_id": w.current_task_id,
        }
        for w in workers
    ]

@router.get("/{worker_id}")
async def get_worker_detail(
    worker_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns detailed state, metrics, and active task of a specific worker.
    """
    stmt = select(Worker).where(
        Worker.id == worker_id,
        Worker.organization_id == ctx.organization_id
    )
    res = await db.execute(stmt)
    worker = res.scalar_one_or_none()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    return {
        "id": worker.id,
        "name": worker.name,
        "worker_type_id": worker.worker_type_id,
        "status": worker.status,
        "logical_zone": worker.logical_zone,
        "logical_station": worker.logical_station,
        "current_source": worker.current_source,
        "current_url": worker.current_url,
        "autonomy_level": worker.autonomy_level,
        "current_mission_id": worker.current_mission_id,
        "current_task_id": worker.current_task_id,
        "created_at": worker.created_at.isoformat(),
        "updated_at": worker.updated_at.isoformat()
    }


@router.post("/{worker_id}/transition")
async def transition_worker_state(
    worker_id: str,
    req: WorkerTransitionRequest,
    ctx: TenantContext = Depends(require_permission("worker:write")),
    db: AsyncSession = Depends(get_db),
):
    """
    Applies a contract-validated state transition to a worker.
    Illegal transitions (per contracts/enums/worker_state.json) are rejected
    with 409 and never persisted (plan Part 6).
    """
    stmt = select(Worker).where(
        Worker.id == worker_id, Worker.organization_id == ctx.organization_id
    )
    result = await db.execute(stmt)
    worker = result.scalar_one_or_none()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    machine = WorkerStateMachine(worker.id, worker.current_task_id or worker.id, worker.status)
    try:
        payload = machine.transition(req.target_state, reason=req.reason)
    except WorkerStateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    worker.status = machine.state.value
    await db.commit()
    return {
        "worker_id": worker.id,
        "previous_state": payload["from_state"],
        "current_state": payload["to_state"],
        "reason": payload["reason"],
        "animation": payload["animation"],
    }
