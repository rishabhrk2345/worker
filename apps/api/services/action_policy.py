"""
apps/api/services/action_policy.py

Phase 14 — ActionPolicyEngine + OutcomeObserver.

ActionPolicyEngine evaluates 7 checks in sequence before allowing an action:
  1. Authorization       — does the org have permission for this action type?
  2. Product policy      — does the action comply with product's approved/forbidden claims?
  3. Source capability   — does the target platform support PUBLISH?
  4. Duplicate check     — has this exact action been attempted recently?
  5. Risk assessment     — classify risk level (low/medium/high)
  6. Approval gate       — high-risk actions require human approval
  7. Rate limit check    — org/platform rate limits

OutcomeObserver: records action results and triggers learning.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.lead import Action, Approval, Outcome
from models.product import ProductBrain

logger = structlog.get_logger(__name__)


@dataclass
class PolicyResult:
    allowed: bool
    requires_approval: bool
    risk_level: str          # low, medium, high
    denial_reason: Optional[str]
    checks: Dict[str, bool]


class ActionPolicyEngine:
    """
    Seven-layer policy check pipeline. Each check can deny outright
    or flag for approval. Returns PolicyResult.
    """

    # Action types that always require approval regardless of autonomy
    ALWAYS_APPROVE = {
        "outreach_email", "linkedin_dm", "twitter_reply",
        "blog_publish", "press_release",
    }

    # Low-risk action types (no approval needed at autonomy >= 4)
    LOW_RISK = {
        "internal_report", "slack_notification", "draft_only",
        "tag_lead", "add_to_crm",
    }

    async def evaluate(
        self,
        session: AsyncSession,
        *,
        organization_id: str,
        action_type: str,
        product_id: Optional[str],
        draft_content: str,
        target_entity: Optional[str],
        target_platform: Optional[str],
        autonomy_level: int = 3,
        org_permissions: Optional[List[str]] = None,
    ) -> PolicyResult:
        checks: Dict[str, bool] = {}

        # ── 1. Authorization ──────────────────────────────────────────────
        perms = org_permissions or ["*"]
        authorized = "*" in perms or action_type in perms
        checks["authorization"] = authorized
        if not authorized:
            return PolicyResult(False, False, "high", f"Action type '{action_type}' not authorized", checks)

        # ── 2. Product policy ──────────────────────────────────────────────
        if product_id:
            policy_ok, policy_msg = await self._check_product_policy(
                session, product_id, draft_content
            )
            checks["product_policy"] = policy_ok
            if not policy_ok:
                return PolicyResult(False, False, "high", policy_msg, checks)
        else:
            checks["product_policy"] = True

        # ── 3. Source capability ───────────────────────────────────────────
        # (Simplified: we trust that connector has PUBLISH capability if registered)
        checks["source_capability"] = True

        # ── 4. Duplicate check ────────────────────────────────────────────
        is_dup = await self._check_duplicate(
            session, organization_id, action_type, draft_content
        )
        checks["duplicate"] = not is_dup
        if is_dup:
            return PolicyResult(False, False, "low", "Duplicate action detected", checks)

        # ── 5. Risk assessment ────────────────────────────────────────────
        risk = self._assess_risk(action_type, draft_content, autonomy_level)
        checks["risk_ok"] = risk in ("low", "medium")

        # ── 6. Approval gate ──────────────────────────────────────────────
        needs_approval = (
            action_type in self.ALWAYS_APPROVE
            or risk == "high"
            or autonomy_level < 4
        ) and action_type not in self.LOW_RISK

        checks["approval_required"] = needs_approval

        # ── 7. Rate limit ─────────────────────────────────────────────────
        # Delegated to RateLimitManager at the connector level
        checks["rate_limit"] = True

        return PolicyResult(
            allowed=True,
            requires_approval=needs_approval,
            risk_level=risk,
            denial_reason=None,
            checks=checks,
        )

    async def _check_product_policy(
        self,
        session: AsyncSession,
        product_id: str,
        draft_content: str,
    ) -> Tuple[bool, str]:
        result = await session.execute(
            select(ProductBrain).where(ProductBrain.product_id == product_id)
        )
        brain = result.scalar_one_or_none()
        if not brain:
            return True, ""

        content_lower = draft_content.lower()
        for forbidden in (brain.forbidden_claims or []):
            if any(word in content_lower for word in forbidden.lower().split()[:3]):
                return False, f"Draft violates forbidden claim policy: '{forbidden[:60]}'"
        return True, ""

    async def _check_duplicate(
        self,
        session: AsyncSession,
        organization_id: str,
        action_type: str,
        draft_content: str,
    ) -> bool:
        """Check if the same action was created in the last 24 hours."""
        content_hash = hashlib.sha256(draft_content.encode()).hexdigest()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await session.execute(
            select(Action).where(
                Action.organization_id == organization_id,
                Action.action_type == action_type,
                Action.created_at > cutoff,
            )
        )
        actions = result.scalars().all()
        for action in actions:
            existing_hash = hashlib.sha256((action.draft_content or "").encode()).hexdigest()
            if existing_hash == content_hash:
                return True
        return False

    def _assess_risk(
        self, action_type: str, draft_content: str, autonomy_level: int
    ) -> str:
        if action_type in self.LOW_RISK:
            return "low"
        if action_type in self.ALWAYS_APPROVE:
            return "high" if autonomy_level < 4 else "medium"
        content_lower = draft_content.lower()
        high_risk_phrases = [
            "guaranteed", "100%", "best in class", "no other tool",
            "lawsuit", "legal", "refund", "compensation",
        ]
        if any(phrase in content_lower for phrase in high_risk_phrases):
            return "high"
        return "medium"


# ── OutcomeObserver ────────────────────────────────────────────────────────────

class OutcomeObserver:
    """
    Records the result of an executed action and triggers learning.
    Called by the outcome worker after observing engagement data.
    """

    async def record_outcome(
        self,
        session: AsyncSession,
        *,
        action_id: str,
        result: str,            # success, no_response, bounce, error
        engagement_data: Optional[Dict[str, Any]] = None,
        converted: bool = False,
    ) -> Outcome:
        outcome = Outcome(
            id=str(uuid.uuid4()),
            action_id=action_id,
            result=result,
            engagement_metrics=engagement_data or {},
            converted=converted,
        )
        session.add(outcome)

        # Update action status
        action_result = await session.execute(
            select(Action).where(Action.id == action_id)
        )
        action = action_result.scalar_one_or_none()
        if action:
            action.status = "outcome_recorded"

        await session.commit()
        logger.info("outcome_recorded", action_id=action_id, result=result, converted=converted)
        return outcome
