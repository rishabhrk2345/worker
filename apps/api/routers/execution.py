"""
apps/api/routers/execution.py

Phase 4 — Mission execution control REST API (Temporal-backed).

- POST /api/missions/{id}/execute      : start the MissionWorkflow
- POST /api/missions/{id}/pause|resume : lifecycle signals
- POST /api/missions/{id}/cancel       : cooperative cancel
- GET  /api/missions/{id}/progress     : workflow query
- POST /api/tasks/{task_id}/approve    : human approval signal to a child
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.audit import record_audit
from core.config import settings
from core.database import get_db
from core.rbac import TenantContext, get_tenant_context, require_permission
from models import Mission
from temporal import client as tclient
from temporal.shared import MissionInput

router = APIRouter(prefix="/api/missions", tags=["Execution"])


class ApprovalDecision(BaseModel):
    approved: bool
    reason: Optional[str] = None
    edited_content: Optional[str] = None


async def _own_mission(db: AsyncSession, mission_id: str, org_id: str) -> Mission:
    stmt = select(Mission).where(
        Mission.id == mission_id, Mission.organization_id == org_id
    )
    mission = (await db.execute(stmt)).scalar_one_or_none()
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.post("/{mission_id}/execute")
async def execute_mission(
    mission_id: str,
    ctx: TenantContext = Depends(require_permission("mission:execute")),
    db: AsyncSession = Depends(get_db),
):
    """Start the durable MissionWorkflow for this mission (Temporal)."""
    mission = await _own_mission(db, mission_id, ctx.organization_id)

    input = MissionInput(
        mission_id=mission.id,
        organization_id=mission.organization_id,
        objective=mission.objective,
        budget_usd=mission.budget_usd,
        product_ids=mission.product_ids or [],
        worker_type_targets={
            "social_discovery": 1,
            "web_discovery": 1,
            "content_analyzer": 1,
            "problem_detector": 1,
            "deep_research": 1,
            "verification": 1,
            "outreach_draft": 1,
        },
    )
    try:
        result = await tclient.start_mission(input)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Temporal unavailable: {exc}",
        )

    mission.status = "ACTIVE"
    mission.started_at = mission.started_at or datetime.now(timezone.utc)
    await record_audit(
        db, ctx.organization_id, "mission.executed", "mission", mission.id,
        user_id=ctx.user_id, after={"workflow_id": result["workflow_id"]},
    )
    await db.commit()
    return result


@router.post("/{mission_id}/pause")
async def pause_mission(
    mission_id: str,
    ctx: TenantContext = Depends(require_permission("mission:execute")),
    db: AsyncSession = Depends(get_db),
):
    await _own_mission(db, mission_id, ctx.organization_id)
    await tclient.signal_mission(mission_id, "pause")
    return {"mission_id": mission_id, "paused": True}


@router.post("/{mission_id}/resume")
async def resume_mission(
    mission_id: str,
    ctx: TenantContext = Depends(require_permission("mission:execute")),
    db: AsyncSession = Depends(get_db),
):
    await _own_mission(db, mission_id, ctx.organization_id)
    await tclient.signal_mission(mission_id, "resume")
    return {"mission_id": mission_id, "paused": False}


@router.post("/{mission_id}/cancel")
async def cancel_mission(
    mission_id: str,
    ctx: TenantContext = Depends(require_permission("mission:execute")),
    db: AsyncSession = Depends(get_db),
):
    mission = await _own_mission(db, mission_id, ctx.organization_id)
    await tclient.signal_mission(mission_id, "cancel")
    mission.status = "CANCELLED"
    await record_audit(
        db, ctx.organization_id, "mission.cancelled", "mission", mission.id, user_id=ctx.user_id
    )
    await db.commit()
    return {"mission_id": mission_id, "cancelled": True}


@router.get("/{mission_id}/progress")
async def mission_progress(
    mission_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    await _own_mission(db, mission_id, ctx.organization_id)
    progress = await tclient.mission_progress(mission_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Mission workflow not running")
    return progress


# NOTE: approvals for wave-4 action tasks arrive on the child workflow id
# pattern f"{mission_id}-w3-{slot}" (WAVES index 3 in mission.py).
@router.post("/{mission_id}/tasks/{wave_idx}/{slot}/approval")
async def approve_task(
    mission_id: str,
    wave_idx: int,
    slot: int,
    decision: ApprovalDecision,
    ctx: TenantContext = Depends(require_permission("action:approve")),
    db: AsyncSession = Depends(get_db),
):
    """Forward a human approval decision to a specific child TaskWorkflow."""
    await _own_mission(db, mission_id, ctx.organization_id)
    await tclient.signal_task(
        mission_id, wave_idx, slot,
        "approval_decision",
        {
            "approved": decision.approved,
            "reason": decision.reason,
            "edited_content": decision.edited_content,
        },
    )
    await record_audit(
        db, ctx.organization_id, "action.approval_signalled", "mission", mission_id,
        user_id=ctx.user_id,
        after={"wave": wave_idx, "slot": slot, "approved": decision.approved},
    )
    await db.commit()
    return {"signalled": True, "wave": wave_idx, "slot": slot, "approved": decision.approved}
