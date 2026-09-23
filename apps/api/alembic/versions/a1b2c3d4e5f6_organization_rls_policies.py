"""organization row-level security policies (ADR-004 / plan J-1)

Row Level Security on all organization-scoped tables. Applied only on
PostgreSQL (RLS is a PG feature); no-ops on SQLite for local tests.

Policies are defined but NOT force-enabled globally: the API layer sets
``app.current_org_id`` per transaction. Sessions that do not set the GUC
(e.g. alembic, superuser) bypass RLS as the table owner.

Revision ID: a1b2c3d4e5f6
Revises: fec5f4418bca
Create Date: 2026-09-21
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "fec5f4418bca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables carrying organization_id (tenant scope). Keep in sync with models.
ORG_SCOPED_TABLES = [
    "users",
    "roles",
    "audit_logs",
    "missions",
    "mission_runs",
    "products",
    "workers",
    "worker_tasks",
    "worker_messages",
    "event_journal",
    "source_connections",
    "crawl_frontier_items",
    "fetched_resources",
    "documents",
    "entities",
    "relationships",
    "signals",
    "portfolio_matches",
    "portfolio_gaps",
    "competitor_profiles",
    "competitor_events",
    "investigations",
    "claims",
    "evidence",
    "contradictions",
    "conversations",
    "leads",
    "actions",
    "learning_events",
    "feedback",
]


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return  # SQLite test runs skip RLS (it is a PG feature)

    # Helper GUC used by all policies: app.current_org_id
    op.execute(
        "CREATE OR REPLACE FUNCTION current_org_id() "
        "RETURNS TEXT AS $$ "
        "SELECT current_setting('app.current_org_id', true) "
        "$$ LANGUAGE sql STABLE"
    )

    for table in ORG_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY org_isolation_{table} ON {table} "
            f"USING (organization_id::text = current_org_id()) "
            f"WITH CHECK (organization_id::text = current_org_id())"
        )


def downgrade() -> None:
    if not _is_postgres():
        return

    for table in ORG_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS org_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS current_org_id()")
