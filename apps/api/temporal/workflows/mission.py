"""
apps/api/temporal/workflows/mission.py

Phase 4 — MissionWorkflow + TaskWorkflow (ADR-003).

One mission = one durable Temporal workflow. The mission executes as
deterministic waves of child TaskWorkflows:

    wave 1: discovery (social_discovery / web_discovery)
    wave 2: analysis  (content_analyzer / problem_detector)
    wave 3: research  (deep_research / verification)
    wave 4: action    (outreach_draft)  -> requires human approval

Workflows MUST be deterministic: no DB access, no wall-clock, no I/O here.
Everything touching the outside world goes through activities. Timestamps use
workflow.now() (deterministic virtual time, stable under replay).

Crash recovery: every side effect is an activity with idempotency keys in the
event journal, so after a worker/process crash Temporal simply re-executes
the pending activity — events are deduplicated by the journal.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, CancelledError

with workflow.unsafe.imports_passed_through():
    from temporal.shared import (
        ACT_EMIT,
        ACT_PERSIST_RESULT,
        ACT_PERSIST_TASK,
        ACT_PERSIST_TRANSITION,
        AllocDecision,
        MissionInput,
        TaskResult,
        TaskSpec,
        activity_name_for_task,
        task_type_for_worker,
    )

RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=3,
)

# Allocation is safe to retry: persist_task_transition is idempotent under
# crash-redelivery (an open WorkerRun for the task is reused, not re-allocated).
ALLOCATION_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=10),
    maximum_attempts=4,
)

# Deterministic wave plan: worker types per wave
WAVES: List[List[str]] = [
    ["social_discovery", "web_discovery"],   # wave 1: discovery
    ["content_analyzer", "problem_detector"],  # wave 2: analysis
    ["deep_research", "verification"],       # wave 3: research
    ["outreach_draft"],                      # wave 4: action (approval-gated)
]

MISSION_BUDGET_USD = 50.0
COST_PER_TASK_USD = 0.25  # conservative planning constant for the budget guard


def _stable_uuid(name: str) -> str:
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def _is_non_retryable(exc: BaseException) -> bool:
    """True when an activity failure is a domain fault retry cannot fix."""
    if isinstance(exc, ApplicationError):
        return bool(getattr(exc, "non_retryable", False))
    cause = getattr(exc, "cause", None)
    return isinstance(cause, ApplicationError) and bool(
        getattr(cause, "non_retryable", False)
    )


def _as_task_result(raw: Any) -> TaskResult:
    """
    Normalize an activity/child result into TaskResult.

    temporalio's default dataconverter serializes dataclasses to JSON, so
    results arrive in workflow code as plain dicts regardless of type hints.
    """
    if isinstance(raw, TaskResult):
        return raw
    if isinstance(raw, dict):
        return TaskResult(**raw)
    raise TypeError(f"unexpected task result payload type: {type(raw)!r}")


@workflow.defn
class TaskWorkflow:
    """
    Executes one task: persist -> allocate worker -> run domain activity ->
    persist result. Supports:

    - automatic retry via RETRY_POLICY (crash-safe: re-runs are idempotent
      through journal idempotency keys),
    - human approval: when requires_approval, waits on the `approval_decision`
      signal BEFORE executing (Temporal signal/await, plan E-2),
    - pause/resume gates and cancellation (marking the task FAILED on cancel).
    """

    def __init__(self) -> None:
        # Signal state is initialized ONLY here — never reset in run(), so a
        # signal that arrives before the first workflow task is preserved.
        self._paused = False
        self._approval: Optional[Dict[str, Any]] = None

    @workflow.signal
    async def approval_decision(self, decision: Dict[str, Any]) -> None:
        """Receives {'approved': bool, 'reason': str, 'edited_content': str?}."""
        self._approval = decision

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False

    @workflow.run
    async def run(self, spec: TaskSpec) -> TaskResult:
        # 1. Durable task row (idempotent on retry)
        await workflow.execute_activity(
            ACT_PERSIST_TASK,
            spec,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_POLICY,
        )

        # 2. Allocate an idle worker + open the run (crash-safe: idempotent)
        assignment = await workflow.execute_activity(
            ACT_PERSIST_TRANSITION,
            args=(spec, "IN_PROGRESS"),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=ALLOCATION_RETRY,
        )

        try:
            # 3. Pause gate (signals may arrive at any time)
            while self._paused:
                await workflow.wait_condition(lambda: not self._paused)

            # 4. Human approval gate
            if spec.requires_approval:
                # Task-level WAITING_APPROVAL is visible in the task table for
                # the approval UI while the worker holds its working state.
                await workflow.execute_activity(
                    ACT_PERSIST_TRANSITION,
                    args=(spec, "WAITING_APPROVAL"),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY_POLICY,
                )
                await workflow.wait_condition(lambda: self._approval is not None)
                decision = self._approval or {}
                if not decision.get("approved", False):
                    result = TaskResult(
                        task_id=spec.task_id,
                        ok=False,
                        error=f"rejected: {decision.get('reason', 'no reason given')}",
                    )
                    await workflow.execute_activity(
                        ACT_PERSIST_RESULT,
                        args=(spec, result),
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RETRY_POLICY,
                    )
                    await workflow.execute_activity(
                        ACT_PERSIST_TRANSITION,
                        args=(spec, "FAILED"),
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RETRY_POLICY,
                    )
                    return result

            # 5. Execute the routed domain activity (heartbeating, budgeted)
            raw_result = await workflow.execute_activity(
                activity_name_for_task(spec.type),
                spec,
                start_to_close_timeout=timedelta(seconds=180),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=RETRY_POLICY,
            )
            result: TaskResult = _as_task_result(raw_result)
        except CancelledError:
            # Parent cancelled (or workflow.cancel()): release the worker and
            # re-raise so Temporal records the child as cancelled.
            try:
                await workflow.execute_activity(
                    ACT_PERSIST_TRANSITION,
                    args=(spec, "FAILED"),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=ALLOCATION_RETRY,
                )
            except Exception:  # cancellation is sticky; best-effort cleanup
                pass
            raise
        except (ApplicationError, ActivityError) as exc:
            if _is_non_retryable(exc):
                # Domain fault (e.g. NoIdleWorker): return a failed result so
                # the mission continues with the remaining tasks.
                result = TaskResult(task_id=spec.task_id, ok=False, error=str(exc))
            else:
                # Retries exhausted: record failure and release the worker.
                result = TaskResult(task_id=spec.task_id, ok=False, error=str(exc))
                await workflow.execute_activity(
                    ACT_PERSIST_TRANSITION,
                    args=(spec, "FAILED"),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY_POLICY,
                )
                return result

        # 6. Persist output + close the run (worker returns to IDLE)
        await workflow.execute_activity(
            ACT_PERSIST_RESULT,
            args=(spec, result),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_POLICY,
        )
        await workflow.execute_activity(
            ACT_PERSIST_TRANSITION,
            args=(spec, "COMPLETED" if result.ok else "FAILED"),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_POLICY,
        )
        return result


@workflow.defn
class MissionWorkflow:
    """
    Durable mission orchestration:

    - deterministic waves of parallel child TaskWorkflows,
    - mission-level pause/resume + cooperative cancel signals,
    - budget guard stops waves once the planned mission budget is spent,
    - progress query for the UI,
    - mission lifecycle events emitted through the journal-first publisher.
    """

    def __init__(self) -> None:
        self._paused = False
        self._cancel_requested = False
        self._completed = 0
        self._failed = 0
        self._total = 0
        self._mission_id = ""

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False

    @workflow.signal
    async def cancel(self) -> None:
        self._cancel_requested = True

    @workflow.query
    def progress(self) -> Dict[str, Any]:
        return {
            "mission_id": self._mission_id,
            "total": self._total,
            "completed": self._completed,
            "failed": self._failed,
            "paused": self._paused,
        }

    # ------------------------------------------------------------------ #

    def _mission_envelope(
        self, input: MissionInput, event_type: str, payload: Dict[str, Any], seq: int
    ) -> Dict[str, Any]:
        return {
            "event_type": event_type,
            "schema_version": "1.0",
            "organization_id": input.organization_id,
            "mission_id": input.mission_id,
            "worker_id": input.mission_id,
            "worker_run_id": _stable_uuid(f"mission-run:{input.mission_id}"),
            "correlation_id": _stable_uuid(f"mission-run:{input.mission_id}"),
            "logical_zone": "SUPERVISOR",
            "logical_station": "supervisor_console",
            "idempotency_key": f"sha256:{input.mission_id}:{event_type}",
            "sequence": seq,
            "occurred_at": workflow.now().isoformat(),
            "payload": payload,
            "metadata": {"emitter": "temporal-workflow"},
        }

    @staticmethod
    def _build_wave_specs(input: MissionInput) -> List[List[TaskSpec]]:
        """Deterministic task plan: same mission -> same task ids every time."""
        waves: List[List[TaskSpec]] = []
        seq = 0
        for wave_idx, worker_types in enumerate(WAVES):
            specs: List[TaskSpec] = []
            for wtype in worker_types:
                count = int((input.worker_type_targets or {}).get(wtype, 1))
                for i in range(count):
                    seq += 1
                    specs.append(
                        TaskSpec(
                            task_id=_stable_uuid(f"task:{input.mission_id}:{seq}"),
                            organization_id=input.organization_id,
                            mission_id=input.mission_id,
                            type=task_type_for_worker(wtype),
                            worker_type_required=wtype,
                            input_data={
                                "objective": input.objective,
                                "product_ids": input.product_ids,
                                "wave": wave_idx,
                                "slot": i,
                            },
                            budget={"maxPages": 5, "maxLLMCalls": 3, "maxCost": 0.5, "maxTime": 60},
                            requires_approval=(wave_idx == len(WAVES) - 1),
                        )
                    )
            waves.append(specs)
        return waves

    @workflow.run
    async def run(self, input: MissionInput) -> Dict[str, Any]:
        self._mission_id = input.mission_id
        wave_specs = self._build_wave_specs(input)
        self._total = sum(len(w) for w in wave_specs)

        await workflow.execute_activity(
            ACT_EMIT,
            self._mission_envelope(
                input,
                "worker.started",
                {
                    "worker_type": "supervisor",
                    "worker_name": f"Mission {input.mission_id[:8]}",
                    "autonomy_level": 3,
                    "mission_objective": input.objective,
                    "budget": {"max_cost_usd": MISSION_BUDGET_USD},
                    "assigned_products": input.product_ids,
                },
                1,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_POLICY,
        )

        results: List[TaskResult] = []
        status = "COMPLETED"
        seq = 1

        try:
            for wave_idx, specs in enumerate(wave_specs):
                if self._cancel_requested:
                    status = "CANCELLED"
                    break

                # Budget guard: stop before starting a wave we cannot afford
                planned_cost = (self._completed + len(specs)) * COST_PER_TASK_USD
                if planned_cost > MISSION_BUDGET_USD:
                    status = "BUDGET_EXHAUSTED"
                    break

                # Mission-level pause gate (children pause independently too)
                while self._paused:
                    await workflow.wait_condition(lambda: not self._paused)
                if self._cancel_requested:
                    status = "CANCELLED"
                    break

                wave_results: List[TaskResult] = await asyncio.gather(
                    *[
                        workflow.execute_child_workflow(
                            TaskWorkflow.run,
                            spec,
                            id=f"{input.mission_id}-w{wave_idx}-{i}",
                        )
                        for i, spec in enumerate(specs)
                    ]
                )
                for r in wave_results:
                    result = _as_task_result(r)
                    results.append(result)
                    if result.ok:
                        self._completed += 1
                    else:
                        self._failed += 1

            if self._cancel_requested and status != "CANCELLED":
                status = "CANCELLED"
        except CancelledError:
            # Hard cancel via Temporal (workflow.cancel())
            status = "CANCELLED"
            seq += 1
            try:
                await workflow.execute_activity(
                    ACT_EMIT,
                    self._mission_envelope(
                        input,
                        "worker.failed",
                        {"reason": "mission_cancelled", "completed": self._completed},
                        seq,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=None,  # no retries: cancellation is sticky
                )
            except Exception:
                pass
            raise

        summary = {
            "mission_id": input.mission_id,
            "status": status,
            "total_tasks": self._total,
            "completed": self._completed,
            "failed": self._failed,
            "failed_task_ids": [r.task_id for r in results if not r.ok],
            "planned_cost_usd": round(self._total * COST_PER_TASK_USD, 2),
        }

        seq += 1
        await workflow.execute_activity(
            ACT_EMIT,
            self._mission_envelope(
                input,
                "worker.completed" if status == "COMPLETED" else "worker.failed",
                {"summary": summary},
                seq,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_POLICY,
        )
        return summary
