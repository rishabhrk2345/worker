"""
apps/api/routers/tasks.py

Phase 3 — REST API for the WorkerTask queue: list ready/blocked tasks,
create tasks, and mark tasks complete/failed. Dependency resolution and
budget state are surfaced here for orchestration.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.rbac import TenantContext, get_tenant_context, require_permission
from core.task_orchestration import resolve_task_dependencies
from models import WorkerTask

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


class TaskCreateRequest(BaseModel):
    worker_type_required: str = Field(min_length=1, max_length=50)
    type: str = Field(min_length=1, max_length=100)
    mission_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    priority: str = "normal"
    input_data: dict = Field(default_factory=dict)
    expected_output: dict = Field(default_factory=dict)
    budget: dict = Field(default_factory=dict)
    retry_policy: dict = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)


def _task_dict(t: WorkerTask) -> dict:
    return {
        "id": t.id,
        "mission_id": t.mission_id,
        "parent_task_id": t.parent_task_id,
        "worker_id": t.worker_id,
        "worker_type_required": t.worker_type_required,
        "type": t.type,
        "priority": t.priority,
        "status": t.status,
        "input_data": t.input_data,
        "budget": t.budget,
        "retry_policy": t.retry_policy,
        "dependencies": t.dependencies,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "result_data": t.result_data,
        "failure_reason": t.failure_reason,
    }


@router.get("")
async def list_tasks(
    mission_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WorkerTask).where(WorkerTask.organization_id == ctx.organization_id)
    if mission_id:
        stmt = stmt.where(WorkerTask.mission_id == mission_id)
    if status_filter:
        stmt = stmt.where(WorkerTask.status == status_filter)
    result = await db.execute(stmt.order_by(WorkerTask.created_at.desc()).limit(500))
    tasks = result.scalars().all()
    return [_task_dict(t) for t in tasks]


@router.get("/schedule/resolve")
async def resolve_schedule(
    mission_id: Optional[str] = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Returns ready / blocked / failed task sets per the dependency DAG."""
    resolution = await resolve_task_dependencies(db, ctx.organization_id, mission_id)
    return resolution


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    req: TaskCreateRequest,
    ctx: TenantContext = Depends(require_permission("task:write")),
    db: AsyncSession = Depends(get_db),
):
    task = WorkerTask(
        organization_id=ctx.organization_id,
        mission_id=req.mission_id,
        parent_task_id=req.parent_task_id,
        worker_type_required=req.worker_type_required,
        type=req.type,
        priority=req.priority,
        status="QUEUED",
        input_data=req.input_data,
        expected_output=req.expected_output,
        budget=req.budget,
        retry_policy=req.retry_policy,
        dependencies=req.dependencies,
    )
    db.add(task)
    await db.flush()
    await db.commit()
    return _task_dict(task)


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WorkerTask).where(
        WorkerTask.id == task_id, WorkerTask.organization_id == ctx.organization_id
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _task_dict(task)


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    result_data: dict = None,
    ctx: TenantContext = Depends(require_permission("task:write")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WorkerTask).where(
        WorkerTask.id == task_id, WorkerTask.organization_id == ctx.organization_id
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    from datetime import datetime, timezone

    task.status = "COMPLETED"
    task.completed_at = datetime.now(timezone.utc)
    task.result_data = result_data or {}
    await db.commit()
    return _task_dict(task)


@router.post("/{task_id}/fail")
async def fail_task(
    task_id: str,
    reason: str = "unspecified",
    ctx: TenantContext = Depends(require_permission("task:write")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WorkerTask).where(
        WorkerTask.id == task_id, WorkerTask.organization_id == ctx.organization_id
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    from datetime import datetime, timezone

    task.status = "FAILED"
    task.completed_at = datetime.now(timezone.utc)
    task.failure_reason = reason
    await db.commit()
    return _task_dict(task)
