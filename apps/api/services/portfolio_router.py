"""
apps/api/services/portfolio_router.py

Phase 9 — PortfolioRouter (ADR-007).

Given a signal (problem statement + metadata), scores every active product
in the portfolio and returns a ranked list of PortfolioMatch results.

Scoring model (no LLM required — keyword + semantic heuristic):
  overall = 0.40 * problem_fit
           + 0.25 * intent_fit
           + 0.20 * persona_fit
           + 0.15 * industry_fit
  minus   negative_keyword_penalty (hard block if signal hits negative keyword)

False-positive reduction: products_not_solved acts as a hard exclusion list.
If the signal maps to any item in problems_not_solved, that product is skipped.
"""

from __future__ import annotations

import re
import uuid
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload

from models.product import Product, ProductBrain, ProductRelationship
from models.intelligence import Signal, PortfolioMatch, PortfolioGap

logger = structlog.get_logger(__name__)


@dataclass
class MatchResult:
    product_id: str
    product_name: str
    overall_score: float
    problem_fit: float
    persona_fit: float
    industry_fit: float
    intent_fit: float
    explanation: str
    match_reasons: List[str] = field(default_factory=list)
    non_match_reasons: List[str] = field(default_factory=list)
    cross_sell_product_id: Optional[str] = None
    cross_sell_product_name: Optional[str] = None


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _keyword_overlap(signal_tokens: List[str], keyword_list: List[str]) -> float:
    """Returns fraction of keyword_list items that appear in signal_tokens."""
    if not keyword_list:
        return 0.0
    hits = sum(
        1 for kw in keyword_list
        if any(tok in " ".join(signal_tokens) for tok in _tokenize(kw))
    )
    return min(hits / len(keyword_list), 1.0)


