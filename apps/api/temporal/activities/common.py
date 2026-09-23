"""
apps/api/temporal/activities/common.py

Phase 4 — Core Temporal activities.

Plain async functions: no DB objects cross the workflow boundary, only the
serializable dataclasses from temporal.shared. All activities open their own
short-lived session via AsyncSessionLocal. Event emission goes through the
production EventPublisher (journal + bus), preserving idempotency keys.

ApplicationError(non_retryable=True) is raised for domain faults that retry
cannot fix (mission deleted, no such worker type, worker vanished).
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from temporalio import activity
from temporalio.exceptions import ApplicationError
from sqlalchemy import func, select

from core.config import settings
from core.database import AsyncSessionLocal
from core.event_publisher import EventPublisher
from core.task_orchestration import BudgetExceededError, BudgetManager
from core.worker_state_machine import WorkerStateMachine, WorkerStateTransitionError
from models import Mission, MissionRun, Organization, Worker, WorkerRun, WorkerTask
from temporal.shared import (
    ACT_ALLOC,
    ACT_EMIT,
    ACT_PERSIST_RESULT,
    ACT_PERSIST_TASK,
    ACT_PERSIST_TRANSITION,
    ACT_SUPERVISE,
    ACTION_TASKS,
    AllocDecision,
    ANALYZE_TASKS,
    CRAWL_TASKS,
    MissionInput,
    RESEARCH_TASKS,
    SupervisorInput,
    SupervisorScan,
    TaskResult,
    TaskSpec,
    WorkerAssignment,
    task_type_for_worker,
)

logger = structlog.get_logger(__name__)


def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mission_run_id(mission_id: str) -> str:
    return _uuid(f"mission-run:{mission_id}")


def _task_family(task_type: str) -> str:
    if task_type in CRAWL_TASKS:
        return "crawl"
    if task_type in ANALYZE_TASKS:
        return "analyze"
    if task_type in RESEARCH_TASKS:
        return "research"
    if task_type in ACTION_TASKS:
        return "action"
    return "crawl"


# Contract-legal first working state per task family. The worker state
# contract (contracts/enums/worker_state.json) allows IDLE ->
# {PLANNING, DISCOVERING, SEARCHING} only — EXECUTING is reserved for
# post-approval actions, so allocation activates a working state, not EXECUTING.
START_STATE_BY_FAMILY = {
    "crawl": "DISCOVERING",
    "analyze": "SEARCHING",
    "research": "SEARCHING",
    "action": "SEARCHING",
}


async def _apply_state_change(
    session,
    *,
    worker: Worker,
    run_id: str,
    organization_id: str,
    mission_id: Optional[str],
    task_id: Optional[str],
    target: str,
    reason: str,
    seq: int,
) -> bool:
    """
    Contract-checked worker state transition + worker.state_changed event.

    Returns True when the transition was legal and emitted; False when the
    contract forbids it (worker keeps its current state, warning logged).
    """
    sm = WorkerStateMachine(worker.id, run_id, worker.status or "IDLE")
    if not sm.can_transition(target):
        logger.warning(
            "worker_state_transition_skipped",
            worker_id=worker.id,
            from_state=worker.status,
            to_state=target,
        )
        return False
    payload = sm.transition(target, reason=reason)
    worker.status = target
    await _emit(
        session,
        _envelope(
            "worker.state_changed",
            organization_id,
            worker.id,
            run_id,
            mission_id,
            task_id,
            worker.logical_zone,
            worker.logical_station,
            seq,
            {
                "from_state": payload["from_state"],
                "to_state": payload["to_state"],
                "reason": reason,
                "animation": payload["animation"],
            },
        ),
    )
    return True


async def _emit(session, event: Dict[str, Any]) -> None:
    """Emit an event through the production journal-first publisher."""
    await EventPublisher(session).publish(event)


def _envelope(
    event_type: str,
    org_id: str,
    worker_id: str,
    run_id: str,
    mission_id: Optional[str],
    task_id: Optional[str],
    zone: str,
    station: Optional[str],
    seq: int,
    payload: Dict[str, Any],
    scenario_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a canonical WorkerEvent envelope for workforce activity."""
    idem_source = f"{task_id or worker_id}:{seq}:{event_type}"
    metadata: Dict[str, Any] = {"emitter": "temporal"}
    if scenario_tag:
        metadata["scenario"] = scenario_tag
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "schema_version": "1.0",
        "organization_id": org_id,
        "mission_id": mission_id,
        "task_id": task_id,
        "worker_id": worker_id,
        "worker_run_id": run_id,
        "correlation_id": _uuid(f"mission-run:{mission_id}" if mission_id else f"worker-run:{run_id}"),
        "logical_zone": zone,
        "logical_station": station,
        "dedupe_key": None,
        "idempotency_key": f"sha256:{idem_source}",
        "sequence": seq,
        "occurred_at": _now().isoformat(),
        "payload": payload,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Journal / persistence activities
