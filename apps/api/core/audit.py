"""
apps/api/core/audit.py

Phase 1 — Audit logging (plan J-4).

All auth events and sensitive mutations are recorded in the audit_logs table
from day one. Never raises: audit failures must not break business flows.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog

logger = structlog.get_logger(__name__)


async def record_audit(
    session: AsyncSession,
    organization_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Records an audit entry for a sensitive action, e.g.:
      action="auth.login", entity_type="user"
      action="product.created", entity_type="product", after={...}
      action="mission.approval_granted", entity_type="approval"
    """
    try:
        entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before,
            after_state=after,
            ip_address=ip_address,
        )
        session.add(entry)
        await session.flush()
    except Exception:
        logger.exception("audit_log_write_failed", action=action, entity_type=entity_type)
