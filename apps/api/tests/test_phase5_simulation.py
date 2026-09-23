"""
apps/api/tests/test_phase5_simulation.py

Phase 5 verification (plan Part 10): Run scenario 1 twice -> identical
event sequence both times. Also verifies events land in the journal through
the production EventPublisher path.
"""

import pytest
from sqlalchemy import select

from core.config import settings
from core.event_publisher import EventPublisher
from models import EventJournal, Organization
from simulation.engine import run_scenario


@pytest.mark.asyncio
async def test_scenario_determinism(test_db):
    """Scenario 01 run twice -> identical event fingerprint."""
    org = Organization(id=settings.DEFAULT_ORG_ID, name="Sim", slug="sim")
    test_db.add(org)
    await test_db.flush()

    run1 = await run_scenario("01_customer_problem", test_db, org.id)
    run2 = await run_scenario("01_customer_problem", test_db, org.id)

    assert run1["steps"] == run2["steps"] == 10
    assert run1["fingerprint"] == run2["fingerprint"]

    # Second run stored 0 new rows (idempotency keys are deterministic)
    assert run1["stored"] == 10
    assert run2["stored"] == 0
    assert run2["rejected_duplicates"] == 10


@pytest.mark.asyncio
async def test_scenario_events_reach_journal(test_db):
    org = Organization(id=settings.DEFAULT_ORG_ID, name="Sim2", slug="sim2")
    test_db.add(org)
    await test_db.flush()

    await run_scenario("08_portfolio_gap", test_db, org.id)
    rows = (
        await test_db.execute(
            select(EventJournal)
            .where(EventJournal.organization_id == org.id)
            .order_by(EventJournal.sequence.asc())
        )
    ).scalars().all()

    assert len(rows) == 5
    assert rows[0].event_type == "worker.started"
    assert rows[-1].event_type == "worker.state_changed"
    assert all(r.metadata_json.get("simulation") == "true" for r in rows)


@pytest.mark.asyncio
async def test_all_scenarios_build_and_publish(test_db):
    org = Organization(id=settings.DEFAULT_ORG_ID, name="Sim3", slug="sim3")
    test_db.add(org)
    await test_db.flush()

    for name in [
        "01_customer_problem", "02_competitor_launch", "03_cross_product",
        "04_trend_spike", "05_worker_failure", "06_human_approval",
        "07_false_positive_learning", "08_portfolio_gap",
    ]:
        result = await run_scenario(name, test_db, org.id)
        assert result["steps"] > 0
        assert result["stored"] == result["steps"]
