"""
apps/api/models/intelligence.py

Intelligence and World Model domain:
- Entity, EntityAlias: resolved real-world entities
- Relationship: temporal knowledge graph edges
- Signal: detected market signals and conversation indicators
- PortfolioMatch: explainable multi-product match output
- PortfolioGap: unserved market opportunities
- CompetitorProfile, CompetitorEvent: digital twins
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

class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # company, person, product, competitor, topic
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    aliases: Mapped[List["EntityAlias"]] = relationship("EntityAlias", back_populates="entity", cascade="all, delete-orphan")

class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    match_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    entity: Mapped["Entity"] = relationship("Entity", back_populates="aliases")

class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    from_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    to_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # SOLVES, COMPETES_WITH, USES, INTEGRATES_WITH
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # problem, competitor_move, trend, lead_intent
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_summary: Mapped[str] = mapped_column(Text, nullable=False)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intent_score: Mapped[float] = mapped_column(Float, default=0.0)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class PortfolioMatch(Base):
    __tablename__ = "portfolio_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_id: Mapped[str] = mapped_column(String(36), ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    secondary_product_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    cross_sell_product_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    overall_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    problem_fit: Mapped[float] = mapped_column(Float, default=0.0)
    persona_fit: Mapped[float] = mapped_column(Float, default=0.0)
    industry_fit: Mapped[float] = mapped_column(Float, default=0.0)
    intent_fit: Mapped[float] = mapped_column(Float, default=0.0)

    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    match_reasons: Mapped[list] = mapped_column(JSON, default=list)
    non_match_reasons: Mapped[list] = mapped_column(JSON, default=list)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class PortfolioGap(Base):
    __tablename__ = "portfolio_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_description: Mapped[str] = mapped_column(Text, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, default=1)
    growth_rate: Mapped[float] = mapped_column(Float, default=0.0)
    target_audience: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    industries: Mapped[list] = mapped_column(JSON, default=list)
    competing_solutions: Mapped[list] = mapped_column(JSON, default=list)
    portfolio_coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class CompetitorProfile(Base):
    __tablename__ = "competitor_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str] = mapped_column(String(500), nullable=False)
    features: Mapped[list] = mapped_column(JSON, default=list)
    pricing: Mapped[dict] = mapped_column(JSON, default=dict)
    messaging: Mapped[dict] = mapped_column(JSON, default=dict)
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_scan_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class CompetitorEvent(Base):
    __tablename__ = "competitor_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    competitor_id: Mapped[str] = mapped_column(String(36), ForeignKey("competitor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False) # pricing_change, feature_launch, messaging_shift
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    impact_score: Mapped[float] = mapped_column(Float, default=0.5)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
