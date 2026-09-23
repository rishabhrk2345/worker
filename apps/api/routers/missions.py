"""
apps/api/routers/missions.py

Phase 3 — REST API for Mission domain (plan Part 7): CRUD for missions,
goals, and mission runs. All endpoints are organization-scoped via TenantContext.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.audit import record_audit
from core.database import get_db
from core.rbac import TenantContext, get_tenant_context, require_permission
from models import Mission, MissionGoal, MissionRun

router = APIRouter(prefix="/api/missions", tags=["Missions"])


class MissionGoalIn(BaseModel):
    description: str
    metric: Optional[str] = None
    target: Optional[float] = None


class MissionCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    objective: str
    priority: str = "normal"
    budget_usd: float = 100.0
    product_ids: List[str] = Field(default_factory=list)
    goals: List[MissionGoalIn] = Field(default_factory=list)


class MissionUpdateRequest(BaseModel):
    name: Optional[str] = None
    objective: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    budget_usd: Optional[float] = None
    product_ids: Optional[List[str]] = None


def _mission_dict(m: Mission, with_goals: bool = True) -> dict:
    data = {
        "id": m.id,
        "name": m.name,
        "objective": m.objective,
        "status": m.status,
        "priority": m.priority,
        "budget_usd": m.budget_usd,
        "product_ids": m.product_ids,
        "scheduled_cron": m.scheduled_cron,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "started_at": m.started_at.isoformat() if m.started_at else None,
        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
    }
    if with_goals:
        data["goals"] = [
            {
                "id": g.id,
                "description": g.description,
                "metric": g.metric,
                "target": g.target,
                "current_value": g.current_value,
            }
            for g in (m.goals or [])
        ]
    return data


@router.get("")
async def list_missions(
    status_filter: Optional[str] = None,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Mission)
        .options(selectinload(Mission.goals))
        .where(Mission.organization_id == ctx.organization_id)
        .order_by(Mission.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Mission.status == status_filter)
    result = await db.execute(stmt)
    missions = result.scalars().unique().all()
    return [_mission_dict(m) for m in missions]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_mission(
    req: MissionCreateRequest,
    ctx: TenantContext = Depends(require_permission("mission:write")),
    db: AsyncSession = Depends(get_db),
):
    mission = Mission(
        organization_id=ctx.organization_id,
        name=req.name,
        objective=req.objective,
        status="PLANNED",
        priority=req.priority,
        budget_usd=req.budget_usd,
        product_ids=req.product_ids,
    )
    for g in req.goals:
        mission.goals.append(
            MissionGoal(description=g.description, metric=g.metric, target=g.target)
        )
    db.add(mission)
    await db.flush()
    await record_audit(
        db, ctx.organization_id, "mission.created", "mission", mission.id,
        user_id=ctx.user_id, after={"name": mission.name, "status": mission.status},
    )
    await db.commit()
    return _mission_dict(mission)


@router.get("/{mission_id}")
async def get_mission(
    mission_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Mission)
        .options(selectinload(Mission.goals), selectinload(Mission.runs))
        .where(Mission.id == mission_id, Mission.organization_id == ctx.organization_id)
    )
    result = await db.execute(stmt)
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    data = _mission_dict(mission)
    data["runs"] = [
        {
            "id": r.id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "cost_usd": r.cost_usd,
        }
        for r in (mission.runs or [])
    ]
    return data


@router.patch("/{mission_id}")
async def update_mission(
    mission_id: str,
    req: MissionUpdateRequest,
    ctx: TenantContext = Depends(require_permission("mission:write")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Mission).where(
        Mission.id == mission_id, Mission.organization_id == ctx.organization_id
    )
    result = await db.execute(stmt)
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")

    before = {"status": mission.status, "priority": mission.priority}
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(mission, field, value)
    await db.flush()
    await record_audit(
        db, ctx.organization_id, "mission.updated", "mission", mission.id,
        user_id=ctx.user_id, before=before,
        after={"status": mission.status, "priority": mission.priority},
    )
    await db.commit()
    return _mission_dict(mission)


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_mission(
    mission_id: str,
    ctx: TenantContext = Depends(require_permission("mission:write")),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Mission).where(
        Mission.id == mission_id, Mission.organization_id == ctx.organization_id
    )
    result = await db.execute(stmt)
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    mission.status = "CANCELLED"
    await record_audit(
        db, ctx.organization_id, "mission.cancelled", "mission", mission.id, user_id=ctx.user_id
    )
    await db.commit()
    return None
