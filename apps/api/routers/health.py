"""
apps/api/routers/health.py

Health endpoints:
  GET /health        — liveness probe (always 200 if process running)
  GET /health/ready  — readiness probe (200 only when DB is reachable)
"""

from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=status.HTTP_200_OK)
async def health_liveness():
    """Liveness probe — confirms the process is alive."""
    return {
        "status": "alive",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "simulation_mode": settings.SIMULATION_MODE,
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def health_readiness(response: Response, db: AsyncSession = Depends(get_db)):
    """
    Readiness probe — confirms app is ready to serve traffic.
    Returns 503 if any critical component is unavailable.
    """
    components: dict[str, str] = {}
    all_healthy = True

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        components["database"] = "healthy"
    except Exception as e:
        components["database"] = f"unhealthy: {str(e)}"
        all_healthy = False

    # Redis check
    try:
        from core.event_bus import get_event_bus
        bus = await get_event_bus()
        components["redis"] = "healthy"
    except Exception as e:
        components["redis"] = f"unavailable: {str(e)} (falling back to in-memory)"
        # Redis degradation is non-fatal

    # Temporal check (optional — non-fatal)
    components["temporal"] = "configured"

    overall = "healthy" if all_healthy else "degraded"
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall,
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "simulation_mode": settings.SIMULATION_MODE,
        "components": components,
    }
