"""
apps/api/core/worker_state_machine.py

Phase 3 — WorkerStateMachine (plan Part 6).

Enforces the worker state transition rules defined in
contracts/enums/worker_state.json (single source of truth). Illegal
transitions raise WorkerStateTransitionError.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from schemas.generated.enums import (
    WORKER_STATE_TRANSITIONS,
    WORKER_ANIMATION_MAP,
    WorkerState,
)
# Legal "exit-to-IDLE" re-entry is always allowed so that a supervisor can
# reset a worker between assignments (FAILED → IDLE after retry, etc.).
RESET_TO_IDLE = {"FAILED", "BLOCKED", "RATE_LIMITED"}


class WorkerStateTransitionError(ValueError):
    """Raised when a worker state transition violates the contract."""""

    def __init__(self, current: str, target: str, worker_id: str = "") -> None:
        self.current = current
        self.target = target
        self.worker_id = worker_id
        super().__init__(
            f"Illegal worker state transition {current} -> {target}"
            + (f" for worker {worker_id}" if worker_id else "")
        )


class WorkerStateMachine:
    """
    Enforces legal WorkerState transitions and produces the matching
    worker.state_changed event payload.

    Tracks a monotonic `sequence` per worker_run (plan D-3: stale events are
    dropped by comparing sequence numbers on the consumer side).
    """

    def __init__(self, worker_id: str, worker_run_id: str, initial_state: str = "IDLE") -> None:
        self.worker_id = worker_id
        self.worker_run_id = worker_run_id
        self.state = WorkerState(initial_state)
        self.sequence = 0
        self.last_transition: Optional[Tuple[str, str, datetime]] = None

    # ------------------------------------------------------------------ #
    # Core transition API
    # ------------------------------------------------------------------ #

    def can_transition(self, target: str | WorkerState) -> bool:
        target_state = WorkerState(target)
        if target_state == self.state:
            return False
        allowed = WORKER_STATE_TRANSITIONS.get(self.state, [])
        if target_state in allowed:
            return True
        # Terminal/recovery reset into IDLE (supervisor intervention)
        if target_state == WorkerState.IDLE and self.state in RESET_TO_IDLE:
            return True
        return False

    def transition(self, target: str | WorkerState, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Applies a transition and returns the worker.state_changed payload.
        Raises WorkerStateTransitionError for illegal transitions.
        """
        target_state = WorkerState(target)
        if not self.can_transition(target_state):
            raise WorkerStateTransitionError(self.state.value, target_state.value, self.worker_id)

        previous = self.state
        self.state = target_state
        self.sequence += 1
        now = datetime.now(timezone.utc)
        self.last_transition = (previous.value, target_state.value, now)

        return {
            "from_state": previous.value,
            "to_state": target_state.value,
            "reason": reason,
            "animation": WORKER_ANIMATION_MAP.get(target_state, "idle_workstation"),
            "_sequence": self.sequence,
            "_occurred_at": now.isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Event envelope builder
    # ------------------------------------------------------------------ #

    def build_state_changed_event(
        self,
        organization_id: str,
        mission_id: Optional[str] = None,
        task_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a complete worker.state_changed envelope for the current state."""
        self.sequence += 1
        now = datetime.now(timezone.utc)
        idem_source = f"{self.worker_run_id}:{self.sequence}:worker.state_changed"
        return {
            "event_id": str(uuid.uuid4()),
            "event_type": "worker.state_changed",
            "schema_version": "1.0",
            "organization_id": organization_id,
            "mission_id": mission_id,
            "task_id": task_id,
            "worker_id": self.worker_id,
            "worker_run_id": self.worker_run_id,
            "correlation_id": str(uuid.uuid5(uuid.NAMESPACE_OID, self.worker_run_id)),
            "logical_zone": None,
            "dedupe_key": None,
            "idempotency_key": f"sha256:{idem_source}",
            "sequence": self.sequence,
            "occurred_at": now.isoformat(),
            "payload": {
                "state": self.state.value,
                "from_state": getattr(self, "_last_from", None),
                "to_state": self.state.value,
                "animation": WORKER_ANIMATION_MAP.get(self.state, "idle_workstation"),
                "reason": reason,
            },
        }


# Re-export helper used above (kept trivial; avoids repeated attribute lookups)
def build_state_changed_event_worker_run_id(x: str) -> str:
    return x
