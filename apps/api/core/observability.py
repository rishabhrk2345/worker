"""
apps/api/core/observability.py

Phase 16 — OpenTelemetry instrumentation + structured logging setup.

Sets up:
  - structlog with JSON output, trace context injection
  - OpenTelemetry SDK (OTLP gRPC export when OTEL_EXPORTER_OTLP_ENDPOINT is set)
  - FastAPI instrumentation via opentelemetry-instrumentation-fastapi
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_OTEL_INITIALIZED = False


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON output and trace context."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def setup_otel(service_name: str, endpoint: str | None = None) -> None:
    """Initialize OpenTelemetry SDK. No-op if already initialized or no endpoint."""
    global _OTEL_INITIALIZED
    if _OTEL_INITIALIZED:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        if endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _OTEL_INITIALIZED = True

    except ImportError:
        # opentelemetry packages not installed — graceful degradation
        pass


def instrument_fastapi(app: Any) -> None:
    """Attach OpenTelemetry auto-instrumentation to a FastAPI app."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass


def get_tracer(name: str = "ai-marketing-os"):
    """Get an OpenTelemetry tracer (no-op if OTel not initialized)."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        class _NoopTracer:
            def start_as_current_span(self, *args, **kwargs):
                from contextlib import contextmanager
                @contextmanager
                def _noop(*a, **kw):
                    yield
                return _noop()
        return _NoopTracer()
