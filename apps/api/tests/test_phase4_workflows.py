"""
apps/api/tests/test_phase4_workflows.py

Phase 4 workflow integration tests on temporalio's time-skipping
WorkflowEnvironment (real bundled test server, real worker process):

- MissionWorkflow completes all waves; task lifecycle is journaled exactly-once
- Approval flow: wave-4 blocks until the approval_decision signal, then runs;
  rejection marks the task FAILED and the mission still completes
- Mission pause/resume gates all task activity
- Cooperative cancel stops the mission with status CANCELLED
- Crash recovery: killing the worker process mid-flight causes Temporal to
  redeliver work to a NEW worker; journal idempotency guarantees no duplicate
  event rows (plan test matrix: "Workflow crash recovery")
- SupervisorWorkflow: periodic scans include ACTIVE missions

Shared DB: temporal_fixtures.temporal_db monkeypatches all three session
factories onto one in-memory SQLite (StaticPool), so activities running inside
the test env's worker and the test-side session see the same data.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from models import EventJournal, Worker, WorkerTask
from temporal.shared import MissionInput
from tests.temporal_fixtures import make_mission_input, tsession, temporal_db  # noqa: F401

TASK_QUEUE = "phase4-test-queue"


def _common_activities():
    from temporal.activities.common import (
        emit_event,
        persist_task_creation,
        persist_task_result,
        persist_task_transition,
    )
    return [
        persist_task_creation,
        persist_task_transition,
        persist_task_result,
        emit_event,
    ]


def _domain_activities():
    from temporal.activities.domain import (
        action_activity,
        analyze_activity,
        research_activity,
        worker_activity,
    )
    return [worker_activity, analyze_activity, research_activity, action_activity]


def _workflows():
    from temporal.workflows.mission import MissionWorkflow, TaskWorkflow
    return [MissionWorkflow, TaskWorkflow]


def _start_worker(env, *, extra_workflows=(), extra_activities=()):
    from temporalio.worker import Worker

    return Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[*_workflows(), *extra_workflows],
        activities=[*_common_activities(), *_domain_activities(), *extra_activities],
        # Sticky workflow-task caching must be OFF for the crash-recovery test:
        # the bundled test server has no sticky-queue fallback, so a workflow
        # task sticky to a killed worker would never be redelivered. Real
        # Temporal servers fall back automatically, so production keeps
        # sticky caching enabled.
        max_cached_workflows=0,
    )


async def _wait_workflow_running(client, workflow_id: str, timeout: float = 45.0) -> None:
    """Poll until the workflow exists and is running (waves run sequentially)."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        handle = client.get_workflow_handle(workflow_id)
        try:
            desc = await handle.describe()
            if desc.status.name == "RUNNING":
                return
        except Exception:
            pass
        await asyncio.sleep(0.2)
    raise TimeoutError(f"workflow {workflow_id} not RUNNING within {timeout}s")


@pytest.fixture
def mission_input(temporal_db) -> MissionInput:
    return make_mission_input(temporal_db["org_id"])


@pytest.mark.asyncio
async def test_mission_completes_all_waves(temporal_db, tsession, mission_input):
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with _start_worker(env):
            client: Client = env.client
            from temporal.workflows.mission import MissionWorkflow

            handle = await client.start_workflow(
                MissionWorkflow.run,
                mission_input,
                id=f"mission-{mission_input.mission_id}",
                task_queue=TASK_QUEUE,
            )
            # Approve the wave-4 action task (mission blocks on it otherwise)
            child_id = f"{mission_input.mission_id}-w3-0"
            await _wait_workflow_running(client, child_id)
            await client.get_workflow_handle(child_id).signal(
                "approval_decision", {"approved": True, "reason": "ok"}
            )

            summary = await handle.result()

            assert summary["status"] == "COMPLETED"
            assert summary["total_tasks"] == 7  # 2+2+2+1 per WAVES
            assert summary["completed"] == 7
            assert summary["failed"] == 0

            # Durable DB effects: all 7 task rows completed
            n_done = (
                await tsession.execute(
                    select(func.count()).select_from(WorkerTask).where(
                        WorkerTask.mission_id == mission_input.mission_id,
                        WorkerTask.status == "COMPLETED",
                    )
                )
            ).scalar()
            assert n_done == 7

            # Every worker returned to IDLE
            idle = (
                await tsession.execute(
                    select(func.count()).select_from(Worker).where(Worker.status == "IDLE")
                )
            ).scalar()
            assert idle == 7

            # Journal: exactly-once rows, all lifecycle event types present
            events = (
                await tsession.execute(
                    select(EventJournal).where(
                        EventJournal.mission_id == mission_input.mission_id
                    )
                )
            ).scalars().all()
            types = {e.event_type for e in events}
            assert {"worker.started", "worker.state_changed", "worker.completed"} <= types
            keys = [e.idempotency_key for e in events]
            assert len(keys) == len(set(keys))


