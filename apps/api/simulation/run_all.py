"""
apps/api/simulation/run_all.py

CLI: run all 8 deterministic scenarios against the configured database.
Usage: uv run python -m simulation.run_all   (from apps/api)
"""

import asyncio

from core.config import settings
from core.database import AsyncSessionLocal, Base
import models  # noqa: F401
from simulation.engine import run_all_scenarios


async def main() -> None:
    # Ensure schema exists (dev convenience; Alembic is the real authority)
    from core.database import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Ensure the default org exists so events have a tenant
        from models import Organization

        org = await session.get(Organization, settings.DEFAULT_ORG_ID)
        if not org:
            session.add(
                Organization(
                    id=settings.DEFAULT_ORG_ID,
                    name=settings.DEFAULT_ORG_NAME,
                    slug="acme-growth",
                    plan="enterprise",
                )
            )
            await session.commit()

        results = await run_all_scenarios(session, settings.DEFAULT_ORG_ID)
        await session.commit()

    print("=" * 60)
    print("SIMULATION RUN COMPLETE (deterministic scenarios)")
    print("=" * 60)
    for r in results:
        print(f"  {r['scenario']:<30} steps={r['steps']:<3} stored={r['stored']:<3} dup_rejected={r['rejected_duplicates']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
