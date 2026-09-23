"""
Shared fixtures for Phase 4 temporal tests.

These tests need TWO databases that must be the SAME database:

1. Activities open their own short-lived sessions via the module-level
   ``AsyncSessionLocal`` in ``temporal.activities.common`` /
   ``temporal.activities.domain`` (and ``EventPublisher``'s owned-session
   path uses ``core.database.AsyncSessionLocal``).
2. Tests assert directly via their own session object — sometimes WHILE the
   worker loop is executing activities (poll-until-state helpers).

We therefore swap all three session factories for one built on a shared
TEMP-FILE SQLite engine. A file-backed DB is essential here: each session
checks out its own connection (AsyncAdaptedQueuePool), so per-connection
SAVEPOINT stacks (used by the EventPublisher's idempotent-insert path) never
interleave. A single shared StaticPool connection WOULD interleave them when
the pytest-asyncio test loop and the Temporal worker loop are concurrently
active, producing "no such savepoint: sa_savepoint_N".

WAL journal mode + a generous busy_timeout let readers (test assertions)
never block writers (activities) and vice versa.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("SIMULATION_MODE", "true")

import core.database as core_database  # noqa: E402
import temporal.activities.common as t_common  # noqa: E402
import temporal.activities.domain as t_domain  # noqa: E402
from models import Organization, Worker, WorkerType  # noqa: E402
from temporal.shared import MissionInput  # noqa: E402


@pytest_asyncio.fixture
async def temporal_db():
    """Shared temp-file SQLite engine; monkeypatches all session factories."""
    fd, raw_path = tempfile.mkstemp(suffix=".db", prefix="phase4-")
    os.close(fd)
    db_path = Path(raw_path)
    # Three slashes + absolute POSIX-style path => sqlite:///C:/... on Windows.
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(core_database.Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    originals = (
        core_database.AsyncSessionLocal,
        t_common.AsyncSessionLocal,
        t_domain.AsyncSessionLocal,
    )
    core_database.AsyncSessionLocal = factory
    t_common.AsyncSessionLocal = factory
    t_domain.AsyncSessionLocal = factory

    # Seed the reference data allocation and the deterministic wave plan rely
    # on: one idle worker per worker type used by MissionWorkflow.WAVES.
    wave_types = [
        ("social_discovery", "DISCOVERY_CITY"),
        ("web_discovery", "DISCOVERY_CITY"),
        ("content_analyzer", "INTELLIGENCE_LAB"),
        ("problem_detector", "INTELLIGENCE_LAB"),
        ("deep_research", "RESEARCH_LAB"),
        ("verification", "RESEARCH_LAB"),
        ("outreach_draft", "ACTION_CENTER"),
    ]
    async with factory() as session:
        org = Organization(name="T-org", slug="t-org")
        session.add(org)
        await session.flush()
        for wtype_id, zone in wave_types:
            session.add(
                WorkerType(
                    id=wtype_id,
                    name=wtype_id,
                    role="DISCOVERY" if "discovery" in wtype_id else "ANALYST",
                    description=f"{wtype_id} workers",
                )
            )
            session.add(
                Worker(
                    organization_id=org.id,
                    worker_type_id=wtype_id,
                    name=f"{wtype_id}-1",
                    status="IDLE",
                    logical_zone=zone,
                )
            )
        await session.commit()
        org_id = org.id

    yield {"engine": engine, "factory": factory, "org_id": org_id}

    core_database.AsyncSessionLocal = originals[0]
    t_common.AsyncSessionLocal = originals[1]
    t_domain.AsyncSessionLocal = originals[2]
    await engine.dispose()
    with contextlib.suppress(OSError):
        for residue in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
            residue.unlink(missing_ok=True)


@pytest_asyncio.fixture
async def tsession(temporal_db):
    """A test-side session bound to the shared in-memory DB."""
    async with temporal_db["factory"]() as session:
        yield session


def make_mission_input(org_id: str, **overrides) -> MissionInput:
    """Minimal MissionInput for the deterministic 7-task wave plan."""
    base = dict(
        mission_id="00000000-0000-0000-0000-0000000000aa",
        organization_id=str(org_id),
        objective="prove phase 4 end to end",
        budget_usd=50.0,
        product_ids=[],
        worker_type_targets={},  # default of 1 task per worker type in WAVES
    )
    base.update(overrides)
    return MissionInput(**base)
