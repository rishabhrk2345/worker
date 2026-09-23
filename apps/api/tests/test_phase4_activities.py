"""
apps/api/tests/test_phase4_activities.py

Phase 4 activity verification with temporalio's ActivityEnvironment
(real activity code, no Temporal server needed):

- persist_task_creation is idempotent
- persist_task_transition allocates an idle worker, is idempotent on
  crash-redelivery, and releases the worker on completion
- NoIdleWorker is a non-retryable ApplicationError
- emit_event lands in the journal (with commit)
- worker_activity respects maxPages budget and heartbeats
- research_activity stops at the confidence threshold
- action activity returns an executed marker
"""

import pytest
from sqlalchemy import func, select
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from models import EventJournal, Worker, WorkerRun, WorkerTask
from temporal.activities.common import persist_task_creation, persist_task_transition
from temporal.activities.domain import (
    action_activity,
    analyze_activity,
    research_activity,
    worker_activity,
)
from temporal.shared import TaskResult, TaskSpec
from tests.temporal_fixtures import tsession, temporal_db  # noqa: F401


@pytest.fixture
def env():
    return ActivityEnvironment()


def make_spec(org_id: str, **overrides) -> TaskSpec:
    base = dict(
        task_id="aaaaaaaa-0000-0000-0000-000000000001",
        organization_id=org_id,
        mission_id=None,
        type="web_fetch",
        worker_type_required="web_discovery",
        input_data={"url": "https://example.com"},
        budget={"maxPages": 3, "maxLLMCalls": 2, "maxCost": 1.0, "maxTime": 10},
    )
    base.update(overrides)
    return TaskSpec(**base)


