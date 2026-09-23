"""
apps/api/core/rate_limiting.py

Phase 16 — Per-org API rate limiting middleware.

Uses an in-memory sliding-window counter (Redis-backed in production).
Limits: RATE_LIMIT_REQUESTS_PER_MINUTE requests per org per minute.
Returns HTTP 429 when exceeded.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings

logger = structlog.get_logger(__name__)


class SlidingWindowCounter:
    """Thread-safe sliding-window rate counter (asyncio, in-memory)."""

    def __init__(self, window_seconds: int = 60, limit: int = 120):
        self.window = window_seconds
        self.limit = limit
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        dq = self._requests[key]

        # Evict old entries
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) >= self.limit:
            return False
        dq.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        cutoff = now - self.window
        dq = self._requests[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        return max(0, self.limit - len(dq))


# Module-level counter singleton
_counter = SlidingWindowCounter(
    window_seconds=60,
    limit=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
)

# Paths that bypass rate limiting
_EXEMPT_PATHS = {"/health", "/", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Reads org ID from JWT in Authorization header (or falls back to IP).
    Applies per-org sliding-window rate limit.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _EXEMPT_PATHS or path.startswith("/ws"):
            return await call_next(request)

        # Determine rate limit key: prefer org_id from JWT, fall back to IP
        key = self._extract_key(request)

        if not _counter.is_allowed(key):
            logger.warning("rate_limit_exceeded", key=key, path=path)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please slow down.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(_counter.remaining(key))
        return response

    @staticmethod
    def _extract_key(request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                from .security import decode_access_token
                payload = decode_access_token(auth[7:])
                return f"org:{payload.get('org_id', 'unknown')}"
            except Exception:
                pass
        return f"ip:{request.client.host if request.client else 'unknown'}"
