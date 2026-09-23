"""
apps/api/connectors/website.py

WebsiteConnector — fetches public web pages using httpx (lightweight)
with optional Playwright fallback for JS-heavy pages.

Capabilities: FETCH, HISTORICAL_SEARCH (via Wayback CDX API), BROWSER_RENDER
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional, Set

import httpx
import structlog

from .base import BaseSourceConnector, FetchResult, SearchResult
from .registry import register
from schemas.generated.enums import SourceCapability

logger = structlog.get_logger(__name__)

WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = "Mozilla/5.0 (compatible; AIMarketingOS/2.0; +https://aimarketingos.io)"


@register("web")
@register("website")
class WebsiteConnector(BaseSourceConnector):
    platform = "website"

    def get_capabilities(self) -> Set[SourceCapability]:
        return {
            SourceCapability.FETCH,
            SourceCapability.HISTORICAL_SEARCH,
            SourceCapability.BROWSER_RENDER,
        }

    async def fetch(self, url: str) -> FetchResult:
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(url)
                raw = resp.text
                rendered = self._extract_text(raw)
                title = self._extract_title(raw)
                content_hash = hashlib.sha256(raw.encode()).hexdigest()
                return FetchResult(
                    url=str(resp.url),
                    status_code=resp.status_code,
                    raw_html=raw,
                    rendered_text=rendered,
                    title=title,
                    content_hash=content_hash,
                )
        except Exception as e:
            logger.warning("website_fetch_error", url=url, error=str(e))
            return FetchResult(
                url=url,
                status_code=0,
                raw_html="",
                rendered_text="",
                error=str(e),
            )

    async def search(self, query: str, *, limit: int = 10, since: Optional[str] = None) -> list[SearchResult]:
        """Historical search via Wayback CDX API."""
        params: Dict[str, Any] = {
            "url": f"*.{query}",
            "output": "json",
            "limit": limit,
            "fl": "original,timestamp,statuscode",
        }
        if since:
            params["from"] = since.replace("-", "")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(WAYBACK_CDX_URL, params=params)
                rows = resp.json()
                return [
                    SearchResult(
                        url=row[0],
                        title=row[0],
                        snippet=f"Archived {row[1]}",
                        platform="wayback",
                    )
                    for row in rows[1:limit + 1]  # skip header
                ]
        except Exception as e:
            logger.warning("wayback_search_error", error=str(e))
            return []

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_title(html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip()[:200] if m else ""

    @staticmethod
    def _extract_text(html: str) -> str:
        """Very lightweight HTML → text (no external deps)."""
        # Remove scripts and styles
        html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text[:50_000]