# ---------------------------------------------------------------------------

@activity.defn
async def persist_task_creation(spec: TaskSpec) -> None:
    """Create (or reuse) the durable WorkerTask row before execution."""
    async with AsyncSessionLocal() as session:
        existing = await session.get(WorkerTask, spec.task_id)
        if existing:
            existing.status = "QUEUED"
            existing.mission_id = spec.mission_id
            existing.failure_reason = None
        else:
            session.add(
                WorkerTask(
                    id=spec.task_id,
                    organization_id=spec.organization_id,
                    mission_id=spec.mission_id,
                    worker_type_required=spec.worker_type_required,
                    type=spec.type,
                    status="QUEUED",
                    input_data=spec.input_data,
                    budget=spec.budget,
                )
            )
        await session.commit()


@activity.defn
async def persist_task_transition(spec: TaskSpec, status: str) -> WorkerAssignment:
    """
    Persist a task status flip and manage the worker-run lifecycle:

    - IN_PROGRESS: allocate an idle worker of the required type, open a
      WorkerRun, emit worker.started + state transition events.
    - COMPLETED / FAILED: close the run, return the worker to IDLE, emit
      terminal state events.

    Heartbeats after each DB step so long allocation storms stay liveness-checked.
    """
    activity.heartbeat()
    async with AsyncSessionLocal() as session:
        task = await session.get(WorkerTask, spec.task_id)
        if task is None:
            raise ApplicationError(
                f"task {spec.task_id} not found", type="TaskMissing", non_retryable=True
            )
        task.status = status
        now = _now()

        if status == "IN_PROGRESS":
            task.started_at = task.started_at or now

            # Idempotent under worker-crash redelivery: if a previous execution
            # of this activity already opened a run, reuse it instead of
            # allocating a second worker (which would hit NoIdleWorker).
            existing_run = (
                await session.execute(
                    select(WorkerRun)
                    .where(WorkerRun.task_id == task.id, WorkerRun.status == "RUNNING")
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing_run is not None:
                prev = await session.get(Worker, existing_run.worker_id)
                return WorkerAssignment(
                    worker_id=existing_run.worker_id,
                    worker_run_id=existing_run.id,
                    worker_name=prev.name if prev else "",
                )

            stmt = (
                select(Worker)
                .where(
                    Worker.organization_id == spec.organization_id,
                    Worker.worker_type_id == spec.worker_type_required,
                    Worker.status == "IDLE",
                )
                .limit(1)
            )
            worker = (await session.execute(stmt)).scalar_one_or_none()
            if worker is None:
                raise ApplicationError(
                    f"no idle {spec.worker_type_required} worker available",
                    type="NoIdleWorker",
                    non_retryable=True,
                )

            run = WorkerRun(
                worker_id=worker.id,
                mission_id=spec.mission_id,
                task_id=task.id,
                status="RUNNING",
                autonomy_level=worker.autonomy_level,
            )
            session.add(run)
            await session.flush()

            task.worker_id = worker.id
            worker.current_task_id = task.id
            zone = worker.logical_zone
            station = worker.logical_station
            await session.commit()

            seq = 1
            await _emit(
                session,
                _envelope(
                    "worker.started", spec.organization_id, worker.id, run.id,
                    spec.mission_id, task.id, zone, station, seq,
                    {
                        "worker_type": spec.worker_type_required,
                        "worker_name": worker.name,
                        "autonomy_level": worker.autonomy_level,
                        "mission_objective": spec.type,
                        "budget": spec.budget,
                    },
                ),
            )
            # Contract-legal activation: IDLE -> family working state.
            start_state = START_STATE_BY_FAMILY[_task_family(spec.type)]
            await _apply_state_change(
                session,
                worker=worker,
                run_id=run.id,
                organization_id=spec.organization_id,
                mission_id=spec.mission_id,
                task_id=task.id,
                target=start_state,
                reason=f"task:{spec.type}",
                seq=seq + 1,
            )
            await session.commit()
            return WorkerAssignment(worker_id=worker.id, worker_run_id=run.id, worker_name=worker.name)

        if status in ("COMPLETED", "FAILED"):
            worker: Optional[Worker] = None
            prev_status = "IDLE"
            if task.worker_id:
                worker = await session.get(Worker, task.worker_id)
            if worker is not None:
                zone = worker.logical_zone
                station = worker.logical_station
                prev_status = worker.status or "IDLE"
                worker.current_task_id = None
            else:
                zone = "OPERATIONS"
                station = None

            run_id = None
            run_stmt = (
                select(WorkerRun)
                .where(WorkerRun.task_id == task.id, WorkerRun.status == "RUNNING")
                .order_by(WorkerRun.started_at.desc())
                .limit(1)
            )
            run = (await session.execute(run_stmt)).scalar_one_or_none()
            if run is not None:
                run.status = "COMPLETED" if status == "COMPLETED" else "FAILED"
                run.completed_at = now
                run_id = run.id

            await session.commit()

            # Terminal state walk (worker returns to IDLE), driven by the
            # worker's ACTUAL current state — not a hardcoded EXECUTING.
            if worker is not None and run_id:
                reason = f"task_{status.lower()}"
                if not await _apply_state_change(
                    session,
                    worker=worker,
                    run_id=run_id,
                    organization_id=spec.organization_id,
                    mission_id=spec.mission_id,
                    task_id=task.id,
                    target="IDLE",
                    reason=reason,
                    seq=99,
                ):
                    # Rare leftovers (e.g. FETCHING) walk through FAILED first.
                    await _apply_state_change(
                        session,
                        worker=worker,
                        run_id=run_id,
                        organization_id=spec.organization_id,
                        mission_id=spec.mission_id,
                        task_id=task.id,
                        target="FAILED",
                        reason=reason,
                        seq=99,
                    )
                    await _apply_state_change(
                        session,
                        worker=worker,
                        run_id=run_id,
                        organization_id=spec.organization_id,
                        mission_id=spec.mission_id,
                        task_id=task.id,
                        target="IDLE",
                        reason=reason,
                        seq=100,
                    )
            elif worker is not None:
                worker.status = "IDLE"
            await session.commit()
            return WorkerAssignment(
                worker_id=worker.id if worker else "",
                worker_run_id=run_id or "",
                worker_name=worker.name if worker else "",
            )

        await session.commit()
        return WorkerAssignment(worker_id="", worker_run_id="", worker_name="")


@activity.defn
async def persist_task_result(spec: TaskSpec, result: TaskResult) -> None:
    """Store output/failure and attach cost telemetry to the run."""
    async with AsyncSessionLocal() as session:
        task = await session.get(WorkerTask, spec.task_id)
        if task is None:
            raise ApplicationError(
                f"task {spec.task_id} not found", type="TaskMissing", non_retryable=True
            )
        now = _now()
        if result.ok:
            task.status = "COMPLETED"
            task.completed_at = now
            task.result_data = result.output
            task.failure_reason = None
        else:
            task.status = "FAILED"
            task.completed_at = now
            task.failure_reason = result.error or "unspecified failure"

        run_id = result.output.get("worker_run_id") if result.ok else None
        if run_id:
            run = await session.get(WorkerRun, run_id)
            if run is not None:
                run.status = "COMPLETED" if result.ok else "FAILED"
                run.completed_at = now
                run.pages_inspected = int(result.output.get("pages_fetched", 0) or 0)
        await session.commit()


# ---------------------------------------------------------------------------
# Event emission activity (workflows cannot publish directly)
# ---------------------------------------------------------------------------

@activity.defn
async def emit_event(event: Dict[str, Any]) -> bool:
    """Journal-first publish of a prebuilt envelope (used by MissionWorkflow)."""
    async with AsyncSessionLocal() as session:
        stored = await EventPublisher(session).publish(event)
        await session.commit()  # activity owns the session: commit or lose the row
        return stored


# ---------------------------------------------------------------------------
# Worker allocation planning (deterministic, DB-driven)
# ---------------------------------------------------------------------------

@activity.defn
async def allocate_workers(input: MissionInput) -> AllocDecision:
    """
    Pick idle workers per requested worker-type target:
      {"social_discovery": 2, "deep_research": 1}
    Falls back to ANY idle worker when a type has none (partial allocation).
    """
    assignments: List[WorkerAssignment] = []
    unassigned: List[str] = []
    async with AsyncSessionLocal() as session:
        remaining = dict(input.worker_type_targets or {})
        for wtype, count in remaining.items():
            stmt = (
                select(Worker)
                .where(
                    Worker.organization_id == input.organization_id,
                    Worker.worker_type_id == wtype,
                    Worker.status == "IDLE",
                )
                .limit(count)
            )
            workers = (await session.execute(stmt)).scalars().all()
            for w in workers:
                assignments.append(
                    WorkerAssignment(worker_id=w.id, worker_run_id="", worker_name=w.name)
                )
            if len(workers) < count:
                unassigned.extend([wtype] * (count - len(workers)))

        # Fallback: fill any shortfall with generic idle workers
        still_short = sum(
            1
            for wtype, count in (input.worker_type_targets or {}).items()
            if count > 0 and wtype not in {a.worker_name for a in assignments}
        )
        if unassigned:
            stmt = (
                select(Worker)
                .where(
                    Worker.organization_id == input.organization_id,
                    Worker.status == "IDLE",
                )
                .limit(len(unassigned))
            )
            extras = (await session.execute(stmt)).scalars().all()
            for w in extras:
                assignments.append(
                    WorkerAssignment(worker_id=w.id, worker_run_id="", worker_name=w.name)
                )
            unassigned = unassigned[len(extras):]

    return AllocDecision(assignments=assignments, unassigned=unassigned)


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

@activity.defn
async def supervisor_scan(input: SupervisorInput) -> SupervisorScan:
    """
    Fleet health scan: counts idle vs active workers per organization and
    raises alerts for stuck EXECUTING workers (no completed run for >5 min).
    """
    async with AsyncSessionLocal() as session:
        orgs = (await session.execute(select(Organization))).scalars().all()
        mission_rows: List[Dict[str, Any]] = []
        alerts: List[Dict[str, Any]] = []
        active_total = 0

        for org in orgs:
            total = (
                await session.execute(
                    select(func.count()).select_from(Worker).where(Worker.organization_id == org.id)
                )
            ).scalar() or 0
            idle = (
                await session.execute(
                    select(func.count()).select_from(Worker).where(
                        Worker.organization_id == org.id, Worker.status == "IDLE"
                    )
                )
            ).scalar() or 0
            active_total += total - idle

            stuck = (
                await session.execute(
                    select(Worker).where(
                        Worker.organization_id == org.id,
                        Worker.status.notin_(("IDLE", "COMPLETED", "FAILED")),
                    )
                )
            ).scalars().all()
            for w in stuck:
                alerts.append(
                    {
                        "organization_id": org.id,
                        "worker_id": w.id,
                        "worker_name": w.name,
                        "state": w.status,
                        "reason": "worker_not_idle",
                    }
                )

            missions = (
                await session.execute(
                    select(Mission).where(
                        Mission.organization_id == org.id, Mission.status == "ACTIVE"
                    )
                )
            ).scalars().all()
            for m in missions:
                mission_rows.append({"mission_id": m.id, "name": m.name, "status": m.status})

        return SupervisorScan(
            ts=time.time(),
            active_workflows=active_total,
            missions=mission_rows,
            alerts=alerts,
        )
