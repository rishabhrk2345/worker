"""
apps/api/models/source.py

Source domain models:
- Source: platform capability and endpoint definitions
- SourceConnection: tenant connection with AES-256 encrypted credentials
- SourceCursor: incremental crawl state tracking
- SourceHealth: adaptive health modes (NORMAL, BURST, RECOVERY, BACKOFF, FAILED)
- CrawlFrontierItem: prioritized queue items evaluated by expected value formula
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String, Text, Boolean, Integer, Float, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(50), primary_key=True) # e.g. "reddit", "x", "linkedin", "news"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSON, default=list) # e.g. ["SEARCH", "FETCH", "COMMENTS"]
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    requires_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    default_rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    connections: Mapped[List["SourceConnection"]] = relationship("SourceConnection", back_populates="source")

class SourceConnection(Base):
    __tablename__ = "source_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(50), ForeignKey("sources.id"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(100), nullable=False)
    credentials_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # AES-256-GCM b64
    status: Mapped[str] = mapped_column(String(50), default="active") # active, degraded, disabled, error
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=60)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source: Mapped["Source"] = relationship("Source", back_populates="connections")
    health: Mapped[Optional["SourceHealth"]] = relationship("SourceHealth", back_populates="connection", uselist=False, cascade="all, delete-orphan")
    cursors: Mapped[List["SourceCursor"]] = relationship("SourceCursor", back_populates="connection", cascade="all, delete-orphan")

class SourceCursor(Base):
    __tablename__ = "source_cursors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    source_connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False) # e.g. "r/saas", "keyword_roas"
    last_item_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    cursor_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    connection: Mapped["SourceConnection"] = relationship("SourceConnection", back_populates="cursors")

    __table_args__ = (
        Index("ix_source_cursor_unique", "source_connection_id", "topic", unique=True),
    )

class SourceHealth(Base):
    __tablename__ = "source_health"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    source_connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_connections.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(50), default="NORMAL") # NORMAL, BURST, RECOVERY, BACKOFF, FAILED
    items_per_hour: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_count_last_hour: Mapped[int] = mapped_column(Integer, default=0)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    connection: Mapped["SourceConnection"] = relationship("SourceConnection", back_populates="health")

class CrawlFrontierItem(Base):
    __tablename__ = "crawl_frontier_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Priority Components: Score = (relevance*0.35)+(freshness*0.20)+(intent*0.25)+(infoGain*0.20)-costPenalty
    priority_score: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    relevance: Mapped[float] = mapped_column(Float, default=0.5)
    freshness: Mapped[float] = mapped_column(Float, default=1.0)
    intent_weight: Mapped[float] = mapped_column(Float, default=0.5)
    information_gain: Mapped[float] = mapped_column(Float, default=0.5)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.01)

    state: Mapped[str] = mapped_column(String(50), default="QUEUED", index=True) # QUEUED, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
