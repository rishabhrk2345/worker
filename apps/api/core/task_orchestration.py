"""
apps/api/core/task_orchestration.py

Phase 3 — Task dependency resolution (plan E-1) and budget enforcement
(plan E-2 / ADR-007).

- resolve_task_dependencies: builds the dependency DAG and marks tasks ready
  to run only when every dependency is COMPLETED.
- BudgetManager: enforces maxTime / maxPages / maxLLMCalls / maxCost budgets
  attached to WorkerTask rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import WorkerTask


class DependencyCycleError(ValueError):
    """Raised when the task dependency graph contains a cycle."""


async def resolve_task_dependencies(
    session: AsyncSession, organization_id: str, mission_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns:
        {
          "ready": [task_id, ...],          # QUEUED tasks whose deps are all COMPLETED
          "blocked": [task_id, ...],        # waiting on unfinished dependencies
          "failed": [task_id, ...],         # dependent on a FAILED dependency
          "cycle": [task_id, ...] or []     # tasks participating in a dependency cycle
        }
    """
    stmt = select(WorkerTask).where(WorkerTask.organization_id == organization_id)
    if mission_id:
        stmt = stmt.where(WorkerTask.mission_id == mission_id)
    result = await session.execute(stmt)
    tasks: List[WorkerTask] = result.scalars().all()

    by_id: Dict[str, WorkerTask] = {t.id: t for t in tasks}
    status_by_id = {t.id: t.status for t in tasks}

    # Cycle detection (iterative DFS with colors)
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {tid: WHITE for tid in by_id}
    cycle_nodes: Set[str] = set()

    def dfs(start: str) -> bool:
        stack: List[Tuple[str, Iterable[str]]] = [(start, iter(by_id[start].dependencies or []))]
        color[start] = GRAY
        path: List[str] = [start]
        on_path: Set[str] = {start}
        found = False
        while stack:
            node, it = stack[-1]
            advanced = False
            for dep in it:
                if dep not in by_id:
                    continue
                c = color[dep]
                if c == GRAY:
                    # Found a back-edge: every node from dep..node on path is in a cycle
                    idx = path.index(dep) if dep in path else 0
                    cycle_nodes.update(path[idx:])
                    found = True
                elif c == WHITE:
                    color[dep] = GRAY
                    stack.append((dep, iter(by_id[dep].dependencies or [])))
                    path.append(dep)
                    on_path.add(dep)
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
                if path and path[-1] == node:
                    path.pop()
                    on_path.discard(node)
        return found

    for tid in by_id:
        if color[tid] == WHITE:
            dfs(tid)

    ready: List[str] = []
    blocked: List[str] = []
    failed: List[str] = []
    for task in tasks:
        deps = task.dependencies or []
        dep_statuses = [status_by_id.get(d) for d in deps if d in status_by_id]
        if any(s == "FAILED" for s in dep_statuses):
            failed.append(task.id)
        elif not dep_statuses or all(s == "COMPLETED" for s in dep_statuses):
            if task.status == "QUEUED":
                ready.append(task.id)
        else:
            blocked.append(task.id)

    return {
        "ready": ready,
        "blocked": blocked,
        "failed": failed,
        "cycle": sorted(cycle_nodes),
    }


class BudgetExceededError(RuntimeError):
    """Raised when a task attempts to continue past its declared budget."""


class BudgetManager:
    """
    Enforces the WorkerTask.budget JSONB contract:
        {"maxTime": seconds, "maxPages": int, "maxLLMCalls": int, "maxCost": usd}

    Usage: before each work step, call `check()`; after each step, `record()`.
    Budget enforcement test (plan Part 10): maxPages=5 -> stops at page 5.
    """

    def __init__(self, budget: Optional[Dict[str, Any]]) -> None:
        self.budget = budget or {}
        self.pages_used: int = 0
        self.llm_calls_used: int = 0
        self.cost_used: float = 0.0
        self.started_at: datetime = datetime.now(timezone.utc)

    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    def remaining(self) -> Dict[str, Any]:
        def rem(limit_key: str, used: float) -> Optional[float]:
            limit = self.budget.get(limit_key)
            return None if limit is None else max(0.0, float(limit) - used)

        time_limit = self.budget.get("maxTime")
        return {
            "pages": rem("maxPages", self.pages_used),
            "llm_calls": rem("maxLLMCalls", self.llm_calls_used),
            "cost_usd": rem("maxCost", self.cost_used),
            "time_seconds": None if time_limit is None else max(0.0, float(time_limit) - self.elapsed_seconds),
        }

    def check(self) -> None:
        """Raise BudgetExceededError when any budget dimension is exhausted."""
        r = self.remaining()
        if r["pages"] is not None and r["pages"] <= 0:
            raise BudgetExceededError(f"Page budget exhausted ({self.budget.get('maxPages')} pages)")
        if r["llm_calls"] is not None and r["llm_calls"] <= 0:
            raise BudgetExceededError(f"LLM call budget exhausted ({self.budget.get('maxLLMCalls')} calls)")
        if r["cost_usd"] is not None and r["cost_usd"] <= 0:
            raise BudgetExceededError(f"Cost budget exhausted (${self.budget.get('maxCost')})")
        if r["time_seconds"] is not None and r["time_seconds"] <= 0:
            raise BudgetExceededError(f"Time budget exhausted ({self.budget.get('maxTime')}s)")

    def record(self, pages: int = 0, llm_calls: int = 0, cost_usd: float = 0.0) -> None:
        self.pages_used += pages
        self.llm_calls_used += llm_calls
        self.cost_used += cost_usd

    def exceeded(self) -> bool:
        try:
            self.check()
            return False
        except BudgetExceededError:
            return True
