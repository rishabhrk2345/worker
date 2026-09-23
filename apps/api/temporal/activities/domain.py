"""
apps/api/temporal/activities/domain.py

Phase 4 — Domain activities executed by the digital workforce.

Each activity:
- receives a TaskSpec (serializable),
- enforces the task budget (ADR-007),
- heartbeats during long operations (plan E-3),
- emits progress events through the production EventPublisher,
- returns a serializable TaskResult.

Execution is intentionally connector-free at this phase: the `_fetch_*`
helpers simulate plausible output so MissionWorkflow can be exercised
end-to-end. Phase 10 connectors will replace these internals WITHOUT any
workflow changes (ADR-006 — orchestration only calls capabilities).
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import structlog
from temporalio import activity

from core.database import AsyncSessionLocal
from core.event_publisher import EventPublisher
from core.task_orchestration import BudgetExceededError, BudgetManager
from temporal.shared import (
    ACT_ACTION, ACT_ANALYZE, ACT_RESEARCH, ACT_WORKER,
    TaskResult, TaskSpec,
)

logger = structlog.get_logger(__name__)

PAGE_DELAY_S = 0.05  # per-page simulated latency (deterministic, no randoms)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _emit_progress(spec: TaskSpec, event_type: str, seq: int, payload: Dict[str, Any]) -> None:
    """Journal-first publish of a task progress event."""
    async with AsyncSessionLocal() as session:
        await EventPublisher(session).publish(
            {
                "event_type": event_type,
                "schema_version": "1.0",
                "organization_id": spec.organization_id,
                "mission_id": spec.mission_id,
                "task_id": spec.task_id,
                "worker_id": f"task-{spec.task_id[:8]}",
                "worker_run_id": f"task-{spec.task_id[:8]}",
                "correlation_id": spec.task_id,
                "logical_zone": "OPERATIONS",
                "idempotency_key": f"sha256:{spec.task_id}:{seq}:{event_type}",
                "sequence": seq,
                "occurred_at": _now().isoformat(),
                "payload": payload,
                "metadata": {"emitter": "temporal-activity"},
            }
        )
        await session.commit()  # activity owns the session: commit or lose the row


def _budget_from(spec: TaskSpec) -> BudgetManager:
    b = spec.budget or {}
    return BudgetManager(
        {
            "maxPages": b.get("maxPages", b.get("max_pages", 10)),
            "maxLLMCalls": b.get("maxLLMCalls", b.get("max_llm_calls", 5)),
            "maxCost": b.get("maxCost", b.get("max_cost", 1.0)),
            "maxTime": b.get("maxTime", b.get("max_time", 60)),
        }
    )


def _result(spec: TaskSpec, ok: bool, output: Dict[str, Any], error: str | None = None) -> TaskResult:
    return TaskResult(task_id=spec.task_id, ok=ok, output=output, error=error)


# ---------------------------------------------------------------------------
# CRAWL family
# ---------------------------------------------------------------------------

@activity.defn
async def worker_activity(spec: TaskSpec) -> TaskResult:
    """
    Discovery/crawl work (social_search, web_fetch, source_scan).
    Simulated connector fetches, one heartbeat per page, budget-bounded.
    """
    activity.heartbeat()
    budget = _budget_from(spec)
    pages = 0
    try:
        while budget.remaining()["pages"] is None or budget.remaining()["pages"] > 0:
            budget.check()
            await asyncio.sleep(PAGE_DELAY_S)  # simulated network fetch
            budget.record(pages=1)
            pages += 1
            activity.heartbeat()  # plan E-3: liveness during long operations

            if pages % 5 == 0:
                await _emit_progress(
                    spec, "worker.page_fetched", pages,
                    {"pages_fetched": pages, "task_type": spec.type},
                )
    except BudgetExceededError:
        pass  # budget exhausted == graceful stop (ADR-007)

    output = {
        "task_type": spec.type,
        "pages_fetched": pages,
        "budget": {"pages_used": budget.pages_used, "llm_used": budget.llm_calls_used},
    }
    await _emit_progress(spec, "worker.search_completed", pages + 1, output)
    return _result(spec, ok=True, output=output)


# ---------------------------------------------------------------------------
# ANALYZE family
# ---------------------------------------------------------------------------

@activity.defn
async def analyze_activity(spec: TaskSpec) -> TaskResult:
    """
    Content analysis (content_analyze, problem_detect, intent_score, match).
    Deterministic scoring derived from input content; LLM-budget-bounded.
    """
    activity.heartbeat()
    budget = _budget_from(spec)
    budget.check()
    budget.record(llm_calls=1)

    source = str(spec.input_data.get("content") or spec.input_data.get("url") or spec.type)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    confidence = 0.55 + (int(digest[:2], 16) / 255) * 0.4  # 0.55..0.95 deterministic

    findings = {
        "task_type": spec.type,
        "confidence": round(confidence, 3),
        "content_hash": digest[:16],
        "llm_calls_used": budget.llm_calls_used,
    }
    if spec.type in ("problem_detect", "intent_score"):
        findings["problem_detected"] = confidence > 0.75
    await _emit_progress(spec, "worker.content_found", 1, findings)
    return _result(spec, ok=True, output=findings)


# ---------------------------------------------------------------------------
# RESEARCH family
# ---------------------------------------------------------------------------

@activity.defn
async def research_activity(spec: TaskSpec) -> TaskResult:
    """
    Deep research & verification (deep_research, verify_claim).
    Iterates evidence steps under budget, emitting research_step events.
    """
    activity.heartbeat()
    budget = _budget_from(spec)
    steps = 0
    confidence = 0.5

    while confidence < 0.9:
        budget.check()
        await asyncio.sleep(PAGE_DELAY_S)
        budget.record(llm_calls=1)
        steps += 1
        confidence = min(0.95, confidence + 0.15)
        activity.heartbeat()
        await _emit_progress(
            spec, "worker.research_step_completed", steps,
            {"step": steps, "confidence": round(confidence, 3)},
        )
        if steps >= 10:  # hard safety cap independent of budget
            break

    verdict = "PASS" if confidence >= 0.9 else "LOW_CONFIDENCE"
    output = {
        "task_type": spec.type,
        "steps": steps,
        "confidence": round(confidence, 3),
        "verdict": verdict,
    }
    await _emit_progress(spec, "worker.verification_completed", steps + 1, output)
    return _result(spec, ok=True, output=output)


# ---------------------------------------------------------------------------
# ACTION family
# ---------------------------------------------------------------------------

@activity.defn
async def action_activity(spec: TaskSpec) -> TaskResult:
    """
    Permissioned actions (draft_outreach, execute_action, publish_content).

    requires_approval=True -> the activity returns a pending marker; the
    TaskWorkflow blocks on the approval signal BEFORE this activity runs.
    Execution itself is simulated here; Phase 14 wires real platform calls.
    """
    activity.heartbeat()
    budget = _budget_from(spec)
    budget.check()

    action_id = f"action-{uuid.uuid4().hex[:12]}"
    output = {
        "task_type": spec.type,
        "action_id": action_id,
        "executed": True,
        "executed_at": _now().isoformat(),
    }
    await _emit_progress(spec, "worker.action_executed", 1, output)
    return _result(spec, ok=True, output=output)
