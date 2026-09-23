"""
apps/api/routers/simulation.py

Phase 5 — Simulation control API. Runs scripted, deterministic scenarios that
flow through the production EventPublisher. UI mode badge (plan Phase 5)
drives off settings.SIMULATION_MODE exposed by /health and /api/snapshot.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.rbac import TenantContext, get_tenant_context
from simulation import engine

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])

SCENARIOS = [
    "01_customer_problem",
    "02_competitor_launch",
    "03_cross_product",
    "04_trend_spike",
    "05_worker_failure",
    "06_human_approval",
    "07_false_positive_learning",
    "08_portfolio_gap",
]


@router.get("/scenarios")
async def list_scenarios(ctx: TenantContext = Depends(get_tenant_context)):
    return {
        "simulation_mode": settings.SIMULATION_MODE,
        "scenarios": SCENARIOS,
    }


@router.post("/run/{scenario_name}")
async def run_scenario(
    scenario_name: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if scenario_name not in SCENARIOS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown scenario: {scenario_name}")
    result = await engine.run_scenario(scenario_name, db, ctx.organization_id)
    await db.commit()
    return result


@router.post("/run-all")
async def run_all(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    results = await engine.run_all_scenarios(db, ctx.organization_id)
    await db.commit()
    return {"runs": results}