@pytest.mark.asyncio
async def test_approval_gate_blocks_until_signal(temporal_db, tsession, mission_input):
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment
    from temporal.workflows.mission import MissionWorkflow

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with _start_worker(env):
            client: Client = env.client
            handle = await client.start_workflow(
                MissionWorkflow.run,
                mission_input,
                id=f"mission-{mission_input.mission_id}",
                task_queue=TASK_QUEUE,
            )
            child_id = f"{mission_input.mission_id}-w3-0"

            # Wave 1-3 complete; wave 4 is WAITING_APPROVAL in the task table.
            await _wait_workflow_running(client, child_id)
            n_waiting = 0
            for _ in range(50):
                n_waiting = (
                    await tsession.execute(
                        select(func.count()).select_from(WorkerTask).where(
                            WorkerTask.mission_id == mission_input.mission_id,
                            WorkerTask.status == "WAITING_APPROVAL",
                        )
                    )
                ).scalar()
                if n_waiting == 1:
                    break
                await asyncio.sleep(0.1)
            assert n_waiting == 1, "wave-4 task must persist WAITING_APPROVAL"

            # Workflow is alive and parked on the gate. NOTE: we must NOT
            # await handle.result() here to "prove" blocking — in the
            # time-skipping environment awaiting a result fast-forwards
            # virtual time, which would run the mission into its execution
            # timeout. describe() does not trigger time-skipping.
            desc = await handle.describe()
            assert desc.status.name == "RUNNING", "mission must still be running while blocked"

            await client.get_workflow_handle(child_id).signal(
                "approval_decision", {"approved": True, "reason": "ship it"}
            )
            summary = await handle.result()
            assert summary["status"] == "COMPLETED"
            assert summary["completed"] == 7


@pytest.mark.asyncio
async def test_approval_rejection_fails_task_but_completes_mission(temporal_db, tsession, mission_input):
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment
    from temporal.workflows.mission import MissionWorkflow

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with _start_worker(env):
            client: Client = env.client
            handle = await client.start_workflow(
                MissionWorkflow.run,
                mission_input,
                id=f"mission-{mission_input.mission_id}",
                task_queue=TASK_QUEUE,
            )
            child_id = f"{mission_input.mission_id}-w3-0"
            await _wait_workflow_running(client, child_id)
            await client.get_workflow_handle(child_id).signal(
                "approval_decision", {"approved": False, "reason": "wrong ICP"}
            )

            summary = await handle.result()
            assert summary["status"] == "COMPLETED"  # mission continues
            assert summary["completed"] == 6
            assert summary["failed"] == 1
            assert len(summary["failed_task_ids"]) == 1

            tsession.expire_all()
            failed = (
                await tsession.execute(
                    select(WorkerTask).where(
                        WorkerTask.mission_id == mission_input.mission_id,
                        WorkerTask.status == "FAILED",
                    )
                )
            ).scalar_one()
            assert "rejected" in (failed.failure_reason or "")


@pytest.mark.asyncio
async def test_mission_pause_resume(temporal_db, tsession, mission_input):
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment
    from temporal.workflows.mission import MissionWorkflow

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with _start_worker(env):
            client: Client = env.client
            handle = await client.start_workflow(
                MissionWorkflow.run,
                mission_input,
                id=f"mission-{mission_input.mission_id}",
                task_queue=TASK_QUEUE,
            )
            child_id = f"{mission_input.mission_id}-w3-0"

            await handle.signal("pause")
            for _ in range(50):
                progress = await handle.query(MissionWorkflow.progress)
                if progress["paused"]:
                    break
                await asyncio.sleep(0.1)
            assert progress["paused"] is True

            await handle.signal("resume")
            await _wait_workflow_running(client, child_id)
            await client.get_workflow_handle(child_id).signal(
                "approval_decision", {"approved": True, "reason": "ok"}
            )
            summary = await handle.result()
            assert summary["status"] == "COMPLETED"
            assert summary["completed"] == 7


