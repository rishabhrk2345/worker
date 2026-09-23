"""
apps/api/temporal/worker.py

Phase 4 — Temporal worker process.

Registers all workflows and activities on the configured task queue and runs
until SIGINT/SIGTERM (graceful shutdown drains running tasks — plan Q:
graceful shutdown). Run with:

    cd apps/api && uv run python -m temporal.worker
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import structlog
from temporalio.client import Client
from temporalio.worker import Worker

from core.config import settings

logging.basicConfig(level=settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)

INTERRUPT_EVENT = asyncio.Event()


async def main() -> None:
    client = await Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE)

    # Activities (plain async functions with @activity.defn)
    from temporal.activities.common import (
        allocate_workers,
        emit_event,
        persist_task_creation,
        persist_task_result,
        persist_task_transition,
        supervisor_scan,
    )
    from temporal.activities.domain import (
        action_activity,
        analyze_activity,
        research_activity,
        worker_activity,
    )
    from temporal.workflows.mission import MissionWorkflow, TaskWorkflow
    from temporal.workflows.supervisor import SupervisorWorkflow

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[MissionWorkflow, TaskWorkflow, SupervisorWorkflow],
        activities=[
            persist_task_creation,
            persist_task_transition,
            persist_task_result,
            emit_event,
            allocate_workers,
            supervisor_scan,
            worker_activity,
            analyze_activity,
            research_activity,
            action_activity,
        ],
        # Graceful shutdown: let in-flight activities finish (plan Q)
        graceful_shutdown_timeout=timedelta(seconds=30),
    )

    async with worker:
        logger.info(
            "temporal_worker_started",
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            namespace=settings.TEMPORAL_NAMESPACE,
        )
        # Wait until interrupted
        await INTERRUPT_EVENT.wait()
        logger.info("temporal_worker_stopping")


def _handle_signal(signum, _frame) -> None:
    INTERRUPT_EVENT.set()


if __name__ == "__main__":
    import signal

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    asyncio.run(main())
