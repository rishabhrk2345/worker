"""
apps/api/main.py

FastAPI Application Entry Point — AI Marketing Intelligence OS v2.0.

Phase 16 additions:
  - RateLimitMiddleware (per-org sliding window)
  - OpenTelemetry instrumentation
  - Structured JSON logging via structlog
  - Graceful SIGTERM shutdown
  - Readiness probe at /health/ready
"""

import asyncio
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import engine, Base
from core.event_publisher import set_default_bus, get_default_bus
from core.event_bus import get_event_bus
from core.observability import setup_logging, setup_otel, instrument_fastapi
from core.rate_limiting import RateLimitMiddleware
from routers import health, workers, products, sources, snapshot, missions, tasks, events, ws, simulation, execution, intelligence

import structlog

# ── Logging & Observability ───────────────────────────────────────────────────

setup_logging(settings.LOG_LEVEL)
setup_otel(settings.OTEL_SERVICE_NAME, settings.OTEL_EXPORTER_OTLP_ENDPOINT)
logger = structlog.get_logger(__name__)

# ── Graceful shutdown support ─────────────────────────────────────────────────

_shutdown_event = asyncio.Event()


def _handle_sigterm(*_):
    logger.info("sigterm_received", msg="Initiating graceful shutdown")
    _shutdown_event.set()


try:
    signal.signal(signal.SIGTERM, _handle_sigterm)
except (OSError, ValueError):
    pass  # SIGTERM not available on all platforms (e.g. Windows in some contexts)

# ── Application Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", env=settings.APP_ENV, simulation=settings.SIMULATION_MODE)

    # Ensure database schema is created/verified
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_ready")

    # Initialize event bus (Redis Streams with in-memory fallback)
    try:
        bus = await get_event_bus()
        set_default_bus(bus)
        logger.info("event_bus_ready", type=type(bus).__name__)
    except Exception as exc:
        logger.warning("event_bus_fallback", error=str(exc))
        set_default_bus(get_default_bus())

    yield  # ← application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("shutdown_start")
    from core.event_publisher import _default_bus
    if _default_bus is not None:
        try:
            await _default_bus.close()
        except Exception:
            pass
    await engine.dispose()
    logger.info("shutdown_complete")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous Multi-Product AI Marketing Workforce Backend API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────────────

# 1. CORS (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Rate limiting (per-org sliding window)
app.add_middleware(RateLimitMiddleware)

# 3. OpenTelemetry auto-instrumentation (after all other middleware)
instrument_fastapi(app)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(snapshot.router)
app.include_router(workers.router)
app.include_router(products.router)
app.include_router(sources.router)
app.include_router(missions.router)
app.include_router(tasks.router)
app.include_router(events.router)
app.include_router(ws.router)
app.include_router(simulation.router)
app.include_router(execution.router)
app.include_router(intelligence.router)


# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", tags=["root"])
async def root():
    return {
        "system": settings.APP_NAME,
        "version": "2.0.0",
        "status": "operational",
        "simulation_mode": settings.SIMULATION_MODE,
        "docs": "/docs",
    }
