"""
apps/api/temporal/workflows/supervisor.py

Phase 4 — SupervisorWorkflow (plan Phase 4 deliverable).

A long-running workflow that periodically scans fleet health via the
`supervisor_scan` activity and exposes the latest scan through a query.
Stops on the `stop` signal (or after max_scans, 0 = forever).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporal.shared import SupervisorInput, SupervisorScan
    from temporal.shared import ACT_SUPERVISE


@workflow.defn
class SupervisorWorkflow:
    """Periodic fleet health scan with queryable latest result."""

    def __init__(self) -> None:
        self._latest: Optional[SupervisorScan] = None
        self._stop = False

    @workflow.signal
    async def stop(self) -> None:
        self._stop = True

    @workflow.query
    def latest_scan(self) -> Optional[SupervisorScan]:
        return self._latest

    @workflow.run
    async def run(self, input: SupervisorInput) -> SupervisorScan:
        scans = 0
        while not self._stop and (input.max_scans == 0 or scans < input.max_scans):
            self._latest = await workflow.execute_activity(
                ACT_SUPERVISE,
                input,
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=None,
            )
            scans += 1
            # Durable timer: survives worker restarts and participates in
            # time-skipping test environments (raw asyncio.sleep would neither
            # persist across process crashes nor be skippable).
            await workflow.sleep(input.interval_seconds)
        return self._latest  # type: ignore[return-value]
