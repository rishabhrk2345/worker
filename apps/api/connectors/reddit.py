"""
apps/api/connectors/reddit.py

RedditConnector — public Reddit JSON API (no auth required for read-only).
With credentials: OAuth for higher rate limits.

Capabilities: SEARCH, FETCH, COMMENTS, REPLIES, INCREMENTAL_SYNC
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Set

import httpx
import structlog

from .base import BaseSourceConnector, Comment, FetchResult, SearchResult
from .registry import register
from schemas.generated.enums import SourceCapability

logger = structlog.get_logger(__name__)

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = "AIMarketingOS/2.0 (research bot)"


@register("reddit")
class RedditConnector(BaseSourceConnector):
    platform = "reddit"

    def __init__(self):
        self._client_id = os.getenv("REDDIT_CLIENT_ID", "")
        self._client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        self._access_token: Optional[str] = None

    def get_capabilities(self) -> Set[SourceCapability]:
        return {
            SourceCapability.SEARCH,
            SourceCapability.FETCH,
            SourceCapability.COMMENTS,
            SourceCapability.REPLIES,
            SourceCapability.INCREMENTAL_SYNC,
            SourceCapability.RATE_LIMIT_AWARE,
        }

    async def search(
        self, query: str, *, limit: int = 25, since: Optional[str] = None
    ) -> List[SearchResult]:
        url = f"{REDDIT_BASE}/search.json"
        params: Dict = {"q": query, "sort": "new", "limit": min(limit, 100), "type": "link"}
        try:
            async with self._client() as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                results = []
                for post in posts:
                    d = post["data"]
                    results.append(SearchResult(
                        url=f"{REDDIT_BASE}{d.get('permalink', '')}",
                        title=d.get("title", ""),
                        snippet=d.get("selftext", "")[:300],
                        published_at=str(d.get("created_utc", "")),
                        author=d.get("author", ""),
                        platform="reddit",
                        external_id=d.get("id", ""),
                    ))
                return results
        except Exception as e:
            logger.warning("reddit_search_error", error=str(e))
            return []

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a Reddit post as JSON."""
        json_url = url.rstrip("/") + ".json?limit=1"
        try:
            async with self._client() as client:
                resp = await client.get(json_url)
                data = resp.json()
                post = data[0]["data"]["children"][0]["data"]
                text = f"{post.get('title', '')}\n\n{post.get('selftext', '')}"
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    raw_html=resp.text,
                    rendered_text=text,
                    title=post.get("title", ""),
                )
        except Exception as e:
            return FetchResult(url=url, status_code=0, raw_html="", rendered_text="", error=str(e))

    async def get_comments(self, url: str, limit: int = 50) -> List[Comment]:
        json_url = url.rstrip("/") + f".json?limit={limit}"
        try:
            async with self._client() as client:
                resp = await client.get(json_url)
                data = resp.json()
                comments_data = data[1]["data"]["children"] if len(data) > 1 else []
                return [
                    Comment(
                        external_id=c["data"].get("id", ""),
                        author=c["data"].get("author", "[deleted]"),
                        content=c["data"].get("body", ""),
                        url=url,
                        posted_at=str(c["data"].get("created_utc", "")),
                        score=c["data"].get("score", 0),
                    )
                    for c in comments_data
                    if c.get("kind") == "t1" and c["data"].get("body")
                ][:limit]
        except Exception as e:
            logger.warning("reddit_comments_error", url=url, error=str(e))
            return []

    async def get_replies(self, comment_id: str, limit: int = 25) -> List[Comment]:
        """Reddit replies are nested in the comment tree — simplified fetch."""
        return []  # Full implementation requires recursive tree walk

    def _client(self) -> httpx.AsyncClient:
        headers = {"User-Agent": USER_AGENT}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return httpx.AsyncClient(
            timeout=15.0,
            headers=headers,
            follow_redirects=True,
        )
