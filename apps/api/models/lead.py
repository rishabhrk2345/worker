"""
apps/api/models/lead.py

Lead, Conversation, and Permissioned Action domain:
- Conversation, Comment: conversation lifecycles and thread tracking
- Lead: commercial prospects evaluated for product fit & intent
- Action: policy-governed workforce actions (drafting, CRM update, alerts)
- Approval: human-in-the-loop governance (APPROVED, EDITED, REJECTED)
- Outcome: observed feedback and conversion tracking
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

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    author_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(50), default="UNKNOWN", index=True) 
    # UNKNOWN, INTEREST, PROBLEM, SOLUTION_SEEKING, COMPARING, HIGH_INTENT, CONTACTED, RESPONDED, CONVERTED, CLOSED
    message_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="conversation", cascade="all, delete-orphan")
    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="conversation")

class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    author_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="comments")

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    target_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    problem_summary: Mapped[str] = mapped_column(Text, nullable=False)
    intent_score: Mapped[float] = mapped_column(Float, default=0.5)
    commercial_relevance: Mapped[float] = mapped_column(Float, default=0.5)
    urgency: Mapped[str] = mapped_column(String(20), default="medium")
    state: Mapped[str] = mapped_column(String(50), default="DISCOVERED", index=True)
    # DISCOVERED, QUALIFYING, QUALIFIED, DRAFT_READY, AWAITING_APPROVAL, CONTACTED, RESPONDED, CONVERTED, LOST, IGNORED
    recommended_action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", back_populates="leads")
    actions: Mapped[List["Action"]] = relationship("Action", back_populates="lead")

class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False) # draft_response, create_crm, publish_content, create_alert
    target_entity: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    draft_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING_APPROVAL", index=True)
    # PENDING_APPROVAL, APPROVED, REJECTED, EXECUTED, FAILED
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="actions")
    approvals: Mapped[List["Approval"]] = relationship("Approval", back_populates="action", cascade="all, delete-orphan")
    outcomes: Mapped[List["Outcome"]] = relationship("Outcome", back_populates="action", cascade="all, delete-orphan")

class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    action_id: Mapped[str] = mapped_column(String(36), ForeignKey("actions.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False) # APPROVED, EDITED, REJECTED
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    edited_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    action: Mapped["Action"] = relationship("Action", back_populates="approvals")

class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    action_id: Mapped[str] = mapped_column(String(36), ForeignKey("actions.id", ondelete="CASCADE"), nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(100), nullable=False) # engagement_received, lead_converted, no_response, negative_feedback
    engagement_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    converted: Mapped[bool] = mapped_column(Boolean, default=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    action: Mapped["Action"] = relationship("Action", back_populates="outcomes")
