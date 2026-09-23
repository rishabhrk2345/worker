"""
apps/api/connectors/base.py

Phase 10 — BaseSourceConnector (ADR-006).

Abstract base that every connector implements.
Connectors declare capabilities via get_capabilities().
The orchestration layer only calls methods the connector has declared.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from schemas.generated.enums import SourceCapability


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    published_at: Optional[str] = None
    author: Optional[str] = None
    platform: Optional[str] = None
    external_id: Optional[str] = None


@dataclass
class FetchResult:
    url: str
    status_code: int
    raw_html: str
    rendered_text: str
    title: str = ""
    published_at: Optional[str] = None
    author: Optional[str] = None
    content_hash: str = ""
    error: Optional[str] = None


@dataclass
class Comment:
    external_id: str
    author: str
    content: str
    url: str
    posted_at: Optional[str] = None
    parent_id: Optional[str] = None
    score: int = 0


@dataclass
class HealthStatus:
    healthy: bool
    mode: str  # NORMAL, BURST, RECOVERY, BACKOFF, FAILED
    items_per_hour: int = 0
    success_rate: float = 1.0
    last_error: Optional[str] = None
    rate_limit_remaining: Optional[int] = None


@dataclass
class RateLimitInfo:
    requests_per_minute: int
    requests_remaining: int
    reset_at: Optional[str] = None


class BaseSourceConnector(abc.ABC):
    """
    Abstract connector. Subclasses implement only the methods matching
    their declared capability set.
    """

    platform: str = "unknown"

    @abc.abstractmethod
    def get_capabilities(self) -> Set[SourceCapability]:
        """Return the set of capabilities this connector supports."""
        ...

    def supports(self, capability: SourceCapability) -> bool:
        return capability in self.get_capabilities()

    # ── Core methods ────────────────────────────────────────────────────────

    async def connect(self, credentials: Optional[Dict[str, Any]] = None) -> None:
        """Initialize connection / auth. Override if needed."""

    async def close(self) -> None:
        """Teardown / close sessions."""

    # ── SEARCH ──────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        since: Optional[str] = None,
    ) -> List[SearchResult]:
        self._require(SourceCapability.SEARCH)
        raise NotImplementedError

    # ── FETCH ───────────────────────────────────────────────────────────────

    async def fetch(self, url: str) -> FetchResult:
        self._require(SourceCapability.FETCH)
        raise NotImplementedError

    # ── COMMENTS ────────────────────────────────────────────────────────────

    async def get_comments(self, url: str, limit: int = 50) -> List[Comment]:
        self._require(SourceCapability.COMMENTS)
        raise NotImplementedError

    # ── REPLIES ─────────────────────────────────────────────────────────────

    async def get_replies(self, comment_id: str, limit: int = 25) -> List[Comment]:
        self._require(SourceCapability.REPLIES)
        raise NotImplementedError

    # ── STREAM ──────────────────────────────────────────────────────────────

    async def stream_recent(self, topic: str) -> AsyncIterator[SearchResult]:
        self._require(SourceCapability.STREAM)
        raise NotImplementedError
        yield  # make this an async generator

    # ── HEALTH / RATE LIMIT ─────────────────────────────────────────────────

    async def get_health(self) -> HealthStatus:
        return HealthStatus(healthy=True, mode="NORMAL")

    async def get_rate_limit(self) -> RateLimitInfo:
        return RateLimitInfo(requests_per_minute=60, requests_remaining=60)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _require(self, cap: SourceCapability) -> None:
        if cap not in self.get_capabilities():
            raise NotImplementedError(
                f"{self.__class__.__name__} does not support {cap.value}"
            )
