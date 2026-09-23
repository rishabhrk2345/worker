"""
apps/api/routers/ws.py

Phase 6 — Real-time WebSocket event stream.

- Endpoint: ws://localhost:8000/ws/events/{org_id}
- Subscription filter protocol (plan L-2): client sends
    {"subscribe": {"mission_ids": [...], "worker_ids": [...], "zones": [...]}}
  and the server only forwards matching events on that connection.
- Event batching (plan L-3): flushes at most every 50ms, batches up to 100.
- Reconnect protocol (plan M-1): client refetches /api/snapshot then
  subscribes; snapshot exposes latest_sequence for gap detection.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Set

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.event_publisher import get_default_bus

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["WebSocket"])

FLUSH_INTERVAL_S = 0.05  # plan L-3: 50ms batching window
MAX_BATCH = 100


def _matches(event: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    mission_ids = filters.get("mission_ids")
    if mission_ids and event.get("mission_id") not in mission_ids:
        return False
    worker_ids = filters.get("worker_ids")
    if worker_ids and event.get("worker_id") not in worker_ids:
        return False
    zones = filters.get("zones")
    if zones and event.get("logical_zone") not in zones:
        return False
    return True


@router.websocket("/ws/events/{org_id}")
async def ws_events(websocket: WebSocket, org_id: str) -> None:
    await websocket.accept()

    filters: Dict[str, Any] = {}
    queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
    bus = get_default_bus()

    async def on_event(event: Dict[str, Any]) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("ws_queue_overflow_dropping_event", org_id=org_id)

    subscription_id = await bus.subscribe(f"org:{org_id}", on_event)

    async def reader() -> None:
        nonlocal filters
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "invalid json"})
                continue
            sub = message.get("subscribe")
            if isinstance(sub, dict):
                filters = {
                    k: list(v) if isinstance(v, (list, tuple, set)) else v
                    for k, v in sub.items()
                }
                await websocket.send_json({"type": "subscribed", "filters": filters})

    async def writer() -> None:
        while True:
            batch: List[Dict[str, Any]] = [await queue.get()]
            await asyncio.sleep(FLUSH_INTERVAL_S)
            while not queue.empty() and len(batch) < MAX_BATCH:
                batch.append(queue.get_nowait())
            matching = [e for e in batch if _matches(e, filters)]
            if matching:
                await websocket.send_json({"type": "events", "events": matching})

    reader_task = asyncio.create_task(reader())
    writer_task = asyncio.create_task(writer())
    try:
        done, pending = await asyncio.wait(
            {reader_task, writer_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                logger.exception("ws_task_failed", error=str(exc))
    finally:
        await bus.unsubscribe(subscription_id)
        try:
            await websocket.close()
        except Exception:
            pass
