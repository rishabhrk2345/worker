"""
apps/api/connectors/threads.py

ThreadsConnector — Meta Threads API (graph.threads.net).

Auth model: a long-lived Threads User Access Token.
  - Env fallback: THREADS_ACCESS_TOKEN (used when no per-org credential is set).
  - Per-org override: pass {"access_token": "..."} to connect() — this is how
    the admin panel wires in a token stored encrypted on SourceConnection
    (see routers/sources.py POST /api/sources/{source_id}/connections).

Capabilities: SEARCH, FETCH, REPLIES, RATE_LIMIT_AWARE

Notes on the underlying API:
  - Keyword search of public Threads posts requires the "Threads Keyword
    Search API" (GET /keyword_search), which is a restricted permission
    Meta grants per-app after review. Without it, search() degrades to an
    empty result with a clear health warning rather than failing hard.
  - fetch() and get_replies() work against a specific Threads media id
    (extracted from a threads.net permalink) and only require the base
    threads_basic / threads_read_replies scopes.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set

import httpx
import structlog

from .base import BaseSourceConnector, Comment, FetchResult, HealthStatus, SearchResult
from .registry import register
from schemas.generated.enums import SourceCapability

logger = structlog.get_logger(__name__)

THREADS_API_BASE = "https://graph.threads.net/v1.0"
USER_AGENT = "AIMarketingOS/2.0 (threads-research)"

MEDIA_FIELDS = "id,text,permalink,timestamp,username,media_type"


@register("threads")
class ThreadsConnector(BaseSourceConnector):
    platform = "threads"

    def __init__(self) -> None:
        self._access_token: str = os.getenv("THREADS_ACCESS_TOKEN", "")
        self._last_error: Optional[str] = None

    def get_capabilities(self) -> Set[SourceCapability]:
        return {
            SourceCapability.SEARCH,
            SourceCapability.FETCH,
            SourceCapability.REPLIES,
            SourceCapability.RATE_LIMIT_AWARE,
        }

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def connect(self, credentials: Optional[Dict[str, Any]] = None) -> None:
        """
        Called by the orchestration layer with the org's decrypted
        SourceConnection credentials, e.g. {"access_token": "THQ..."}.
        Falls back to THREADS_ACCESS_TOKEN when no override is given.
        """
        if credentials and credentials.get("access_token"):
            self._access_token = credentials["access_token"]
        self._last_error = None

    # ── SEARCH ───────────────────────────────────────────────────────────────

    async def search(
        self, query: str, *, limit: int = 25, since: Optional[str] = None
    ) -> List[SearchResult]:
        if not self._access_token:
            self._last_error = "No Threads access token configured"
            logger.warning("threads_search_no_token")
            return []
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{THREADS_API_BASE}/keyword_search",
                    params={
                        "q": query,
                        "search_type": "RECENT",
                        "fields": MEDIA_FIELDS,
                        "access_token": self._access_token,
                    },
                )
                if resp.status_code == 403:
                    # App doesn't have keyword-search access yet — degrade gracefully.
                    self._last_error = "Threads app lacks Keyword Search permission (403)"
                    logger.warning("threads_search_forbidden")
                    return []
                resp.raise_for_status()
                items = resp.json().get("data", [])
                return [self._to_search_result(it) for it in items[:limit]]
        except Exception as e:
            self._last_error = str(e)
            logger.warning("threads_search_error", query=query, error=str(e))
            return []

    # ── FETCH ────────────────────────────────────────────────────────────────

    async def fetch(self, url: str) -> FetchResult:
        media_id = self._extract_media_id(url)
        if not media_id:
            return FetchResult(
                url=url, status_code=400, raw_html="", rendered_text="",
                error="Could not extract Threads media id from URL",
            )
        if not self._access_token:
            return FetchResult(
                url=url, status_code=401, raw_html="", rendered_text="",
                error="No Threads access token configured",
            )
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{THREADS_API_BASE}/{media_id}",
                    params={"fields": MEDIA_FIELDS, "access_token": self._access_token},
                )
                resp.raise_for_status()
                data = resp.json()
                text = data.get("text", "")
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    raw_html=resp.text,
                    rendered_text=text,
                    title=text[:120],
                    author=data.get("username"),
                    published_at=data.get("timestamp"),
                )
        except Exception as e:
            self._last_error = str(e)
            return FetchResult(url=url, status_code=0, raw_html="", rendered_text="", error=str(e))

    # ── REPLIES ──────────────────────────────────────────────────────────────

    async def get_comments(self, url: str, limit: int = 50) -> List[Comment]:
        """Top-level replies to a Threads post — Threads has no separate
        'comments vs replies' distinction, so this delegates to get_replies."""
        media_id = self._extract_media_id(url)
        if not media_id:
            return []
        return await self.get_replies(media_id, limit=limit)

    async def get_replies(self, comment_id: str, limit: int = 25) -> List[Comment]:
        if not self._access_token:
            self._last_error = "No Threads access token configured"
            return []
        try:
            async with self._client() as client:
                resp = await client.get(
                    f"{THREADS_API_BASE}/{comment_id}/replies",
                    params={
                        "fields": f"{MEDIA_FIELDS},root_post,replied_to",
                        "reverse": "false",
                        "access_token": self._access_token,
                    },
                )
                resp.raise_for_status()
                items = resp.json().get("data", [])
                return [
                    Comment(
                        external_id=it.get("id", ""),
                        author=it.get("username", ""),
                        content=it.get("text", ""),
                        url=it.get("permalink", ""),
                        posted_at=it.get("timestamp"),
                        parent_id=comment_id,
                    )
                    for it in items[:limit]
                ]
        except Exception as e:
            self._last_error = str(e)
            logger.warning("threads_replies_error", comment_id=comment_id, error=str(e))
            return []

    # ── HEALTH ───────────────────────────────────────────────────────────────

    async def get_health(self) -> HealthStatus:
        if not self._access_token:
            return HealthStatus(
                healthy=False,
                mode="BLOCKED",
                last_error="No Threads access token configured — add one via the Sources admin panel",
            )
        if self._last_error:
            return HealthStatus(healthy=False, mode="BACKOFF", last_error=self._last_error)
        return HealthStatus(healthy=True, mode="NORMAL")

    async def get_rate_limit(self):
        from .base import RateLimitInfo
        return RateLimitInfo(requests_per_minute=40, requests_remaining=40)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _to_search_result(item: Dict[str, Any]) -> SearchResult:
        text = item.get("text", "") or ""
        return SearchResult(
            url=item.get("permalink", ""),
            title=text[:120],
            snippet=text[:300],
            published_at=item.get("timestamp"),
            author=item.get("username"),
            platform="threads",
            external_id=item.get("id", ""),
        )

    @staticmethod
    def _extract_media_id(url: str) -> Optional[str]:
        """
        Threads permalinks look like:
          https://www.threads.net/@user/post/CxAbCdEfGhI
        The final path segment is the shortcode the Graph API also accepts
        as a media id lookup once resolved; if the URL is already a bare id,
        pass it straight through.
        """
        m = re.search(r"/post/([A-Za-z0-9_-]+)", url)
        if m:
            return m.group(1)
        if re.fullmatch(r"[A-Za-z0-9_-]+", url):
            return url
        return None

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
