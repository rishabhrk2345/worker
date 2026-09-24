"""
apps/api/routers/sources.py

REST API endpoints for the Source Observatory: monitoring/connection status,
plus the admin panel's credential management (create/update/delete a
SourceConnection and test it end-to-end against the live connector).
"""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.rbac import TenantContext, get_tenant_context, require_permission
from core.security import encrypt_credential, decrypt_credential
from models import Source, SourceConnection, SourceHealth
from connectors import build_connector

router = APIRouter(prefix="/api/sources", tags=["Sources"])


# ── Request schemas ─────────────────────────────────────────────────────────

class SourceConnectionCreateRequest(BaseModel):
    alias: str = Field(min_length=2, max_length=100)
    credentials: Dict[str, Any] = Field(default_factory=dict)
    rate_limit_per_min: Optional[int] = None


class SourceConnectionUpdateRequest(BaseModel):
    alias: Optional[str] = Field(default=None, min_length=2, max_length=100)
    credentials: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    rate_limit_per_min: Optional[int] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _connection_dict(c: SourceConnection) -> dict:
    return {
        "id": c.id,
        "source_id": c.source_id,
        "name": c.source.name if c.source else c.alias,
        "platform": c.source.platform if c.source else "unknown",
        "alias": c.alias,
        "status": c.status,
        "rate_limit_per_min": c.rate_limit_per_min,
        "has_credentials": bool(c.credentials_encrypted),
        "capabilities": c.source.capabilities if c.source else [],
        "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
        "health": {
            "mode": c.health.mode if c.health else "NORMAL",
            "items_per_hour": c.health.items_per_hour if c.health else 0,
            "success_rate": c.health.success_rate if c.health else 1.0,
            "last_error": c.health.last_error if c.health else None,
        } if c.health else None,
    }


async def _get_owned_connection(
    connection_id: str, ctx: TenantContext, db: AsyncSession
) -> SourceConnection:
    stmt = (
        select(SourceConnection)
        .options(selectinload(SourceConnection.source), selectinload(SourceConnection.health))
        .where(
            SourceConnection.id == connection_id,
            SourceConnection.organization_id == ctx.organization_id,
        )
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source connection not found")
    return conn


# ── Catalog ──────────────────────────────────────────────────────────────────

@router.get("/catalog")
async def list_source_catalog(db: AsyncSession = Depends(get_db)):
    """
    All known platforms this system knows how to crawl (Source rows), for the
    admin panel's "add a connection" picker — independent of whether the
    current org has connected them yet.
    """
    result = await db.execute(select(Source).order_by(Source.name))
    sources = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "platform": s.platform,
            "description": s.description,
            "capabilities": s.capabilities,
            "base_url": s.base_url,
            "requires_auth": s.requires_auth,
            "default_rate_limit_per_min": s.default_rate_limit_per_min,
        }
        for s in sources
    ]


# ── Connections (org-scoped) ────────────────────────────────────────────────

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
    return [_connection_dict(c) for c in conns]


@router.post("/{source_id}/connections", status_code=status.HTTP_201_CREATED)
async def create_source_connection(
    source_id: str,
    req: SourceConnectionCreateRequest,
    ctx: TenantContext = Depends(require_permission("source:write")),
    db: AsyncSession = Depends(get_db),
):
    """
    Adds a credential-backed connection to a source for this org — this is
    what the admin panel's "Save credentials" button calls. Credentials are
    AES-256-GCM encrypted before they touch the database; the plaintext is
    never persisted or logged.
    """
    src = await db.get(Source, source_id)
    if not src:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown source '{source_id}'")

    conn = SourceConnection(
        organization_id=ctx.organization_id,
        source_id=source_id,
        alias=req.alias,
        credentials_encrypted=encrypt_credential(_dumps(req.credentials)) if req.credentials else None,
        status="active",
        rate_limit_per_min=req.rate_limit_per_min or src.default_rate_limit_per_min,
    )
    db.add(conn)
    await db.flush()

    health = SourceHealth(source_connection_id=conn.id, mode="NORMAL")
    db.add(health)
    await db.commit()

    conn.source = src
    conn.health = health
    return _connection_dict(conn)


@router.patch("/connections/{connection_id}")
async def update_source_connection(
    connection_id: str,
    req: SourceConnectionUpdateRequest,
    ctx: TenantContext = Depends(require_permission("source:write")),
    db: AsyncSession = Depends(get_db),
):
    """Rotate credentials, rename, pause/resume, or re-rate-limit a connection."""
    conn = await _get_owned_connection(connection_id, ctx, db)

    if req.alias is not None:
        conn.alias = req.alias
    if req.credentials is not None:
        conn.credentials_encrypted = encrypt_credential(_dumps(req.credentials)) if req.credentials else None
    if req.status is not None:
        conn.status = req.status
    if req.rate_limit_per_min is not None:
        conn.rate_limit_per_min = req.rate_limit_per_min

    await db.commit()
    return _connection_dict(conn)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source_connection(
    connection_id: str,
    ctx: TenantContext = Depends(require_permission("source:write")),
    db: AsyncSession = Depends(get_db),
):
    conn = await _get_owned_connection(connection_id, ctx, db)
    await db.delete(conn)
    await db.commit()


@router.post("/connections/{connection_id}/test")
async def test_source_connection(
    connection_id: str,
    ctx: TenantContext = Depends(require_permission("source:write")),
    db: AsyncSession = Depends(get_db),
):
    """
    Builds the real connector for this connection, hands it the decrypted
    credentials, and reports back live health — so the admin panel can show
    "Connected" / "Failed: <reason>" right after a credential is pasted in.
    """
    conn = await _get_owned_connection(connection_id, ctx, db)

    connector = build_connector(conn.source_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"No connector implementation registered for '{conn.source_id}' yet",
        )

    credentials: Dict[str, Any] = {}
    if conn.credentials_encrypted:
        try:
            credentials = _loads(decrypt_credential(conn.credentials_encrypted))
        except Exception:
            # Legacy/seed-demo connections stored a raw (non-JSON) placeholder
            # string — treat as "no usable credentials" instead of a hard 500.
            credentials = {}

    await connector.connect(credentials)
    health = await connector.get_health()
    await connector.close()

    if not conn.health:
        conn.health = SourceHealth(source_connection_id=conn.id)
        db.add(conn.health)
    conn.health.mode = health.mode
    conn.health.success_rate = health.success_rate
    conn.health.last_error = health.last_error
    conn.status = "active" if health.healthy else "error"
    await db.commit()

    return {
        "healthy": health.healthy,
        "mode": health.mode,
        "last_error": health.last_error,
    }


# ── JSON helpers ─────────────────────────────────────────────────────────────

def _dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data)


def _loads(data: str) -> Dict[str, Any]:
    return json.loads(data)
