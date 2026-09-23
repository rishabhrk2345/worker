"""
apps/api/connectors/search.py

SearchConnector — SerpAPI web search.
Capabilities: SEARCH, FETCH (snippet-level)
Falls back to a DuckDuckGo HTML scrape when SERPAPI_KEY is not set.
"""

from __future__ import annotations

import os
from typing import List, Optional, Set

import httpx
import structlog

from .base import BaseSourceConnector, FetchResult, SearchResult
from .registry import register
from schemas.generated.enums import SourceCapability

logger = structlog.get_logger(__name__)

SERPAPI_URL = "https://serpapi.com/search"
DDG_URL = "https://html.duckduckgo.com/html/"


@register("search")
@register("serp")
class SearchConnector(BaseSourceConnector):
    platform = "search"

    def __init__(self):
        self._api_key = os.getenv("SERPAPI_KEY", "")

    def get_capabilities(self) -> Set[SourceCapability]:
        return {SourceCapability.SEARCH, SourceCapability.FETCH, SourceCapability.RATE_LIMIT_AWARE}

    async def search(
        self, query: str, *, limit: int = 10, since: Optional[str] = None
    ) -> List[SearchResult]:
        if self._api_key:
            return await self._serpapi_search(query, limit)
        return await self._ddg_search(query, limit)

    async def fetch(self, url: str) -> FetchResult:
        from .website import WebsiteConnector
        return await WebsiteConnector().fetch(url)

    # ── SerpAPI ─────────────────────────────────────────────────────────────

    async def _serpapi_search(self, query: str, limit: int) -> List[SearchResult]:
        params = {
            "q": query,
            "api_key": self._api_key,
            "num": limit,
            "output": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(SERPAPI_URL, params=params)
                data = resp.json()
                results = []
                for r in data.get("organic_results", [])[:limit]:
                    results.append(SearchResult(
                        url=r.get("link", ""),
                        title=r.get("title", ""),
                        snippet=r.get("snippet", ""),
                        published_at=r.get("date"),
                        platform="search",
                    ))
                return results
        except Exception as e:
            logger.warning("serpapi_error", error=str(e))
            return []

    # ── DuckDuckGo fallback ─────────────────────────────────────────────────

    async def _ddg_search(self, query: str, limit: int) -> List[SearchResult]:
        import re
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as client:
                resp = await client.post(DDG_URL, data={"q": query})
                html = resp.text
                # Extract result URLs and titles
                links = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    html,
                    re.DOTALL,
                )
                results = []
                for url, title in links[:limit]:
                    clean_title = re.sub(r"<[^>]+>", "", title).strip()
                    results.append(SearchResult(
                        url=url,
                        title=clean_title,
                        snippet="",
                        platform="search",
                    ))
                return results
        except Exception as e:
            logger.warning("ddg_search_error", error=str(e))
            return []
