"""
apps/api/services/competitor_intelligence.py

Phase 13 — Competitor Intelligence services.

CompetitorIntelligence:  monitors competitor websites for changes.
MarketProblemMiner:      discovers problem clusters from conversation data.
PortfolioGapDetector:    identifies unserved market problems.
AnomalyDetector:         detects mention spikes and unusual activity.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.intelligence import (
    CompetitorProfile, CompetitorEvent, Signal, PortfolioGap
)

logger = structlog.get_logger(__name__)


# ── CompetitorIntelligence ────────────────────────────────────────────────────

class CompetitorIntelligence:
    """
    Monitors competitor digital presence for meaningful changes.
    Compares current web content snapshots against stored profiles.
    """

    CHANGE_THRESHOLD = 0.15  # 15% content diff triggers a change event

    async def scan_competitor(
        self,
        session: AsyncSession,
        competitor_id: str,
        organization_id: str,
        current_content: str,
    ) -> List[CompetitorEvent]:
        """
        Compare current content to stored profile.
        Emit CompetitorEvent for detected changes.
        """
        result = await session.execute(
            select(CompetitorProfile).where(CompetitorProfile.id == competitor_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return []

        events = []
        content_lower = current_content.lower()

        # Pricing change detection
        pricing_keywords = ["$", "price", "pricing", "plan", "per month", "/mo", "annually"]
        old_pricing_str = str(profile.pricing or {}).lower()
        pricing_mentions = sum(kw in content_lower for kw in pricing_keywords)
        if pricing_mentions > 2 and self._content_changed(old_pricing_str, content_lower[:500]):
            ev = await self._record_event(
                session, competitor_id, organization_id,
                "pricing_change",
                f"Pricing content changed on {profile.website}",
                profile.website,
                impact_score=0.8,
            )
            events.append(ev)

        # Feature launch detection
        feature_keywords = ["new feature", "announcing", "introducing", "launched", "now available", "beta"]
        feature_hits = sum(kw in content_lower for kw in feature_keywords)
        if feature_hits >= 2:
            ev = await self._record_event(
                session, competitor_id, organization_id,
                "feature_launch",
                f"Possible feature announcement detected at {profile.website}",
                profile.website,
                impact_score=0.7,
            )
            events.append(ev)

        # Messaging change detection
        messaging_keywords = ["mission", "we help", "we solve", "the future of", "platform for"]
        msg_hits = sum(kw in content_lower for kw in messaging_keywords)
        old_msg_str = str(profile.messaging or {}).lower()
        if msg_hits > 0 and self._content_changed(old_msg_str, content_lower[:300]):
            ev = await self._record_event(
                session, competitor_id, organization_id,
                "messaging_shift",
                f"Homepage messaging appears to have changed at {profile.website}",
                profile.website,
                impact_score=0.5,
            )
            events.append(ev)

        # Update last scanned timestamp
        profile.last_scanned_at = datetime.now(timezone.utc)
        profile.next_scan_at = datetime.now(timezone.utc) + timedelta(hours=24)
        await session.commit()

        return events

    async def _record_event(
        self,
        session: AsyncSession,
        competitor_id: str,
        organization_id: str,
        event_type: str,
        description: str,
        source_url: str,
        impact_score: float = 0.5,
    ) -> CompetitorEvent:
        ev = CompetitorEvent(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            competitor_id=competitor_id,
            event_type=event_type,
            description=description,
            source_url=source_url,
            impact_score=impact_score,
        )
        session.add(ev)
        logger.info("competitor_event", type=event_type, competitor=competitor_id)
        return ev

    @staticmethod
    def _content_changed(old: str, new: str) -> bool:
        if not old:
            return True
        old_words = set(old.split())
        new_words = set(new.split())
        if not old_words:
            return True
        overlap = len(old_words & new_words) / len(old_words)
        return overlap < (1 - CompetitorIntelligence.CHANGE_THRESHOLD)


# ── MarketProblemMiner ─────────────────────────────────────────────────────────

class MarketProblemMiner:
    """
    Discovers problem clusters from a collection of text snippets
    (Reddit posts, reviews, support conversations).

    Groups similar problems using keyword co-occurrence.
    """

    PROBLEM_MARKERS = [
        "struggling with", "can't figure out", "problem with",
        "issue with", "broken", "doesn't work", "wish there was",
        "annoyed by", "frustrated that", "looking for a way to",
        "is there a tool", "need help with", "how do i",
        "keeps failing", "error when", "bug in",
    ]

    def mine(self, texts: List[str], min_occurrences: int = 2) -> List[Dict[str, Any]]:
        """Extract problem statements from a list of text snippets."""
        problems: List[str] = []
        for text in texts:
            text_lower = text.lower()
            for marker in self.PROBLEM_MARKERS:
                idx = text_lower.find(marker)
                if idx >= 0:
                    # Extract up to 150 chars after the marker
                    excerpt = text[idx: idx + 150].split(".")[0].strip()
                    if len(excerpt) > 20:
                        problems.append(excerpt)

        # Count word n-grams to find common themes
        word_counts: Counter = Counter()
        for p in problems:
            words = p.lower().split()
            for i in range(len(words) - 1):
                bigram = f"{words[i]} {words[i+1]}"
                word_counts[bigram] += 1

        clusters: List[Dict[str, Any]] = []
        seen: set = set()
        for problem in problems:
            key = problem[:40].lower()
            if key in seen:
                continue
            seen.add(key)
            # Score by common bigrams
            words = problem.lower().split()
            bigram_score = sum(
                word_counts.get(f"{words[i]} {words[i+1]}", 0)
                for i in range(len(words) - 1)
            )
            clusters.append({
                "problem": problem,
                "estimated_volume": bigram_score,
                "source_count": sum(1 for t in texts if problem[:20].lower() in t.lower()),
            })

        clusters.sort(key=lambda x: x["estimated_volume"], reverse=True)
        return [c for c in clusters if c["source_count"] >= min_occurrences]


# ── PortfolioGapDetector ────────────────────────────────────────────────────────

class PortfolioGapDetector:
    """
    Identifies problems from signals that no current product addresses.
    Updates PortfolioGap records with volume and opportunity scores.
    """

    async def detect_gaps(
        self,
        session: AsyncSession,
        organization_id: str,
        unmatched_problems: List[str],
    ) -> List[PortfolioGap]:
        """
        Takes a list of problem strings that had no portfolio match.
        Groups them into gap records.
        """
        gaps = []
        for problem in unmatched_problems:
            problem_key = problem[:500]

            existing = await session.execute(
                select(PortfolioGap).where(
                    PortfolioGap.organization_id == organization_id,
                    PortfolioGap.problem_description == problem_key,
                )
            )
            gap = existing.scalar_one_or_none()
            if gap:
                gap.volume += 1
                gap.growth_rate = min(gap.growth_rate + 0.05, 10.0)
                gap.last_updated_at = datetime.now(timezone.utc)
                gap.opportunity_score = min(
                    0.3 + (gap.volume * 0.05) + (gap.growth_rate * 0.1), 1.0
                )
            else:
                gap = PortfolioGap(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    problem_description=problem_key,
                    volume=1,
                    growth_rate=0.0,
                    portfolio_coverage_score=0.0,
                    opportunity_score=0.3,
                )
                session.add(gap)
            gaps.append(gap)

        await session.commit()
        return gaps


# ── AnomalyDetector ────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Detects statistical anomalies in mention frequency.
    Uses a simple rolling-window z-score approach.
    """

    def detect_spike(
        self,
        recent_counts: List[int],
        window: int = 7,
        z_threshold: float = 2.0,
    ) -> bool:
        """
        Returns True if the latest value is a spike (z-score > threshold).
        `recent_counts`: list of counts (oldest first), last = most recent.
        """
        if len(recent_counts) < window + 1:
            return False
        history = recent_counts[-window - 1: -1]
        latest = recent_counts[-1]
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = variance ** 0.5
        if std == 0:
            return False
        z = (latest - mean) / std
        return z > z_threshold
