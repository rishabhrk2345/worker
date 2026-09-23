"""
apps/api/models/mission.py

Mission domain models:
- Mission: a long-running business objective that orchestrates the AI workforce
- MissionGoal: measurable success criteria for a mission
- MissionRun: one execution lifecycle of a mission (maps to a Temporal workflow run)

All mission tables carry organization_id for tenant isolation from day one (ADR-004).
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String, Text, Integer, Float, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PLANNED", index=True)
    # PLANNED, ACTIVE, PAUSED, COMPLETED, FAILED, CANCELLED
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True) # low, normal, high, critical
    budget_usd: Mapped[float] = mapped_column(Float, default=100.0)
    product_ids: Mapped[list] = mapped_column(JSON, default=list) # portfolio products in scope
    scheduled_cron: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    goals: Mapped[List["MissionGoal"]] = relationship("MissionGoal", back_populates="mission", cascade="all, delete-orphan")
    runs: Mapped[List["MissionRun"]] = relationship("MissionRun", back_populates="mission", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_mission_org_status", "organization_id", "status"),
    )

class MissionGoal(Base):
    __tablename__ = "mission_goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    mission_id: Mapped[str] = mapped_column(String(36), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # e.g. "qualified_leads", "coverage"
    target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    mission: Mapped["Mission"] = relationship("Mission", back_populates="goals")

class MissionRun(Base):
    __tablename__ = "mission_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    mission_id: Mapped[str] = mapped_column(String(36), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="RUNNING", index=True)
    # RUNNING, COMPLETED, FAILED, CANCELLED
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    mission: Mapped["Mission"] = relationship("Mission", back_populates="runs")
