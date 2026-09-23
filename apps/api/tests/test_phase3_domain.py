"""
apps/api/tests/test_phase3_domain.py

Phase 3 verification (plan Part 10):
- IDLE -> VERIFYING raises WorkerStateTransitionError
- Legal chains transition cleanly
- Budget enforcement: maxPages=5 -> BudgetExceededError at page 5
- Task dependency resolution: B blocked until A completes
- REST: worker transition endpoint rejects illegal moves with 409
- REST: mission create + org isolation (cross-tenant read returns 404)
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import create_access_token
from core.task_orchestration import (
    BudgetExceededError,
    BudgetManager,
    resolve_task_dependencies,
)
from core.worker_state_machine import WorkerStateMachine, WorkerStateTransitionError
from models import Mission, Organization, WorkerTask


# --------------------------------------------------------------------------
# State machine
# --------------------------------------------------------------------------

def test_illegal_transition_rejected():
    sm = WorkerStateMachine("w1", "run1", "IDLE")
    with pytest.raises(WorkerStateTransitionError):
        sm.transition("VERIFYING")  # IDLE -> VERIFYING is illegal


def test_legal_chain_transitions():
    sm = WorkerStateMachine("w1", "run1", "IDLE")
    sm.transition("DISCOVERING")
    sm.transition("SEARCHING")
    sm.transition("FETCHING")
    sm.transition("READING")
    sm.transition("ANALYZING")
    sm.transition("VERIFYING")
    sm.transition("MATCHING")
    assert sm.state.value == "MATCHING"
    assert sm.sequence == 7


def test_failure_recovery_to_idle():
    sm = WorkerStateMachine("w1", "run1", "FETCHING")
    sm.transition("FAILED")
    sm.transition("IDLE")  # supervisor reset
    assert sm.state.value == "IDLE"


def test_completed_is_terminal():
    # COMPLETED has no outgoing transitions in the contract table
    sm = WorkerStateMachine("w1", "run1", "COMPLETED")
    assert sm.can_transition("IDLE") is False
    assert sm.can_transition("SEARCHING") is False
    with pytest.raises(WorkerStateTransitionError):
        sm.transition("IDLE")


# --------------------------------------------------------------------------
# Budget enforcement (plan: maxPages=5 -> stops at 5)
# --------------------------------------------------------------------------

def test_budget_page_limit_enforced():
    bm = BudgetManager({"maxPages": 5})
    for _ in range(5):
        bm.check()          # fetches 1..5 allowed
        bm.record(pages=1)
    assert bm.pages_used == 5
    with pytest.raises(BudgetExceededError):
        bm.check()          # a 6th fetch is denied -> research stops
    assert bm.exceeded() is True


def test_budget_cost_limit_enforced():
    bm = BudgetManager({"maxCost": 1.0})
    bm.record(cost_usd=0.6)
    bm.check()
    bm.record(cost_usd=0.5)  # now 1.1 > 1.0
    with pytest.raises(BudgetExceededError):
        bm.check()


def test_unlimited_budget_never_raises():
    bm = BudgetManager({})
    for _ in range(100):
        bm.check()
        bm.record(pages=1, llm_calls=1, cost_usd=1.0)


# --------------------------------------------------------------------------
# Task dependency resolution
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependency_resolution_blocks_and_releases(test_db: AsyncSession):
    org = Organization(id="22222222-2222-2222-2222-222222222221", name="Deps", slug="deps")
    test_db.add(org)
    await test_db.flush()

    task_a = WorkerTask(
        organization_id=org.id, worker_type_required="deep_research", type="research"
    )
    test_db.add(task_a)
    await test_db.flush()  # assign task_a.id before wiring the dependency
    task_b = WorkerTask(
        organization_id=org.id, worker_type_required="content_analyzer",
        type="analyze", dependencies=[task_a.id],
    )
    test_db.add_all([task_b])
    await test_db.flush()

    # B must be blocked while A is QUEUED
    res = await resolve_task_dependencies(test_db, org.id)
    assert task_a.id in res["ready"]
    assert task_b.id in res["blocked"]

    # A completes -> B becomes ready
    task_a.status = "COMPLETED"
    res = await resolve_task_dependencies(test_db, org.id)
    assert task_b.id in res["ready"]


@pytest.mark.asyncio
async def test_dependency_failure_propagates(test_db: AsyncSession):
    org = Organization(id="22222222-2222-2222-2222-222222222222", name="Deps2", slug="deps2")
    test_db.add(org)
    await test_db.flush()

    task_a = WorkerTask(
        organization_id=org.id, worker_type_required="web_discovery", type="fetch",
        status="FAILED", failure_reason="boom",
    )
    test_db.add(task_a)
    await test_db.flush()  # assign task_a.id before wiring the dependency
    task_b = WorkerTask(
        organization_id=org.id, worker_type_required="content_analyzer",
        type="analyze", dependencies=[task_a.id],
    )
    test_db.add_all([task_b])
    await test_db.flush()

    res = await resolve_task_dependencies(test_db, org.id)
    assert task_b.id in res["failed"]


# --------------------------------------------------------------------------
# REST: worker transition + mission isolation
# --------------------------------------------------------------------------

@pytest.fixture
async def seeded_app(test_db):
    """App with dependency_overrides pointed at the test session."""
    from main import app
    from core.database import get_db

    org_a = Organization(id="33333333-3333-3333-3333-333333333331", name="OrgA", slug="org-a")
    org_b = Organization(id="33333333-3333-3333-3333-333333333332", name="OrgB", slug="org-b")
    test_db.add_all([org_a, org_b])
    await test_db.flush()

    worker = models_worker()
    worker.organization_id = org_a.id
    test_db.add(worker)
    await test_db.flush()

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    yield app, org_a, org_b, worker
    app.dependency_overrides.clear()


def models_worker():
    from models import Worker
    return Worker(
        worker_type_id="social_discovery",
        name="Test Worker",
        status="IDLE",
        logical_zone="DISCOVERY_CITY",
        autonomy_level=2,
    )


def _auth_header(org_id: str) -> dict:
    token = create_access_token(user_id="u1", organization_id=org_id, role="owner")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_worker_transition_endpoint_rejects_illegal(seeded_app):
    app, org_a, _org_b, worker = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            f"/api/workers/{worker.id}/transition",
            json={"target_state": "COMPLETED", "reason": "illegal"},
            headers=_auth_header(org_a.id),
        )
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_worker_transition_endpoint_accepts_legal(seeded_app):
    app, org_a, _org_b, worker = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            f"/api/workers/{worker.id}/transition",
            json={"target_state": "DISCOVERING", "reason": "mission_start"},
            headers=_auth_header(org_a.id),
        )
        assert resp.status_code == 200
        assert resp.json()["current_state"] == "DISCOVERING"


@pytest.mark.asyncio
async def test_mission_cross_tenant_isolation(seeded_app, test_db):
    """Org B cannot read Org A's mission (plan RLS test at app layer)."""
    app, org_a, org_b, _worker = seeded_app
    mission = Mission(
        organization_id=org_a.id, name="A's mission", objective="test", status="PLANNED"
    )
    test_db.add(mission)
    await test_db.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        # Org A sees it
        ok = await client.get(f"/api/missions/{mission.id}", headers=_auth_header(org_a.id))
        assert ok.status_code == 200

        # Org B gets 404 (never leaks existence)
        leak = await client.get(f"/api/missions/{mission.id}", headers=_auth_header(org_b.id))
        assert leak.status_code == 404

        # Org B list contains none of Org A's missions
        listing = await client.get("/api/missions", headers=_auth_header(org_b.id))
        assert listing.status_code == 200
        assert all(m["id"] != mission.id for m in listing.json())


@pytest.mark.asyncio
async def test_mission_create_and_list(seeded_app):
    app, org_a, *_rest = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        created = await client.post(
            "/api/missions",
            json={
                "name": "Q4 Attribution Push",
                "objective": "Find 50 attribution pain signals",
                "budget_usd": 250.0,
                "goals": [{"description": "50 signals", "metric": "signals", "target": 50}],
            },
            headers=_auth_header(org_a.id),
        )
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "PLANNED"
        assert len(body["goals"]) == 1
