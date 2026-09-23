"""
apps/api/connectors/rate_limiter.py

Token-bucket rate limiter per connector per organization.
Thread-safe (asyncio), in-memory. Redis-backed variant can replace
the _buckets dict for multi-process deployments.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple

import structlog

logger = structlog.get_logger(__name__)


class TokenBucket:
    """Classic token bucket: refills at `rate` tokens/second, cap at `capacity`."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int = 1) -> bool:
        """Consume `tokens`. Returns True if allowed, False if rate-limited."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.rate,
            )
            self._last_refill = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def wait_and_consume(self, tokens: int = 1) -> None:
        """Block until tokens are available, then consume."""
        while not await self.consume(tokens):
            await asyncio.sleep(1.0 / self.rate)


class RateLimitManager:
    """
    Per-(org, platform) token bucket registry.
    Default: 60 requests/minute = 1 req/sec.
    """

    def __init__(self) -> None:
        self._buckets: Dict[Tuple[str, str], TokenBucket] = {}

    def _key(self, org_id: str, platform: str) -> Tuple[str, str]:
        return (org_id, platform.lower())

    def configure(self, org_id: str, platform: str, requests_per_minute: int) -> None:
        rate = requests_per_minute / 60.0
        self._buckets[self._key(org_id, platform)] = TokenBucket(
            rate=rate,
            capacity=min(requests_per_minute, 100),  # burst cap
        )

    def _get_or_create(self, org_id: str, platform: str) -> TokenBucket:
        key = self._key(org_id, platform)
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(rate=1.0, capacity=60)
        return self._buckets[key]

    async def check(self, org_id: str, platform: str) -> bool:
        """Non-blocking check. Returns False if rate-limited."""
        bucket = self._get_or_create(org_id, platform)
        allowed = await bucket.consume()
        if not allowed:
            logger.warning("rate_limit_hit", org=org_id, platform=platform)
        return allowed

    async def wait(self, org_id: str, platform: str) -> None:
        """Block until a token is available."""
        bucket = self._get_or_create(org_id, platform)
        await bucket.wait_and_consume()


# Module-level singleton
_rate_limit_manager: RateLimitManager | None = None


def get_rate_limit_manager() -> RateLimitManager:
    global _rate_limit_manager
    if _rate_limit_manager is None:
        _rate_limit_manager = RateLimitManager()
    return _rate_limit_manager