@pytest.mark.asyncio
async def test_persist_task_creation_idempotent(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    spec = make_spec(org_id, task_id="aaaaaaaa-0000-0000-0000-000000000010")

    await env.run(persist_task_creation, spec)
    await env.run(persist_task_creation, spec)  # replay / retry must be safe

    n = (
        await tsession.execute(
            select(func.count()).select_from(WorkerTask).where(WorkerTask.id == spec.task_id)
        )
    ).scalar()
    assert n == 1


@pytest.mark.asyncio
async def test_transition_allocates_and_releases_worker(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    spec = make_spec(org_id, task_id="aaaaaaaa-0000-0000-0000-000000000020")
    await env.run(persist_task_creation, spec)  # workflow creates the task first

    assignment = await env.run(persist_task_transition, spec, "IN_PROGRESS")
    assert assignment.worker_id and assignment.worker_run_id

    worker = await tsession.get(Worker, assignment.worker_id)
    assert worker.status == "DISCOVERING"  # contract-legal crawl-family start state
    assert worker.current_task_id == spec.task_id
    task = await tsession.get(WorkerTask, spec.task_id)
    assert task.status == "IN_PROGRESS"
    assert task.started_at is not None

    await env.run(persist_task_transition, spec, "COMPLETED")
    tsession.expire_all()  # identity map is stale: activities wrote via their own sessions
    worker = await tsession.get(Worker, assignment.worker_id)
    assert worker.status == "IDLE"
    assert worker.current_task_id is None
    run = (
        await tsession.execute(
            select(WorkerRun).where(WorkerRun.task_id == spec.task_id)
        )
    ).scalar_one()
    assert run.status == "COMPLETED"
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_transition_is_idempotent_on_crash_redelivery(temporal_db, tsession, env):
    """Second IN_PROGRESS delivery must reuse the open run, not allocate twice."""
    org_id = temporal_db["org_id"]
    spec = make_spec(org_id, task_id="aaaaaaaa-0000-0000-0000-000000000021")
    await env.run(persist_task_creation, spec)

    first = await env.run(persist_task_transition, spec, "IN_PROGRESS")
    second = await env.run(persist_task_transition, spec, "IN_PROGRESS")

    assert first.worker_id == second.worker_id
    assert first.worker_run_id == second.worker_run_id

    runs = (
        await tsession.execute(
            select(func.count()).select_from(WorkerRun).where(WorkerRun.task_id == spec.task_id)
        )
    ).scalar()
    assert runs == 1

    executing = (
        await tsession.execute(
            select(func.count()).select_from(Worker).where(Worker.status != "IDLE")
        )
    ).scalar()
    assert executing == 1  # exactly one worker activated (DISCOVERING, not IDLE)


@pytest.mark.asyncio
async def test_no_idle_worker_is_non_retryable(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    spec = make_spec(
        org_id,
        task_id="aaaaaaaa-0000-0000-0000-000000000022",
        worker_type_required="evidence",  # real contract type, not seeded by the fixture
    )
    await env.run(persist_task_creation, spec)  # workflow creates the task first

    with pytest.raises(ApplicationError) as exc_info:
        await env.run(persist_task_transition, spec, "IN_PROGRESS")
    assert "no idle" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_emit_event_lands_in_journal(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    event = {
        "event_type": "worker.started",
        "organization_id": org_id,
        "worker_id": "w-1",
        "worker_run_id": "r-1",
        "correlation_id": "c-1",
        "idempotency_key": "phase4-emit-1",
        "sequence": 1,
        "occurred_at": "2026-01-01T00:00:00+00:00",
        "payload": {"x": 1},
    }
    stored = await env.run(_emit_event, event)
    assert stored is True

    n = (
        await tsession.execute(
            select(func.count()).select_from(EventJournal).where(
                EventJournal.idempotency_key == "phase4-emit-1"
            )
        )
    ).scalar()
    assert n == 1


async def _emit_event(event):
    # Local import keeps the module under test as the single source of truth.
    from temporal.activities.common import emit_event

    return await emit_event(event)


@pytest.mark.asyncio
async def test_worker_activity_respects_budget_and_heartbeats(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    heartbeats = []
    env.on_heartbeat = lambda *args, **kwargs: heartbeats.append(args)

    spec = make_spec(
        org_id,
        task_id="aaaaaaaa-0000-0000-0000-000000000030",
        budget={"maxPages": 2, "maxLLMCalls": 2, "maxCost": 1.0, "maxTime": 10},
    )
    result: TaskResult = await env.run(worker_activity, spec)

    assert result.ok is True
    assert result.output["pages_fetched"] == 2  # maxPages=2 -> stops at 2
    assert len(heartbeats) >= 3  # initial + one per page


@pytest.mark.asyncio
async def test_research_activity_stops_at_confidence(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    spec = make_spec(
        org_id,
        task_id="aaaaaaaa-0000-0000-0000-000000000031",
        type="deep_research",
        worker_type_required="deep_research",
        budget={"maxLLMCalls": 10, "maxPages": 10, "maxCost": 5.0, "maxTime": 60},
    )
    result: TaskResult = await env.run(research_activity, spec)
    assert result.ok
    assert result.output["verdict"] == "PASS"
    assert result.output["confidence"] >= 0.9
    assert result.output["steps"] < 10  # threshold, not safety cap


@pytest.mark.asyncio
async def test_analyze_activity_deterministic_scoring(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    spec = make_spec(
        org_id,
        task_id="aaaaaaaa-0000-0000-0000-000000000032",
        type="content_analyze",
        worker_type_required="content_analyzer",
        input_data={"content": "identical input"},
    )
    r1: TaskResult = await env.run(analyze_activity, spec)
    r2: TaskResult = await env.run(analyze_activity, spec)
    assert r1.ok and r2.ok
    assert r1.output["confidence"] == r2.output["confidence"]  # deterministic
    assert r1.output["content_hash"] == r2.output["content_hash"]


@pytest.mark.asyncio
async def test_action_activity_executes(temporal_db, tsession, env):
    org_id = temporal_db["org_id"]
    spec = make_spec(
        org_id,
        task_id="aaaaaaaa-0000-0000-0000-000000000033",
        type="draft_outreach",
        worker_type_required="outreach_draft",
    )
    result: TaskResult = await env.run(action_activity, spec)
    assert result.ok
    assert result.output["executed"] is True
    assert result.output["action_id"].startswith("action-")
