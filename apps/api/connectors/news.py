"""
apps/api/connectors/news.py

NewsConnector — NewsAPI.org search.
Falls back to a Google News RSS scrape when NEWSAPI_KEY is not set.

Capabilities: SEARCH, FETCH
"""

from __future__ import annotations

import os
from typing import List, Optional, Set
from urllib.parse import quote

import httpx
import structlog

from .base import BaseSourceConnector, FetchResult, SearchResult
from .registry import register
from schemas.generated.enums import SourceCapability

logger = structlog.get_logger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"
GNEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


@register("news")
class NewsConnector(BaseSourceConnector):
    platform = "news"

    def __init__(self):
        self._api_key = os.getenv("NEWSAPI_KEY", "")

    def get_capabilities(self) -> Set[SourceCapability]:
        return {SourceCapability.SEARCH, SourceCapability.FETCH, SourceCapability.RATE_LIMIT_AWARE}

    async def search(
        self, query: str, *, limit: int = 10, since: Optional[str] = None
    ) -> List[SearchResult]:
        if self._api_key:
            return await self._newsapi_search(query, limit, since)
        return await self._gnews_search(query, limit)

    async def fetch(self, url: str) -> FetchResult:
        from .website import WebsiteConnector
        return await WebsiteConnector().fetch(url)

    # ── NewsAPI ─────────────────────────────────────────────────────────────

    async def _newsapi_search(self, query: str, limit: int, since: Optional[str]) -> List[SearchResult]:
        params = {
            "q": query,
            "apiKey": self._api_key,
            "pageSize": min(limit, 100),
            "sortBy": "publishedAt",
            "language": "en",
        }
        if since:
            params["from"] = since
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(NEWSAPI_URL, params=params)
                data = resp.json()
                return [
                    SearchResult(
                        url=a.get("url", ""),
                        title=a.get("title", ""),
                        snippet=a.get("description", ""),
                        published_at=a.get("publishedAt"),
                        author=a.get("author"),
                        platform="news",
                    )
                    for a in data.get("articles", [])[:limit]
                ]
        except Exception as e:
            logger.warning("newsapi_error", error=str(e))
            return []

    # ── Google News RSS fallback ─────────────────────────────────────────────

    async def _gnews_search(self, query: str, limit: int) -> List[SearchResult]:
        from .rss import RSSConnector
        url = GNEWS_RSS_URL.format(query=quote(query))
        rss = RSSConnector()
        return await rss.search(url, limit=limit)
