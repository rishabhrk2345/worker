"""
apps/api/connectors/health_monitor.py

SourceHealthMonitor — tracks per-connector failure rates and transitions
the source through: NORMAL → BACKOFF → RECOVERY → FAILED (and back).

State machine:
  NORMAL    → BACKOFF    (failure_rate > 0.3 in last 10 requests)
  BACKOFF   → RECOVERY   (after backoff_seconds, try again)
  RECOVERY  → NORMAL     (3 consecutive successes)
  RECOVERY  → BACKOFF    (any failure during recovery)
  BACKOFF   → FAILED     (failure_rate > 0.8 in 20+ requests)
  FAILED    → BACKOFF    (after FAILED_RETRY_SECONDS, retry)
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

BACKOFF_SECONDS = 60
RECOVERY_REQUIRED_SUCCESSES = 3
FAILED_RETRY_SECONDS = 600
WINDOW_SIZE = 20


@dataclass
class SourceHealthState:
    source_id: str
    mode: str = "NORMAL"       # NORMAL, BURST, RECOVERY, BACKOFF, FAILED
    consecutive_successes: int = 0
    backoff_until: float = 0.0
    results: Deque[bool] = field(default_factory=lambda: deque(maxlen=WINDOW_SIZE))
    items_per_hour: int = 0
    last_error: Optional[str] = None

    def failure_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if not r) / len(self.results)

    def is_available(self) -> bool:
        if self.mode == "FAILED":
            return time.monotonic() >= self.backoff_until
        if self.mode == "BACKOFF":
            return time.monotonic() >= self.backoff_until
        return True


class SourceHealthMonitor:
    """Tracks health state for all source connections."""

    def __init__(self) -> None:
        self._states: Dict[str, SourceHealthState] = {}

    def _get(self, source_id: str) -> SourceHealthState:
        if source_id not in self._states:
            self._states[source_id] = SourceHealthState(source_id=source_id)
        return self._states[source_id]

    def record_success(self, source_id: str) -> None:
        state = self._get(source_id)
        state.results.append(True)
        state.consecutive_successes += 1
        state.last_error = None

        if state.mode == "RECOVERY":
            if state.consecutive_successes >= RECOVERY_REQUIRED_SUCCESSES:
                state.mode = "NORMAL"
                logger.info("source_recovered", source=source_id)
        elif state.mode in ("BACKOFF", "FAILED"):
            if time.monotonic() >= state.backoff_until:
                state.mode = "RECOVERY"
                state.consecutive_successes = 0

    def record_failure(self, source_id: str, error: str = "") -> None:
        state = self._get(source_id)
        state.results.append(False)
        state.consecutive_successes = 0
        state.last_error = error

        fr = state.failure_rate()
        if state.mode == "NORMAL" and fr > 0.3 and len(state.results) >= 5:
            state.mode = "BACKOFF"
            state.backoff_until = time.monotonic() + BACKOFF_SECONDS
            logger.warning("source_backoff", source=source_id, failure_rate=fr)
        elif state.mode == "RECOVERY":
            state.mode = "BACKOFF"
            state.backoff_until = time.monotonic() + BACKOFF_SECONDS
            logger.warning("source_recovery_failed", source=source_id)
        elif state.mode == "BACKOFF" and fr > 0.8 and len(state.results) >= WINDOW_SIZE:
            state.mode = "FAILED"
            state.backoff_until = time.monotonic() + FAILED_RETRY_SECONDS
            logger.error("source_failed", source=source_id)

    def get_mode(self, source_id: str) -> str:
        return self._get(source_id).mode

    def is_available(self, source_id: str) -> bool:
        return self._get(source_id).is_available()

    def get_summary(self, source_id: str) -> dict:
        s = self._get(source_id)
        return {
            "source_id": source_id,
            "mode": s.mode,
            "failure_rate": round(s.failure_rate(), 3),
            "consecutive_successes": s.consecutive_successes,
            "items_per_hour": s.items_per_hour,
            "last_error": s.last_error,
        }


_health_monitor: SourceHealthMonitor | None = None


def get_health_monitor() -> SourceHealthMonitor:
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SourceHealthMonitor()
    return _health_monitor
