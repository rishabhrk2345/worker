"""
apps/api/services/crawl_frontier.py

Phase 11 — CrawlFrontier service.

Priority score formula (ADR-H2):
  score = (relevance × 0.35) + (freshness × 0.20) + (intent × 0.25)
          + (information_gain × 0.20) - cost_penalty

Backed by the crawl_frontier_items table with dedupe_key unique constraint.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.source import CrawlFrontierItem

logger = structlog.get_logger(__name__)


def _compute_priority(
    relevance: float,
    freshness: float,
    intent: float,
    information_gain: float,
    cost_estimate: float = 0.1,
) -> float:
    raw = (
        relevance * 0.35
        + freshness * 0.20
        + intent * 0.25
        + information_gain * 0.20
        - min(cost_estimate * 0.1, 0.15)
    )
    return round(max(0.0, min(raw, 1.0)), 4)


def _make_dedupe_key(org_id: str, url: str) -> str:
    return hashlib.sha256(f"{org_id}:{url}".encode()).hexdigest()


class CrawlFrontier:
    """
    Manages the prioritized crawl queue.

    enqueue: add a URL (idempotent via dedupe_key).
    pop_next: claim and return the highest-priority QUEUED item.
    mark_done / mark_failed: update item state.
    """

    async def enqueue(
        self,
        session: AsyncSession,
        *,
        organization_id: str,
        url: str,
        topic: str = "",
        product_id: Optional[str] = None,
        source_connection_id: Optional[str] = None,
        relevance: float = 0.5,
        freshness: float = 0.5,
        intent: float = 0.5,
        information_gain: float = 0.5,
        cost_estimate: float = 0.1,
    ) -> Optional[CrawlFrontierItem]:
        dedupe = _make_dedupe_key(organization_id, url)

        # Idempotency: return existing item if already queued
        existing = await session.execute(
            select(CrawlFrontierItem).where(CrawlFrontierItem.dedupe_key == dedupe)
        )
        item = existing.scalar_one_or_none()
        if item:
            # Bump priority if new score is higher
            new_score = _compute_priority(relevance, freshness, intent, information_gain, cost_estimate)
            if new_score > item.priority_score:
                item.priority_score = new_score
                item.relevance = relevance
                item.freshness = freshness
                item.intent = intent
                item.information_gain = information_gain
                await session.commit()
            return item

        score = _compute_priority(relevance, freshness, intent, information_gain, cost_estimate)
        item = CrawlFrontierItem(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            source_connection_id=source_connection_id,
            url=url,
            topic=topic,
            product_id=product_id,
            priority_score=score,
            relevance=relevance,
            freshness=freshness,
            intent=intent,
            information_gain=information_gain,
            cost_estimate=cost_estimate,
            state="QUEUED",
            attempt_count=0,
            dedupe_key=dedupe,
        )
        session.add(item)
        await session.commit()
        logger.debug("frontier_enqueued", url=url[:80], score=score)
        return item

    async def pop_next(
        self,
        session: AsyncSession,
        organization_id: str,
        limit: int = 1,
    ) -> List[CrawlFrontierItem]:
        """
        Claim the highest-priority QUEUED items, transition to IN_PROGRESS.
        Uses a simple SELECT FOR UPDATE pattern.
        """
        result = await session.execute(
            select(CrawlFrontierItem)
            .where(
                CrawlFrontierItem.organization_id == organization_id,
                CrawlFrontierItem.state == "QUEUED",
            )
            .order_by(CrawlFrontierItem.priority_score.desc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        items = result.scalars().all()
        now = datetime.now(timezone.utc)
        for item in items:
            item.state = "IN_PROGRESS"
            item.last_checked_at = now
            item.attempt_count += 1
        await session.commit()
        return items

    async def mark_done(self, session: AsyncSession, item_id: str) -> None:
        result = await session.execute(
            select(CrawlFrontierItem).where(CrawlFrontierItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            item.state = "COMPLETED"
            item.last_checked_at = datetime.now(timezone.utc)
            await session.commit()

    async def mark_failed(
        self, session: AsyncSession, item_id: str, max_attempts: int = 3
    ) -> None:
        result = await session.execute(
            select(CrawlFrontierItem).where(CrawlFrontierItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item:
            if item.attempt_count >= max_attempts:
                item.state = "FAILED"
            else:
                item.state = "QUEUED"  # back to queue with lower priority
                item.priority_score = max(item.priority_score - 0.1, 0.0)
                item.next_check_at = datetime.now(timezone.utc) + timedelta(
                    minutes=5 * item.attempt_count
                )
            await session.commit()

    async def get_queue_depth(self, session: AsyncSession, organization_id: str) -> int:
        result = await session.execute(
            select(CrawlFrontierItem).where(
                CrawlFrontierItem.organization_id == organization_id,
                CrawlFrontierItem.state == "QUEUED",
            )
        )
        return len(result.scalars().all())
