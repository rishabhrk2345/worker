"""
apps/api/temporal/client.py

Phase 4 — Temporal client helpers for the FastAPI layer.

Keeps one process-wide Client and provides typed operations used by the REST
API: start mission, pause/resume, cancel, approval signal, progress query.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import structlog

from core.config import settings

logger = structlog.get_logger(__name__)

_client = None
_client_lock = asyncio.Lock()


async def get_client():
    """Process-wide Temporal client (lazy, thread-safe)."""
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                from temporalio.client import Client

                try:
                    _client = await Client.connect(
                        settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE
                    )
                except Exception as exc:
                    logger.warning("temporal_connect_failed", error=str(exc))
                    raise
    return _client


def mission_workflow_id(mission_id: str) -> str:
    return f"mission-{mission_id}"


def supervisor_workflow_id(organization_id: str) -> str:
    return f"supervisor-{organization_id}"


async def start_mission(input) -> Dict[str, Any]:
    """Start (or signal an existing) MissionWorkflow for the mission."""
    from temporal.workflows.mission import MissionWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(
        mission_workflow_id(input.mission_id),
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    await handle.start(
        MissionWorkflow.run,
        input,
        id=mission_workflow_id(input.mission_id),
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    return {"workflow_id": mission_workflow_id(input.mission_id), "started": True}


async def get_or_start_supervisor(organization_id: str) -> Dict[str, Any]:
    """Ensure one SupervisorWorkflow runs per organization (idempotent)."""
    from temporal.workflows.supervisor import SupervisorWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(
        supervisor_workflow_id(organization_id),
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )
    try:
        desc = await handle.describe()
        return {"workflow_id": supervisor_workflow_id(organization_id), "status": str(desc.status)}
    except Exception:
        await handle.start(
            SupervisorWorkflow.run,
            SupervisorInput(interval_seconds=30.0),
            id=supervisor_workflow_id(organization_id),
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
        return {"workflow_id": supervisor_workflow_id(organization_id), "status": "RUNNING"}


async def signal_mission(mission_id: str, signal: str, arg: Optional[Any] = None) -> None:
    client = await get_client()
    handle = client.get_workflow_handle(mission_workflow_id(mission_id))
    await handle.signal(signal, arg) if arg else await handle.signal(signal)


async def signal_task(mission_id: str, wave_idx: int, slot: int, signal: str, arg: Any) -> None:
    """Signal a specific child TaskWorkflow by its deterministic id."""
    client = await get_client()
    handle = client.get_workflow_handle(f"{mission_id}-w{wave_idx}-{slot}")
    await handle.signal(signal, arg)


async def mission_progress(mission_id: str) -> Optional[Dict[str, Any]]:
    """Query the MissionWorkflow progress (None when not running)."""
    from temporal.workflows.mission import MissionWorkflow

    client = await get_client()
    handle = client.get_workflow_handle(mission_workflow_id(mission_id))
    try:
        return await handle.query(MissionWorkflow.progress)
    except Exception:
        return None
