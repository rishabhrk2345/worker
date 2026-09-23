"""
apps/api/models/worker.py

Worker domain models:
- WorkerType: capabilities, default budget, zone default
- Worker: persistent AI worker instance with logical zone/station mapping
- WorkerRun: execution lifecycle of a worker
- WorkerTask: discrete units of work with budget, retry policy, dependencies
- WorkerAttempt, WorkerMessage, WorkerHeartbeat, WorkerMetric
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

class WorkerType(Base):
    __tablename__ = "worker_types"

    id: Mapped[str] = mapped_column(String(50), primary_key=True) # e.g. "social_discovery", "deep_research"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    default_autonomy_level: Mapped[int] = mapped_column(Integer, default=2)
    default_zone: Mapped[str] = mapped_column(String(50), default="DISCOVERY_CITY")
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    default_budget: Mapped[dict] = mapped_column(JSON, default=dict)

    workers: Mapped[List["Worker"]] = relationship("Worker", back_populates="worker_type")

class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_type_id: Mapped[str] = mapped_column(String(50), ForeignKey("worker_types.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="IDLE", index=True) # IDLE, PLANNING, RESEARCHING, etc.
    logical_zone: Mapped[str] = mapped_column(String(50), default="DISCOVERY_CITY", index=True)
    logical_station: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_mission_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    current_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    current_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    autonomy_level: Mapped[int] = mapped_column(Integer, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    worker_type: Mapped["WorkerType"] = relationship("WorkerType", back_populates="workers")
    runs: Mapped[List["WorkerRun"]] = relationship("WorkerRun", back_populates="worker", cascade="all, delete-orphan")
    tasks: Mapped[List["WorkerTask"]] = relationship("WorkerTask", back_populates="worker")

class WorkerRun(Base):
    __tablename__ = "worker_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    worker_id: Mapped[str] = mapped_column(String(36), ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True)
    mission_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="RUNNING") # RUNNING, COMPLETED, FAILED, CANCELLED
    autonomy_level: Mapped[int] = mapped_column(Integer, default=2)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    pages_inspected: Mapped[int] = mapped_column(Integer, default=0)

    worker: Mapped["Worker"] = relationship("Worker", back_populates="runs")
    heartbeats: Mapped[List["WorkerHeartbeat"]] = relationship("WorkerHeartbeat", back_populates="worker_run", cascade="all, delete-orphan")
    metrics: Mapped[List["WorkerMetric"]] = relationship("WorkerMetric", back_populates="worker_run", cascade="all, delete-orphan")

class WorkerTask(Base):
    __tablename__ = "worker_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    mission_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("workers.id", ondelete="SET NULL"), nullable=True, index=True)
    worker_type_required: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal") # low, normal, high, critical
    status: Mapped[str] = mapped_column(String(50), default="QUEUED", index=True) # QUEUED, ASSIGNED, IN_PROGRESS, WAITING_APPROVAL, COMPLETED, FAILED

    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    expected_output: Mapped[dict] = mapped_column(JSON, default=dict)
    budget: Mapped[dict] = mapped_column(JSON, default=dict) # maxTime, maxPages, maxLLMCalls, maxCost
    retry_policy: Mapped[dict] = mapped_column(JSON, default=dict) # maxAttempts, backoffSeconds
    dependencies: Mapped[list] = mapped_column(JSON, default=list) # list of task IDs

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    worker: Mapped[Optional["Worker"]] = relationship("Worker", back_populates="tasks")
    attempts: Mapped[List["WorkerAttempt"]] = relationship("WorkerAttempt", back_populates="task", cascade="all, delete-orphan")

class WorkerAttempt(Base):
    __tablename__ = "worker_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("worker_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="RUNNING") # RUNNING, SUCCESS, FAILED
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    task: Mapped["WorkerTask"] = relationship("WorkerTask", back_populates="attempts")

class WorkerMessage(Base):
    __tablename__ = "worker_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    from_worker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    to_worker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    message_type: Mapped[str] = mapped_column(String(50), default="DATA_PACKAGE") # DATA_PACKAGE, STATUS_QUERY, ACK
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    worker_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("worker_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    current_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    task_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    worker_run: Mapped["WorkerRun"] = relationship("WorkerRun", back_populates="heartbeats")

class WorkerMetric(Base):
    __tablename__ = "worker_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    worker_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("worker_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    llm_tokens: Mapped[int] = mapped_column(Integer, default=0)
    llm_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    browser_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    worker_run: Mapped["WorkerRun"] = relationship("WorkerRun", back_populates="metrics")