def _score_problem_fit(signal_text: str, brain: ProductBrain) -> tuple[float, list, list]:
    """
    Returns (score, match_reasons, non_match_reasons).
    Hard block if signal matches any problem_not_solved item.
    """
    tokens = _tokenize(signal_text)
    match_reasons: List[str] = []
    non_match_reasons: List[str] = []

    # Hard exclusion check
    for not_solved in (brain.problems_not_solved or []):
        ns_tokens = _tokenize(not_solved)
        if sum(1 for t in ns_tokens if t in tokens) >= max(1, len(ns_tokens) // 3):
            non_match_reasons.append(f"Signal matches excluded problem: {not_solved[:60]}")
            return 0.0, match_reasons, non_match_reasons

    # Negative keyword penalty
    for neg_kw in (brain.negative_keywords or []):
        if _tokenize(neg_kw)[0] in tokens if _tokenize(neg_kw) else False:
            non_match_reasons.append(f"Negative keyword matched: {neg_kw}")
            return 0.0, match_reasons, non_match_reasons

    # Keyword overlap
    kw_score = _keyword_overlap(tokens, brain.keywords or [])
    # Problems solved overlap
    ps_score = 0.0
    for p in (brain.problems_solved or []):
        p_tokens = _tokenize(p)
        hits = sum(1 for t in p_tokens if t in tokens)
        if hits >= max(1, len(p_tokens) // 4):
            ps_score = min(ps_score + 0.25, 1.0)
            match_reasons.append(f"Solves: {p[:60]}")

    # Customer language overlap
    cl_score = _keyword_overlap(tokens, brain.customer_language or [])
    if cl_score > 0.1:
        match_reasons.append("Customer language pattern matched")

    score = 0.4 * kw_score + 0.4 * ps_score + 0.2 * cl_score
    return min(score, 1.0), match_reasons, non_match_reasons


def _score_persona_fit(signal_meta: Dict[str, Any], brain: ProductBrain) -> float:
    persona_hint = (signal_meta.get("persona") or "").lower()
    industry_hint = (signal_meta.get("industry") or "").lower()
    if not persona_hint and not industry_hint:
        return 0.5  # neutral when no persona data
    score = 0.0
    for p in (brain.personas or []):
        if any(tok in persona_hint for tok in _tokenize(p)):
            score += 0.4
    for ind in (brain.industries or []):
        if any(tok in industry_hint for tok in _tokenize(ind)):
            score += 0.3
    return min(score, 1.0)


def _score_industry_fit(signal_meta: Dict[str, Any], brain: ProductBrain) -> float:
    industry_hint = (signal_meta.get("industry") or "").lower()
    if not industry_hint:
        return 0.5
    for ind in (brain.industries or []):
        if any(tok in industry_hint for tok in _tokenize(ind)):
            return 1.0
    return 0.1


def _score_intent(intent_score: float) -> float:
    """Map 0-1 intent signal score to fit component."""
    return min(intent_score * 1.2, 1.0)


class PortfolioRouter:
    """
    Scores all active products in the portfolio against a signal and
    returns ranked PortfolioMatch records, persisting them to the DB.
    """

    OVERALL_THRESHOLD = 0.35  # minimum score to produce a match

    async def route(
        self,
        session: AsyncSession,
        organization_id: str,
        signal_id: str,
        signal_text: str,
        signal_meta: Optional[Dict[str, Any]] = None,
        intent_score: float = 0.5,
    ) -> List[MatchResult]:
        meta = signal_meta or {}

        # Load all active products with their brains eagerly (avoid lazy-load in async)
        result = await session.execute(
            select(Product)
            .where(
                Product.organization_id == organization_id,
                Product.status == "active",
            )
            .options(selectinload(Product.brain))
        )
        products = result.scalars().all()

        # Load cross-sell relationships
        rel_result = await session.execute(
            select(ProductRelationship).where(
                ProductRelationship.relationship_type.in_(["CROSS_SELL", "BUNDLE"])
            )
        )
        relationships = rel_result.scalars().all()
        cross_sell_map: Dict[str, str] = {
            r.product_a_id: r.product_b_id for r in relationships
        }

        matches: List[MatchResult] = []

        for product in products:
            brain = product.brain
            if not brain:
                continue

            problem_fit, match_reasons, non_match_reasons = _score_problem_fit(
                signal_text, brain
            )
            if problem_fit == 0.0 and non_match_reasons:
                # Hard exclusion — skip entirely
                logger.debug(
                    "product_excluded",
                    product=product.name,
                    reason=non_match_reasons[0],
                )
                continue

            persona_fit = _score_persona_fit(meta, brain)
            industry_fit = _score_industry_fit(meta, brain)
            intent_fit = _score_intent(intent_score)

            overall = (
                0.40 * problem_fit
                + 0.25 * intent_fit
                + 0.20 * persona_fit
                + 0.15 * industry_fit
            )

            if overall < self.OVERALL_THRESHOLD:
                continue

            explanation = (
                f"{product.name} scores {overall:.0%} overall. "
                f"Problem fit: {problem_fit:.0%}, Intent: {intent_fit:.0%}. "
                + (f"Reasons: {'; '.join(match_reasons[:2])}." if match_reasons else "")
            )

            cross_sell_id = cross_sell_map.get(product.id)

            matches.append(
                MatchResult(
                    product_id=product.id,
                    product_name=product.name,
                    overall_score=round(overall, 4),
                    problem_fit=round(problem_fit, 4),
                    persona_fit=round(persona_fit, 4),
                    industry_fit=round(industry_fit, 4),
                    intent_fit=round(intent_fit, 4),
                    explanation=explanation,
                    match_reasons=match_reasons,
                    non_match_reasons=non_match_reasons,
                    cross_sell_product_id=cross_sell_id,
                )
            )

        # Sort descending
        matches.sort(key=lambda m: m.overall_score, reverse=True)

        # Persist matches to DB
        for i, m in enumerate(matches[:3]):  # top 3
            cross_sell_id = m.cross_sell_product_id
            row = PortfolioMatch(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                signal_id=signal_id,
                primary_product_id=m.product_id,
                secondary_product_id=matches[i + 1].product_id if i + 1 < len(matches) else None,
                cross_sell_product_id=cross_sell_id,
                overall_score=m.overall_score,
                problem_fit=m.problem_fit,
                persona_fit=m.persona_fit,
                industry_fit=m.industry_fit,
                intent_fit=m.intent_fit,
                explanation=m.explanation,
                match_reasons=m.match_reasons,
                non_match_reasons=m.non_match_reasons,
            )
            session.add(row)

        if matches:
            await session.commit()
            logger.info(
                "portfolio_match_complete",
                signal_id=signal_id,
                top_match=matches[0].product_name,
                score=matches[0].overall_score,
            )
        else:
            # Log as gap candidate
            await self._record_gap_candidate(session, organization_id, signal_text)

        return matches

    async def _record_gap_candidate(
        self,
        session: AsyncSession,
        organization_id: str,
        problem_text: str,
    ) -> None:
        """If no product matches, record as a portfolio gap candidate."""
        from sqlalchemy import func

        # Check if a similar gap already exists (exact text match for now)
        existing = await session.execute(
            select(PortfolioGap).where(
                PortfolioGap.organization_id == organization_id,
                PortfolioGap.problem_description == problem_text[:500],
            )
        )
        gap = existing.scalar_one_or_none()
        if gap:
            gap.volume += 1
            gap.last_updated_at = datetime.now(timezone.utc)
        else:
            gap = PortfolioGap(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                problem_description=problem_text[:500],
                volume=1,
                opportunity_score=0.5,
                portfolio_coverage_score=0.0,
            )
            session.add(gap)
        await session.commit()
        logger.info("portfolio_gap_recorded", problem=problem_text[:80])
