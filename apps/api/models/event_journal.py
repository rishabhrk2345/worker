"""
apps/api/models/event_journal.py

EventJournal: The permanent, immutable, audit-grade event store of the AI workforce.
Every event emitted by any worker is persisted here before or concurrently with real-time broadcast.
Enforces idempotency, deduplication, causal tracking, and sequential replay.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Integer, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class EventJournal(Base):
    __tablename__ = "event_journal"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(20), default="1.0")

    # Worker & Execution context
    worker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    worker_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    mission_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Causation & Distributed Tracing
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    causation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    span_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Context identifiers
    source_connection_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Logical 3D positioning (NO coordinates in business events)
    logical_zone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    logical_station: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Deduplication & Idempotency
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Structured Payloads
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_event_org_occurred", "organization_id", "occurred_at"),
        Index("ix_event_worker_seq", "worker_run_id", "sequence"),
        Index("ix_event_mission_occurred", "mission_id", "occurred_at"),
        Index("ix_event_correlation", "correlation_id"),
    )
