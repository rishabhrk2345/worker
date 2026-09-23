"""
apps/api/services/evidence_pipeline.py

Phase 12 — Evidence pipeline (ADR-008).

EvidencePipeline:   stores Claim + Evidence with full provenance.
CriticWorker:       verifies a claim against its evidence, produces Verification.
ContradictionDetector: detects conflicting claims within an investigation.
EntityResolver:     matches alias strings to canonical Entity records.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.research import Claim, Evidence, Verification, Contradiction, Investigation
from models.intelligence import Entity, EntityAlias

logger = structlog.get_logger(__name__)


# ── EvidencePipeline ─────────────────────────────────────────────────────────

class EvidencePipeline:
    """
    Creates Claim + Evidence records from raw signal data.
    Applies lineage detection to mark DERIVED evidence.
    """

    async def record_evidence(
        self,
        session: AsyncSession,
        *,
        organization_id: str,
        investigation_id: str,
        claim_statement: str,
        source_url: str,
        evidence_quote: str,
        evidence_type: str = "DIRECT",
        confidence: float = 0.8,
        source_authority: float = 0.8,
        is_independent: bool = True,
        lineage_parent_url: Optional[str] = None,
    ) -> Tuple[Claim, Evidence]:
        """Find or create a Claim, then attach Evidence to it."""

        # Find existing claim with same statement in this investigation
        result = await session.execute(
            select(Claim).where(
                Claim.investigation_id == investigation_id,
                Claim.statement == claim_statement[:1000],
            )
        )
        claim = result.scalar_one_or_none()

        if not claim:
            claim = Claim(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                investigation_id=investigation_id,
                statement=claim_statement[:1000],
                confidence=confidence,
            )
            session.add(claim)
            await session.flush()

        # Create evidence record
        ev = Evidence(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            claim_id=claim.id,
            evidence_type=evidence_type,
            source_url=source_url[:1000],
            evidence_quote=evidence_quote[:2000],
            confidence=confidence,
            source_authority=source_authority,
            is_independent=is_independent,
            lineage_parent_url=lineage_parent_url,
        )
        session.add(ev)

        # Update claim confidence (average of all evidence)
        existing_evidence = await session.execute(
            select(Evidence).where(Evidence.claim_id == claim.id)
        )
        all_ev = existing_evidence.scalars().all()
        if all_ev:
            claim.confidence = round(
                sum(e.confidence for e in all_ev) / len(all_ev), 3
            )

        await session.commit()
        return claim, ev


# ── CriticWorker ─────────────────────────────────────────────────────────────

class CriticWorker:
    """
    Verifies a claim against all its evidence.
    Produces a Verification record with verdict:
      PASS              — high confidence, no contradictions
      LOW_CONFIDENCE    — not enough strong evidence
      RESEARCH_AGAIN    — ambiguous, need more data
      CONTRADICTED      — conflicting evidence found
    """

    MIN_EVIDENCE_FOR_PASS = 2
    MIN_CONFIDENCE_FOR_PASS = 0.75

    async def verify(
        self,
        session: AsyncSession,
        claim_id: str,
        worker_id: str,
    ) -> Verification:
        # Load claim + all evidence
        claim_result = await session.execute(
            select(Claim).where(Claim.id == claim_id)
        )
        claim = claim_result.scalar_one_or_none()
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        ev_result = await session.execute(
            select(Evidence).where(Evidence.claim_id == claim_id)
        )
        evidence_list = ev_result.scalars().all()

        verdict, reason = self._evaluate(claim, evidence_list)
        checks = {
            "evidence_count": len(evidence_list),
            "avg_confidence": round(claim.confidence, 3),
            "has_contradicting": any(e.evidence_type == "CONTRADICTING" for e in evidence_list),
            "has_independent": any(e.is_independent for e in evidence_list),
        }

        verification = Verification(
            id=str(uuid.uuid4()),
            claim_id=claim_id,
            verdict=verdict,
            reason=reason,
            checks_performed=checks,
            verified_by_worker_id=worker_id,
        )
        session.add(verification)

        # Mark claim as verified if PASS
        if verdict == "PASS":
            claim.verified = True

        await session.commit()
        logger.info("claim_verified", claim_id=claim_id, verdict=verdict)
        return verification

    def _evaluate(
        self, claim: Claim, evidence_list: List[Evidence]
    ) -> Tuple[str, str]:
        if not evidence_list:
            return "LOW_CONFIDENCE", "No evidence found for this claim."

        contradicting = [e for e in evidence_list if e.evidence_type == "CONTRADICTING"]
        if contradicting:
            return (
                "CONTRADICTED",
                f"Found {len(contradicting)} contradicting evidence items. Manual review needed.",
            )

        strong_ev = [e for e in evidence_list if e.confidence >= 0.7 and e.is_independent]
        if len(strong_ev) < self.MIN_EVIDENCE_FOR_PASS:
            return (
                "LOW_CONFIDENCE",
                f"Only {len(strong_ev)} independent high-confidence evidence items (need {self.MIN_EVIDENCE_FOR_PASS}).",
            )

        if claim.confidence < self.MIN_CONFIDENCE_FOR_PASS:
            return (
                "RESEARCH_AGAIN",
                f"Aggregate confidence {claim.confidence:.0%} below threshold {self.MIN_CONFIDENCE_FOR_PASS:.0%}.",
            )

        return "PASS", f"Verified: {len(strong_ev)} independent evidence items, confidence {claim.confidence:.0%}."


# ── ContradictionDetector ─────────────────────────────────────────────────────

class ContradictionDetector:
    """
    Finds pairs of claims in an investigation that logically conflict.
    Simple heuristic: claims with contradicting evidence sharing the same
    investigation, or directly-opposing keyword patterns.
    """

    OPPOSITION_PAIRS = [
        ("increases", "decreases"), ("launched", "discontinued"),
        ("positive", "negative"), ("growing", "shrinking"),
        ("better", "worse"), ("higher", "lower"),
    ]

    async def detect(
        self,
        session: AsyncSession,
        investigation_id: str,
        organization_id: str,
    ) -> List[Contradiction]:
        result = await session.execute(
            select(Claim).where(Claim.investigation_id == investigation_id)
        )
        claims = result.scalars().all()
        contradictions = []

        for i, claim_a in enumerate(claims):
            for claim_b in claims[i + 1:]:
                if self._are_contradictory(claim_a.statement, claim_b.statement):
                    # Check if contradiction already exists
                    existing = await session.execute(
                        select(Contradiction).where(
                            Contradiction.claim_a_id == claim_a.id,
                            Contradiction.claim_b_id == claim_b.id,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    c = Contradiction(
                        id=str(uuid.uuid4()),
                        organization_id=organization_id,
                        claim_a_id=claim_a.id,
                        claim_b_id=claim_b.id,
                        description=f"Potential conflict between: '{claim_a.statement[:80]}' and '{claim_b.statement[:80]}'",
                        resolved=False,
                    )
                    session.add(c)
                    contradictions.append(c)

        if contradictions:
            await session.commit()
            logger.info(
                "contradictions_detected",
                investigation_id=investigation_id,
                count=len(contradictions),
            )

        return contradictions

    def _are_contradictory(self, text_a: str, text_b: str) -> bool:
        a_lower = text_a.lower()
        b_lower = text_b.lower()
        for word_a, word_b in self.OPPOSITION_PAIRS:
            if word_a in a_lower and word_b in b_lower:
                return True
            if word_b in a_lower and word_a in b_lower:
                return True
        return False


# ── EntityResolver ─────────────────────────────────────────────────────────────

class EntityResolver:
    """
    Resolves a raw string mention to a canonical Entity.
    Falls back to creating a new entity if no match found.
    """

    CONFIDENCE_THRESHOLD = 0.7

    async def resolve(
        self,
        session: AsyncSession,
        organization_id: str,
        mention: str,
        entity_type: str = "company",
        source_platform: Optional[str] = None,
    ) -> Entity:
        """Find existing entity by alias match, or create a new one."""
        mention_lower = mention.lower().strip()

        # Check aliases
        alias_result = await session.execute(
            select(EntityAlias).where(EntityAlias.alias.ilike(f"%{mention_lower}%"))
        )
        alias = alias_result.scalar_one_or_none()
        if alias:
            entity_result = await session.execute(
                select(Entity).where(Entity.id == alias.entity_id)
            )
            entity = entity_result.scalar_one_or_none()
            if entity:
                entity.last_seen_at = datetime.now(timezone.utc)
                await session.commit()
                return entity

        # Check canonical name
        entity_result = await session.execute(
            select(Entity).where(
                Entity.organization_id == organization_id,
                Entity.canonical_name.ilike(f"%{mention_lower}%"),
                Entity.entity_type == entity_type,
            )
        )
        entity = entity_result.scalar_one_or_none()
        if entity:
            # Add alias for future lookup
            new_alias = EntityAlias(
                id=str(uuid.uuid4()),
                entity_id=entity.id,
                alias=mention_lower,
                source_platform=source_platform,
                match_confidence=0.85,
            )
            session.add(new_alias)
            await session.commit()
            return entity

        # Create new entity
        entity = Entity(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            name=mention,
            canonical_name=mention_lower,
            entity_type=entity_type,
            confidence=0.8,
        )
        session.add(entity)
        alias = EntityAlias(
            id=str(uuid.uuid4()),
            entity_id=entity.id,
            alias=mention_lower,
            source_platform=source_platform,
            match_confidence=1.0,
        )
        session.add(alias)
        await session.commit()
        logger.info("entity_created", name=mention, type=entity_type)
        return entity
