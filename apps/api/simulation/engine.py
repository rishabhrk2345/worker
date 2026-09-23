"""
apps/api/simulation/engine.py

Phase 5 — Deterministic Simulation Engine.

Runs scripted scenarios that emit REAL WorkerEvent envelopes through the
production EventPublisher (journal + bus). Guarantees:

- NO random timers: every event offset is a scripted constant.
- Determinism: event ids / runs / correlations are uuid5-derived from
  (scenario_name, step_index), so two runs of the same scenario produce
  byte-identical event sequences (plan Phase 5 verification gate).
"""

from __future__ import annotations

import importlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.event_publisher import EventPublisher

logger = structlog.get_logger(__name__)

SCENARIO_MODULES = [
    "simulation.scenarios.01_customer_problem",
    "simulation.scenarios.02_competitor_launch",
    "simulation.scenarios.03_cross_product",
    "simulation.scenarios.04_trend_spike",
    "simulation.scenarios.05_worker_failure",
    "simulation.scenarios.06_human_approval",
    "simulation.scenarios.07_false_positive_learning",
    "simulation.scenarios.08_portfolio_gap",
]


def _stable_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:aimarketing-os:{name}"))


def deterministic_event(
    scenario: str,
    step: int,
    organization_id: str,
    event_type: str,
    worker_id: str,
    worker_run_id: str,
    mission_id: Optional[str],
    offset_seconds: float,
    payload: Dict[str, Any],
    logical_zone: Optional[str] = None,
    logical_station: Optional[str] = None,
    task_id: Optional[str] = None,
    product_id: Optional[str] = None,
    base_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Builds a fully deterministic WorkerEvent envelope for a scenario step.
    Identical inputs always yield an identical event dict.
    """
    base = base_time or datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
    occurred = base + timedelta(seconds=offset_seconds)
    sequence = step + 1
    event_id = _stable_uuid(f"{scenario}:step:{step}")
    correlation_id = _stable_uuid(f"{scenario}:correlation")
    worker_run = _stable_uuid(f"{scenario}:run:{worker_id}") if worker_run_id == "auto" else worker_run_id
    return {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": "1.0",
        "organization_id": organization_id,
        "mission_id": mission_id,
        "task_id": task_id,
        "worker_id": worker_id,
        "worker_run_id": worker_run,
        "correlation_id": correlation_id,
        "causation_id": _stable_uuid(f"{scenario}:step:{step-1}") if step > 0 else None,
        "trace_id": _stable_uuid(f"{scenario}:trace")[:32],
        "span_id": f"{step:016x}",
        "logical_zone": logical_zone,
        "logical_station": logical_station,
        "dedupe_key": None,
        "idempotency_key": f"sha256:{scenario}:{step}:{event_type}",
        "sequence": sequence,
        "occurred_at": occurred.isoformat(),
        "payload": payload,
        "metadata": {"simulation": "true", "scenario": scenario},
    }


async def run_scenario(
    scenario_name: str,
    session: AsyncSession,
    organization_id: Optional[str] = None,
    steps_builder: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Executes one scripted scenario end-to-end.

    Returns a summary with the deterministic event fingerprint so tests can
    assert that two runs produce identical sequences.
    """
    org_id = organization_id or settings.DEFAULT_ORG_ID
    module = importlib.import_module(f"simulation.scenarios.{scenario_name}")
    steps: List[Dict[str, Any]] = module.build_steps(org_id)

    publisher = EventPublisher(session)
    stored = 0
    rejected = 0
    for i, event in enumerate(steps):
        # Re-derive determinism keys (scenarios build raw step descriptors)
        event.setdefault("organization_id", org_id)
        ok = await publisher.publish(event)
        if ok:
            stored += 1
        else:
            rejected += 1
        logger.debug(
            "simulation_event",
            scenario=scenario_name,
            step=i,
            event_type=event.get("event_type"),
            stored=ok,
        )

    fingerprint = "|".join(
        f"{e['event_type']}@{e['occurred_at']}#{e['sequence']}" for e in steps
    )
    return {
        "scenario": scenario_name,
        "steps": len(steps),
        "stored": stored,
        "rejected_duplicates": rejected,
        "fingerprint": fingerprint,
    }


async def run_all_scenarios(session: AsyncSession, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
    results = []
    for name in [
        "01_customer_problem",
        "02_competitor_launch",
        "03_cross_product",
        "04_trend_spike",
        "05_worker_failure",
        "06_human_approval",
        "07_false_positive_learning",
        "08_portfolio_gap",
    ]:
        results.append(await run_scenario(name, session, organization_id))
    return results
