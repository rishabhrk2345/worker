"""
apps/api/routers/sources.py

REST API endpoints for Source Observatory monitoring and connection status.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.database import get_db
from core.rbac import TenantContext, get_tenant_context
from models import Source, SourceConnection, SourceHealth

router = APIRouter(prefix="/api/sources", tags=["Sources"])

@router.get("")
async def list_sources(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all monitored sources and their connection health states.
    """
    stmt = (
        select(SourceConnection)
        .options(selectinload(SourceConnection.source), selectinload(SourceConnection.health))
        .where(SourceConnection.organization_id == ctx.organization_id)
        .order_by(SourceConnection.alias)
    )
    result = await db.execute(stmt)
    conns = result.scalars().all()

    return [
        {
            "id": c.id,
            "source_id": c.source_id,
            "name": c.source.name if c.source else c.alias,
            "platform": c.source.platform if c.source else "unknown",
            "alias": c.alias,
            "status": c.status,
            "rate_limit_per_min": c.rate_limit_per_min,
            "capabilities": c.source.capabilities if c.source else [],
            "health": {
                "mode": c.health.mode if c.health else "NORMAL",
                "items_per_hour": c.health.items_per_hour if c.health else 0,
                "success_rate": c.health.success_rate if c.health else 1.0,
                "last_error": c.health.last_error if c.health else None
            } if c.health else None
        }
        for c in conns
    ]
