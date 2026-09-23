"""
apps/api/models/learning.py

Continuous learning and self-improvement domain:
- LearningEvent: records autonomous and human-guided adaptations to the system
- Feedback: human corrections, approval/rejection notes, false positive reports
- SourceReliability: historical accuracy and reliability ratings per connector
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Text, Float, Integer, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class LearningEvent(Base):
    __tablename__ = "learning_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    learning_type: Mapped[str] = mapped_column(String(100), nullable=False) # product_brain_updated, source_priority_changed, query_expanded
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False) # product_brain, source, worker_type
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    before_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(50), default="outcome") # human_approval, false_positive, outcome
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False) # action, portfolio_match, lead, claim
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False) # positive, false_positive, rejected_action, edit
    value_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class SourceReliability(Base):
    __tablename__ = "source_reliability"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    source_connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_connections.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    reliability_score: Mapped[float] = mapped_column(Float, default=0.8) # 0.0 to 1.0
    accuracy_score: Mapped[float] = mapped_column(Float, default=0.8)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.8)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
