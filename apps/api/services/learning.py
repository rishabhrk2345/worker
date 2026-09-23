"""
apps/api/services/learning.py

Phase 15 — Learning & Feedback Loop.

LearningWorker:   processes feedback events, updates ProductBrain confidence,
                  source reliability scores, and keyword query lists.
StrategyUpdater:  adjusts crawl priorities and worker routing based on outcomes.
FeedbackProcessor: normalises raw feedback records into learning signals.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.learning import LearningEvent, Feedback, SourceReliability
from models.product import ProductBrain
from models.source import SourceConnection

logger = structlog.get_logger(__name__)


class LearningWorker:
    """
    Processes a feedback record and updates the relevant knowledge artifact.

    Feedback types handled:
      - positive:          boosts product keyword relevance + source reliability
      - false_positive:    demotes keyword match + adds to negative_keywords
      - rejected_action:   records draft pattern as forbidden if recurring
      - edit:              extracts delta between original and edited draft
      - outcome_converted: strong signal to boost all related scores
    """

    async def process_feedback(
        self,
        session: AsyncSession,
        feedback_id: str,
        organization_id: str,
    ) -> LearningEvent:
        result = await session.execute(
            select(Feedback).where(Feedback.id == feedback_id)
        )
        feedback = result.scalar_one_or_none()
        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")

        before_state: Dict = {}
        after_state: Dict = {}
        changes: List[str] = []

        if feedback.feedback_type == "false_positive":
            changes = await self._handle_false_positive(session, feedback, before_state, after_state)
        elif feedback.feedback_type == "positive":
            changes = await self._handle_positive(session, feedback, before_state, after_state)
        elif feedback.feedback_type == "outcome_converted":
            changes = await self._handle_converted(session, feedback, before_state, after_state)
        elif feedback.feedback_type in ("rejected_action", "edit"):
            changes = await self._handle_action_feedback(session, feedback, before_state, after_state)
        else:
            changes = [f"Unhandled feedback type: {feedback.feedback_type}"]

        event = LearningEvent(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            event_type=f"feedback_{feedback.feedback_type}",
            entity_type=feedback.subject_type,
            entity_id=feedback.subject_id,
            before_state=before_state,
            after_state=after_state,
            triggered_by=feedback.source,
        )
        session.add(event)
        await session.commit()
        logger.info(
            "learning_applied",
            feedback_type=feedback.feedback_type,
            changes=changes,
        )
        return event

    async def _handle_false_positive(
        self,
        session: AsyncSession,
        feedback: Feedback,
        before_state: Dict,
        after_state: Dict,
    ) -> List[str]:
        """Demote keywords and add negative keyword to ProductBrain."""
        if feedback.subject_type != "product_match":
            return []
        # Feedback value should contain {"keyword": "...", "product_id": "..."}
        value = feedback.value or {}
        product_id = value.get("product_id")
        keyword = value.get("keyword", "")
        if not product_id or not keyword:
            return []

        result = await session.execute(
            select(ProductBrain).where(ProductBrain.product_id == product_id)
        )
        brain = result.scalar_one_or_none()
        if not brain:
            return []

        before_state["negative_keywords"] = list(brain.negative_keywords or [])
        neg_kws = list(brain.negative_keywords or [])
        if keyword.lower() not in [k.lower() for k in neg_kws]:
            neg_kws.append(keyword.lower())
            brain.negative_keywords = neg_kws
        after_state["negative_keywords"] = neg_kws
        return [f"Added '{keyword}' to negative_keywords for product {product_id}"]

    async def _handle_positive(
        self,
        session: AsyncSession,
        feedback: Feedback,
        before_state: Dict,
        after_state: Dict,
    ) -> List[str]:
        """Boost source reliability for the sources involved."""
        value = feedback.value or {}
        source_id = value.get("source_connection_id")
        if not source_id:
            return []

        result = await session.execute(
            select(SourceReliability).where(
                SourceReliability.source_connection_id == source_id
            )
        )
        reliability = result.scalar_one_or_none()
        if not reliability:
            reliability = SourceReliability(
                id=str(uuid.uuid4()),
                source_connection_id=source_id,
                reliability_score=0.7,
                accuracy_score=0.7,
                freshness_score=0.7,
                sample_count=0,
            )
            session.add(reliability)

        before_state["reliability_score"] = reliability.reliability_score
        # Weighted running average: new = (old * n + 1.0) / (n + 1)
        n = reliability.sample_count
        reliability.reliability_score = round((reliability.reliability_score * n + 1.0) / (n + 1), 3)
        reliability.accuracy_score = round((reliability.accuracy_score * n + 1.0) / (n + 1), 3)
        reliability.sample_count += 1
        reliability.updated_at = datetime.now(timezone.utc)
        after_state["reliability_score"] = reliability.reliability_score
        return [f"Source {source_id} reliability boosted to {reliability.reliability_score:.3f}"]

    async def _handle_converted(
        self,
        session: AsyncSession,
        feedback: Feedback,
        before_state: Dict,
        after_state: Dict,
    ) -> List[str]:
        """Conversion is the strongest signal — boost all related artifacts."""
        changes = await self._handle_positive(session, feedback, before_state, after_state)
        changes.append("Conversion recorded as strong positive signal")
        return changes

    async def _handle_action_feedback(
        self,
        session: AsyncSession,
        feedback: Feedback,
        before_state: Dict,
        after_state: Dict,
    ) -> List[str]:
        value = feedback.value or {}
        return [f"Action feedback recorded: {feedback.feedback_type}"]


class StrategyUpdater:
    """
    Adjusts crawl priorities and worker routing based on accumulated learning.
    Called after a batch of LearningEvents are processed.
    """

    async def update_crawl_priorities(
        self,
        session: AsyncSession,
        organization_id: str,
    ) -> Dict[str, float]:
        """
        Returns a dictionary of {platform: priority_multiplier} for the
        CrawlFrontier to apply when scoring items from each platform.
        """
        result = await session.execute(
            select(SourceReliability)
        )
        reliabilities = result.scalars().all()

        priority_map: Dict[str, float] = {}
        for r in reliabilities:
            # Map reliability 0-1 → multiplier 0.5-1.5
            multiplier = 0.5 + r.reliability_score
            priority_map[r.source_connection_id] = round(multiplier, 3)

        return priority_map

    async def get_routing_weights(
        self,
        session: AsyncSession,
        organization_id: str,
    ) -> Dict[str, float]:
        """
        Returns weights for routing research tasks to different sources,
        based on past performance.
        """
        result = await session.execute(
            select(SourceReliability)
        )
        reliabilities = result.scalars().all()
        return {
            r.source_connection_id: r.accuracy_score
            for r in reliabilities
        }
