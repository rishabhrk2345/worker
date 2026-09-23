"""
apps/api/temporal/shared.py

Phase 4 — Serializable data contracts passed between workflows and activities.

Temporal requires every value crossing a workflow/activity boundary to be
serializable. Dataclasses with primitives (str/int/float/bool/None/dict)
convert cleanly via temporalio's default dataconverter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MissionInput:
    mission_id: str
    organization_id: str
    objective: str
    budget_usd: float
    product_ids: List[str] = field(default_factory=list)
    worker_type_targets: Dict[str, int] = field(default_factory=dict)


@dataclass
class TaskSpec:
    task_id: str
    organization_id: str
    mission_id: Optional[str]
    type: str
    worker_type_required: str
    input_data: Dict[str, Any]
    budget: Dict[str, Any]
    attempt: int = 1
    requires_approval: bool = False


@dataclass
class TaskResult:
    task_id: str
    ok: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class WorkerAssignment:
    worker_id: str
    worker_run_id: str
    worker_name: str


@dataclass
class AllocDecision:
    assignments: List[WorkerAssignment]
    unassigned: List[str]


@dataclass
class SupervisorScan:
    ts: float
    active_workflows: int
    missions: List[Dict[str, Any]] = field(default_factory=list)
    alerts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SupervisorInput:
    interval_seconds: float = 30.0
    max_scans: int = 0  # 0 = run until stopped


# ---------------------------------------------------------------------------
# Task-type taxonomy (plan Part 8: workers/{discovery,research,intelligence,action})
# ---------------------------------------------------------------------------

CRAWL_TASKS = {"web_fetch", "social_search", "source_scan"}
ANALYZE_TASKS = {"content_analyze", "problem_detect", "intent_score", "match"}
RESEARCH_TASKS = {"deep_research", "verify_claim"}
ACTION_TASKS = {"draft_outreach", "execute_action", "publish_content"}


# Deterministic worker-type -> task-type routing (used by MissionWorkflow)
TASK_TYPE_BY_WORKER_TYPE = {
    "social_discovery": "social_search",
    "web_discovery": "web_fetch",
    "search": "source_scan",
    "news": "source_scan",
    "forum": "source_scan",
    "review": "source_scan",
    "competitor_discovery": "source_scan",
    "trend_discovery": "source_scan",
    "deep_research": "deep_research",
    "conversation_research": "deep_research",
    "competitor_research": "deep_research",
    "market_research": "deep_research",
    "customer_research": "deep_research",
    "content_analyzer": "content_analyze",
    "problem_detector": "problem_detect",
    "intent_recognizer": "intent_score",
    "sentiment_analyzer": "content_analyze",
    "product_matcher": "match",
    "portfolio_analyzer": "match",
    "evidence": "verify_claim",
    "verification": "verify_claim",
    "outreach_draft": "draft_outreach",
    "content": "publish_content",
    "lead": "execute_action",
}


def task_type_for_worker(worker_type: str) -> str:
    return TASK_TYPE_BY_WORKER_TYPE.get(worker_type, "source_scan")


def activity_name_for_task(task_type: str) -> str:
    """Route a task type to its registered Temporal activity name."""
    if task_type in CRAWL_TASKS:
        return "worker_activity"
    if task_type in ANALYZE_TASKS:
        return "analyze_activity"
    if task_type in RESEARCH_TASKS:
        return "research_activity"
    if task_type in ACTION_TASKS:
        return "action_activity"
    return "worker_activity"


# Well-known activity names (single source of truth for worker registration)
ACT_WORKER = "worker_activity"
ACT_ANALYZE = "analyze_activity"
ACT_RESEARCH = "research_activity"
ACT_ACTION = "action_activity"
ACT_EMIT = "emit_event"
ACT_PERSIST_TASK = "persist_task_creation"
ACT_PERSIST_TRANSITION = "persist_task_transition"
ACT_PERSIST_RESULT = "persist_task_result"
ACT_ALLOC = "allocate_workers"
ACT_SUPERVISE = "supervisor_scan"
