"""
apps/api/routers/intelligence.py

Phase 9 — Portfolio matching, gap detection, and intelligence endpoints.
"""

from __future__ import annotations

import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.rbac import get_tenant_context, TenantContext
from models.intelligence import Signal, PortfolioMatch, PortfolioGap
from services.portfolio_router import PortfolioRouter

router = APIRouter(prefix="/api/intelligence", tags=["Intelligence"])

_portfolio_router = PortfolioRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class MatchSignalRequest(BaseModel):
    problem_statement: str
    intent_score: float = 0.5
    persona: Optional[str] = None
    industry: Optional[str] = None
    source_url: Optional[str] = None


class MatchResult(BaseModel):
    product_id: str
    product_name: str
    overall_score: float
    problem_fit: float
    persona_fit: float
    industry_fit: float
    intent_fit: float
    explanation: str
    match_reasons: list
    non_match_reasons: list
    cross_sell_product_id: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/match", response_model=List[MatchResult])
async def match_signal_to_portfolio(
    req: MatchSignalRequest,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """
    Route a problem signal through the portfolio to find matching products.
    Applies false-positive reduction via problems_not_solved.
    """
    # Create a Signal record
    signal = Signal(
        id=str(uuid.uuid4()),
        organization_id=tenant.organization_id,
        signal_type="problem",
        source_url=req.source_url or "api:direct",
        content_summary=req.problem_statement[:500],
        problem_statement=req.problem_statement,
        intent_score=req.intent_score,
    )
    db.add(signal)
    await db.flush()

    matches = await _portfolio_router.route(
        session=db,
        organization_id=tenant.organization_id,
        signal_id=signal.id,
        signal_text=req.problem_statement,
        signal_meta={
            "persona": req.persona or "",
            "industry": req.industry or "",
        },
        intent_score=req.intent_score,
    )

    return [
        MatchResult(
            product_id=m.product_id,
            product_name=m.product_name,
            overall_score=m.overall_score,
            problem_fit=m.problem_fit,
            persona_fit=m.persona_fit,
            industry_fit=m.industry_fit,
            intent_fit=m.intent_fit,
            explanation=m.explanation,
            match_reasons=m.match_reasons,
            non_match_reasons=m.non_match_reasons,
            cross_sell_product_id=m.cross_sell_product_id,
        )
        for m in matches
    ]


@router.get("/gaps")
async def get_portfolio_gaps(
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Return all detected portfolio gaps, ordered by opportunity score."""
    result = await db.execute(
        select(PortfolioGap)
        .where(PortfolioGap.organization_id == tenant.organization_id)
        .order_by(PortfolioGap.opportunity_score.desc())
        .limit(50)
    )
    gaps = result.scalars().all()
    return [
        {
            "id": g.id,
            "problem_description": g.problem_description,
            "volume": g.volume,
            "growth_rate": g.growth_rate,
            "opportunity_score": g.opportunity_score,
            "portfolio_coverage_score": g.portfolio_coverage_score,
            "first_detected_at": g.first_detected_at.isoformat(),
        }
        for g in gaps
    ]


@router.get("/matches")
async def get_portfolio_matches(
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    """Return recent portfolio match results."""
    result = await db.execute(
        select(PortfolioMatch)
        .where(PortfolioMatch.organization_id == tenant.organization_id)
        .order_by(PortfolioMatch.matched_at.desc())
        .limit(100)
    )
    matches = result.scalars().all()
    return [
        {
            "id": m.id,
            "signal_id": m.signal_id,
            "primary_product_id": m.primary_product_id,
            "overall_score": m.overall_score,
            "problem_fit": m.problem_fit,
            "explanation": m.explanation,
            "matched_at": m.matched_at.isoformat(),
        }
        for m in matches
    ]