@pytest.mark.asyncio
async def test_mission_cooperative_cancel(temporal_db, tsession, mission_input):
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment
    from temporal.workflows.mission import MissionWorkflow

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with _start_worker(env):
            client: Client = env.client
            handle = await client.start_workflow(
                MissionWorkflow.run,
                mission_input,
                id=f"mission-{mission_input.mission_id}",
                task_queue=TASK_QUEUE,
            )
            await handle.signal("cancel")
            summary = await handle.result()
            assert summary["status"] == "CANCELLED"
            assert summary["completed"] < 7  # cancelled before all waves ran


@pytest.mark.asyncio
async def test_crash_recovery_worker_restart_no_duplicate_events(temporal_db, tsession, mission_input):
    """
    Kill the worker while waves are in flight; start a NEW worker; Temporal
    must redeliver and the mission must complete. Journal idempotency keys
    guarantee exactly-once event rows even though activities re-executed.
    """
    from temporalio.client import Client
    from temporalio.testing import WorkflowEnvironment
    from temporal.workflows.mission import MissionWorkflow

    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Worker "process" #1: killed while waves are in flight.
        crash_worker = _start_worker(env)
        await crash_worker.__aenter__()
        client: Client = env.client
        handle = await client.start_workflow(
            MissionWorkflow.run,
            mission_input,
            id=f"mission-{mission_input.mission_id}",
            task_queue=TASK_QUEUE,
        )
        child_id = f"{mission_input.mission_id}-w3-0"

        # Give wave 1 time to get under way, then "crash" (graceful timeout 0
        # abandons in-flight activities — the closest thing to a process kill).
        await asyncio.sleep(0.4)
        await asyncio.wait_for(crash_worker.shutdown(), timeout=5)

        # Worker "process" #2: picks up all redelivered work.
        async with _start_worker(env):
            await _wait_workflow_running(client, child_id)
            await client.get_workflow_handle(child_id).signal(
                "approval_decision", {"approved": True, "reason": "post-crash ok"}
            )
            summary = await handle.result()
            assert summary["status"] == "COMPLETED"
            assert summary["completed"] == 7

            # Exactly-once journal: every idempotency key stored exactly once
            events = (
                await tsession.execute(
                    select(EventJournal).where(
                        EventJournal.mission_id == mission_input.mission_id
                    )
                )
            ).scalars().all()
            keys = [e.idempotency_key for e in events]
            assert len(keys) == len(set(keys))
            assert len(keys) >= 10  # mission + per-task lifecycle events

            tasks_done = (
                await tsession.execute(
                    select(func.count()).select_from(WorkerTask).where(
                        WorkerTask.mission_id == mission_input.mission_id,
                        WorkerTask.status == "COMPLETED",
                    )
                )
            ).scalar()
            assert tasks_done == 7


@pytest.mark.asyncio
async def test_supervisor_scans_include_active_missions(temporal_db, tsession):
    from models import Mission
    from temporalio.testing import WorkflowEnvironment
    from temporal.workflows.supervisor import SupervisorWorkflow

    from temporal.activities.common import supervisor_scan

    # Seed an ACTIVE mission so the scan has something to report.
    tsession.add(
        Mission(
            organization_id=temporal_db["org_id"],
            name="Watched mission",
            objective="be supervised",
            status="ACTIVE",
        )
    )
    await tsession.commit()

    async with await WorkflowEnvironment.start_time_skipping() as env:
        from temporalio.worker import Worker

        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[SupervisorWorkflow],
            activities=[supervisor_scan],
        ):
            client = env.client
            handle = await client.start_workflow(
                SupervisorWorkflow.run,
                {"interval_seconds": 0.05, "max_scans": 2},
                id="supervisor-test-2",
                task_queue=TASK_QUEUE,
            )
            latest = await handle.result()
            assert latest is not None
            assert latest.active_workflows == 0  # all seeded workers are IDLE
            assert latest.alerts == []
            assert [m["name"] for m in latest.missions] == ["Watched mission"]
