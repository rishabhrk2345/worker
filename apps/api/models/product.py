"""
apps/api/models/product.py

Product domain models:
- Product: dynamic portfolio product definition
- ProductBrain: deep knowledge base including problems_NOT_solved & forbidden claims
- ProductFeature, ProductProblem, ProductCompetitor, ProductRelationship
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String, Text, Boolean, DateTime, ForeignKey, Index, JSON, Float
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="SaaS")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active") # active, inactive, draft
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    brain: Mapped[Optional["ProductBrain"]] = relationship("ProductBrain", back_populates="product", uselist=False, cascade="all, delete-orphan")
    features: Mapped[List["ProductFeature"]] = relationship("ProductFeature", back_populates="product", cascade="all, delete-orphan")
    problems: Mapped[List["ProductProblem"]] = relationship("ProductProblem", back_populates="product", cascade="all, delete-orphan")
    relationships_as_a: Mapped[List["ProductRelationship"]] = relationship("ProductRelationship", foreign_keys="ProductRelationship.product_a_id", back_populates="product_a", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_product_org_slug", "organization_id", "slug", unique=True),
    )

class ProductBrain(Base):
    __tablename__ = "product_brains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Ideal Customer Profile & Personas
    icp: Mapped[str] = mapped_column(Text, default="")
    personas: Mapped[list] = mapped_column(JSON, default=list)
    industries: Mapped[list] = mapped_column(JSON, default=list)

    # Problems Solved vs NOT Solved (CRITICAL FOR FALSE-POSITIVE REDUCTION)
    problems_solved: Mapped[list] = mapped_column(JSON, default=list)
    problems_not_solved: Mapped[list] = mapped_column(JSON, default=list)
    product_boundaries: Mapped[str] = mapped_column(Text, default="")

    # Features, Use Cases, Integrations
    features: Mapped[list] = mapped_column(JSON, default=list)
    use_cases: Mapped[list] = mapped_column(JSON, default=list)
    integrations: Mapped[list] = mapped_column(JSON, default=list)

    # Customer Language & Semantics
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    semantic_concepts: Mapped[list] = mapped_column(JSON, default=list)
    customer_language: Mapped[list] = mapped_column(JSON, default=list)
    negative_keywords: Mapped[list] = mapped_column(JSON, default=list)

    # Competitors, Objections, Proof
    competitors: Mapped[list] = mapped_column(JSON, default=list)
    alternatives: Mapped[list] = mapped_column(JSON, default=list)
    objections: Mapped[list] = mapped_column(JSON, default=list)
    proof_points: Mapped[list] = mapped_column(JSON, default=list)
    pricing: Mapped[dict] = mapped_column(JSON, default=dict)

    # Claims & Compliance Policies
    approved_claims: Mapped[list] = mapped_column(JSON, default=list)
    forbidden_claims: Mapped[list] = mapped_column(JSON, default=list)
    messaging_guidelines: Mapped[dict] = mapped_column(JSON, default=dict)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    product: Mapped["Product"] = relationship("Product", back_populates="brain")

class ProductFeature(Base):
    __tablename__ = "product_features"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="core")
    status: Mapped[str] = mapped_column(String(50), default="available") # available, beta, planned

    product: Mapped["Product"] = relationship("Product", back_populates="features")

class ProductProblem(Base):
    __tablename__ = "product_problems"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    target_segment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="high") # low, medium, high, critical
    evidence_count: Mapped[int] = mapped_column(default=0)

    product: Mapped["Product"] = relationship("Product", back_populates="problems")

class ProductRelationship(Base):
    __tablename__ = "product_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    product_a_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    product_b_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False) # CROSS_SELL, UPSELL, BUNDLE, COMPETES_WITH, SIMILAR
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    product_a: Mapped["Product"] = relationship("Product", foreign_keys=[product_a_id], back_populates="relationships_as_a")
    product_b: Mapped["Product"] = relationship("Product", foreign_keys=[product_b_id])

    __table_args__ = (
        Index("ix_product_rel_pair", "product_a_id", "product_b_id", unique=True),
    )
