"""
apps/api/connectors/youtube.py

YouTubeConnector — YouTube Data API v3.

Capabilities: SEARCH, FETCH, COMMENTS, RATE_LIMIT_AWARE

Without YOUTUBE_API_KEY: falls back to scraping the public YouTube search
page (no JS required — uses the oembed + RSS feed approach) so the connector
works out of the box even in demo / simulation mode.

With YOUTUBE_API_KEY: full API access — search by keyword, fetch video
metadata, and retrieve top-level comments.

YouTube is the primary discovery source for this system. Comment threads
on industry videos contain some of the highest-quality unsolicited problem
statements: founders, growth practitioners, and operators describe pain
points in detail when commenting on tutorials and case study videos.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, AsyncIterator, Dict, List, Optional, Set
from urllib.parse import quote

import httpx
import structlog

from .base import BaseSourceConnector, Comment, FetchResult, SearchResult
from .registry import register
from schemas.generated.enums import SourceCapability

logger = structlog.get_logger(__name__)

YT_API_BASE = "https://www.googleapis.com/youtube/v3"
YT_OEMBED   = "https://www.youtube.com/oembed"
YT_RSS_BASE = "https://www.youtube.com/feeds/videos.xml"

# Public RSS search proxy (no API key needed for recent videos by query)
INVIDIOUS_BASE = "https://inv.nadeko.net"   # public Invidious instance

USER_AGENT = "AIMarketingOS/2.0 (youtube-research; +https://aimarketingos.io)"


@register("youtube")
class YouTubeConnector(BaseSourceConnector):
    platform = "youtube"

    def __init__(self) -> None:
        self._api_key = os.getenv("YOUTUBE_API_KEY", "")

    def get_capabilities(self) -> Set[SourceCapability]:
        return {
            SourceCapability.SEARCH,
            SourceCapability.FETCH,
            SourceCapability.COMMENTS,
            SourceCapability.RATE_LIMIT_AWARE,
        }

    # ── SEARCH ───────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        since: Optional[str] = None,
    ) -> List[SearchResult]:
        if self._api_key:
            return await self._api_search(query, limit, since)
        return await self._fallback_search(query, limit)

    async def _api_search(
        self, query: str, limit: int, since: Optional[str]
    ) -> List[SearchResult]:
        params: Dict[str, Any] = {
            "part":       "snippet",
            "q":          query,
            "type":       "video",
            "maxResults": min(limit, 50),
            "order":      "relevance",
            "key":        self._api_key,
        }
        if since:
            params["publishedAfter"] = since  # RFC 3339 e.g. 2025-01-01T00:00:00Z

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{YT_API_BASE}/search", params=params)
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return [
                    SearchResult(
                        url=f"https://www.youtube.com/watch?v={it['id']['videoId']}",
                        title=it["snippet"]["title"],
                        snippet=it["snippet"]["description"][:300],
                        published_at=it["snippet"]["publishedAt"],
                        author=it["snippet"]["channelTitle"],
                        platform="youtube",
                        external_id=it["id"]["videoId"],
                    )
                    for it in items
                    if it.get("id", {}).get("videoId")
                ]
        except Exception as e:
            logger.warning("youtube_api_search_error", query=query, error=str(e))
            return await self._fallback_search(query, limit)

    async def _fallback_search(self, query: str, limit: int) -> List[SearchResult]:
        """
        No-key fallback: query a public Invidious instance JSON API.
        Invidious is an open-source YouTube front-end with a JSON API.
        Returns basic video metadata without requiring a Google API key.
        """
        try:
            url = f"{INVIDIOUS_BASE}/api/v1/search"
            params = {"q": query, "type": "video", "sort_by": "relevance"}
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                items = resp.json()
                results = []
                for v in items[:limit]:
                    vid = v.get("videoId", "")
                    if not vid:
                        continue
                    results.append(SearchResult(
                        url=f"https://www.youtube.com/watch?v={vid}",
                        title=v.get("title", ""),
                        snippet=v.get("description", "")[:300],
                        published_at=str(v.get("published", "")),
                        author=v.get("author", ""),
                        platform="youtube",
                        external_id=vid,
                    ))
                return results
        except Exception as e:
            logger.warning("youtube_fallback_search_error", query=query, error=str(e))
            return []

    # ── FETCH ─────────────────────────────────────────────────────────────────

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch video metadata. Uses oEmbed (no key needed) for title + author.
        With API key: also fetches full description and statistics.
        """
        video_id = self._extract_video_id(url)
        if not video_id:
            return FetchResult(url=url, status_code=400, raw_html="", rendered_text="",
                               error="Could not extract video ID from URL")

        if self._api_key:
            return await self._api_fetch(url, video_id)
        return await self._oembed_fetch(url, video_id)

    async def _api_fetch(self, url: str, video_id: str) -> FetchResult:
        try:
            params = {
                "part":  "snippet,statistics",
                "id":    video_id,
                "key":   self._api_key,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{YT_API_BASE}/videos", params=params)
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if not items:
                    return FetchResult(url=url, status_code=404, raw_html="",
                                       rendered_text="", error="Video not found")
                snip = items[0]["snippet"]
                stats = items[0].get("statistics", {})
                text = (
                    f"{snip['title']}\n\n"
                    f"Channel: {snip['channelTitle']}\n"
                    f"Published: {snip['publishedAt']}\n"
                    f"Views: {stats.get('viewCount', '?')}  "
                    f"Likes: {stats.get('likeCount', '?')}  "
                    f"Comments: {stats.get('commentCount', '?')}\n\n"
                    f"{snip['description']}"
                )
                return FetchResult(
                    url=url,
                    status_code=200,
                    raw_html=resp.text,
                    rendered_text=text,
                    title=snip["title"],
                    author=snip["channelTitle"],
                    published_at=snip["publishedAt"],
                )
        except Exception as e:
            logger.warning("youtube_api_fetch_error", video_id=video_id, error=str(e))
            return await self._oembed_fetch(url, video_id)

    async def _oembed_fetch(self, url: str, video_id: str) -> FetchResult:
        """oEmbed requires no API key and returns title + author."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    YT_OEMBED,
                    params={"url": url, "format": "json"},
                )
                resp.raise_for_status()
                data = resp.json()
                text = f"{data.get('title', '')}\nChannel: {data.get('author_name', '')}"
                return FetchResult(
                    url=url,
                    status_code=200,
                    raw_html=resp.text,
                    rendered_text=text,
                    title=data.get("title", ""),
                    author=data.get("author_name", ""),
                )
        except Exception as e:
            return FetchResult(url=url, status_code=0, raw_html="",
                               rendered_text="", error=str(e))

    # ── COMMENTS ─────────────────────────────────────────────────────────────

    async def get_comments(self, url: str, limit: int = 50) -> List[Comment]:
        """
        Fetch top-level comments on a video.
        Requires YOUTUBE_API_KEY — comments are not accessible without auth.
        Falls back to Invidious if key not set.
        """
        video_id = self._extract_video_id(url)
        if not video_id:
            return []

        if self._api_key:
            return await self._api_comments(url, video_id, limit)
        return await self._invidious_comments(url, video_id, limit)

    async def _api_comments(
        self, url: str, video_id: str, limit: int
    ) -> List[Comment]:
        params = {
            "part":       "snippet",
            "videoId":    video_id,
            "maxResults": min(limit, 100),
            "order":      "relevance",
            "key":        self._api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{YT_API_BASE}/commentThreads", params=params
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return [
                    Comment(
                        external_id=it["id"],
                        author=it["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"],
                        content=it["snippet"]["topLevelComment"]["snippet"]["textDisplay"],
                        url=url,
                        posted_at=it["snippet"]["topLevelComment"]["snippet"]["publishedAt"],
                        score=it["snippet"]["topLevelComment"]["snippet"].get("likeCount", 0),
                    )
                    for it in items
                ]
        except Exception as e:
            logger.warning("youtube_comments_error", video_id=video_id, error=str(e))
            return []

    async def _invidious_comments(
        self, url: str, video_id: str, limit: int
    ) -> List[Comment]:
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(
                    f"{INVIDIOUS_BASE}/api/v1/comments/{video_id}",
                    params={"type": "youtube"},
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    Comment(
                        external_id=c.get("commentId", ""),
                        author=c.get("author", ""),
                        content=c.get("content", ""),
                        url=url,
                        posted_at=str(c.get("published", "")),
                        score=c.get("likeCount", 0),
                    )
                    for c in data.get("comments", [])[:limit]
                ]
        except Exception as e:
            logger.warning("youtube_invidious_comments_error", video_id=video_id, error=str(e))
            return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from any YouTube URL format."""
        patterns = [
            r"(?:v=|v/|embed/|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$",
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    async def get_health(self):
        from .base import HealthStatus
        if self._api_key:
            return HealthStatus(healthy=True, mode="NORMAL")
        return HealthStatus(
            healthy=True,
            mode="NORMAL",
            last_error="No YOUTUBE_API_KEY set — using Invidious fallback",
        )
