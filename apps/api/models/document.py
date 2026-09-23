"""
apps/api/models/document.py

Crawl / Content domain models (plan Part 5):
- FetchedResource: raw HTTP fetch record (dedupe by content hash)
- Document: normalized, searchable content with embedding vector placeholder
- DocumentVersion: temporal versioning of document content for change detection

Notes:
- The `embedding` column is intentionally a JSON placeholder so the model works
  on SQLite in tests and PostgreSQL in production. A dedicated Alembic migration
  adds `content_embedding vector(1536)` via pgvector on PostgreSQL, keeping the
  single schema authority (ADR-001) intact.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Text, Integer, Float, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class FetchedResource(Base):
    __tablename__ = "fetched_resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_connection_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("source_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rendered_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    __table_args__ = (
        Index("ix_fetched_resource_org_url", "organization_id", "url"),
    )

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_connection_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("source_connections.id", ondelete="SET NULL"), nullable=True, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("fetched_resources.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON placeholder; pgvector migration swaps to vector(1536) on PostgreSQL
    content_embedding: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    versions: Mapped[list] = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_document_org_type", "organization_id", "document_type"),
    )

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    document: Mapped["Document"] = relationship("Document", back_populates="versions")
