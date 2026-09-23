"""
apps/api/connectors/rss.py

RSSConnector — fetches and parses RSS/Atom feeds.
Capabilities: FETCH, INCREMENTAL_SYNC
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set

import httpx
import structlog

from .base import BaseSourceConnector, FetchResult, SearchResult
from .registry import register
from schemas.generated.enums import SourceCapability

logger = structlog.get_logger(__name__)

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
}


@register("rss")
class RSSConnector(BaseSourceConnector):
    platform = "rss"
    _cursor: Dict[str, str] = {}  # feed_url → last_item_guid

    def get_capabilities(self) -> Set[SourceCapability]:
        return {SourceCapability.FETCH, SourceCapability.INCREMENTAL_SYNC}

    async def fetch(self, url: str) -> FetchResult:
        """Fetch RSS feed and convert to readable text."""
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url)
                text = resp.text
                items = self._parse_items(text)
                rendered = "\n\n".join(
                    f"{i['title']}\n{i['description']}" for i in items[:20]
                )
                return FetchResult(
                    url=url,
                    status_code=resp.status_code,
                    raw_html=text,
                    rendered_text=rendered,
                    title=self._parse_channel_title(text),
                    content_hash=hashlib.sha256(text.encode()).hexdigest(),
                )
        except Exception as e:
            return FetchResult(url=url, status_code=0, raw_html="", rendered_text="", error=str(e))

    async def search(self, query: str, *, limit: int = 10, since: Optional[str] = None) -> List[SearchResult]:
        """Fetch feed URL and filter items by query."""
        result = await self.fetch(query)  # query = feed URL here
        if result.error:
            return []
        items = self._parse_items(result.raw_html)
        q = query.lower()
        matches = [
            SearchResult(
                url=i["link"],
                title=i["title"],
                snippet=i["description"][:200],
                published_at=i["pub_date"],
                platform="rss",
            )
            for i in items
            if q in (i["title"] + i["description"]).lower()
        ]
        return matches[:limit]

    # ── Parsing ──────────────────────────────────────────────────────────────

    def _parse_items(self, xml_text: str) -> list[dict]:
        items = []
        try:
            root = ET.fromstring(xml_text)
            # Try RSS 2.0
            for item in root.iter("item"):
                items.append({
                    "title": item.findtext("title") or "",
                    "link": item.findtext("link") or "",
                    "description": re.sub(r"<[^>]+>", "", item.findtext("description") or ""),
                    "pub_date": item.findtext("pubDate") or "",
                    "guid": item.findtext("guid") or item.findtext("link") or "",
                })
            # Try Atom
            for entry in root.findall("atom:entry", NS):
                link_el = entry.find("atom:link", NS)
                link = link_el.get("href", "") if link_el is not None else ""
                items.append({
                    "title": entry.findtext("atom:title", "", NS),
                    "link": link,
                    "description": entry.findtext("atom:summary", "", NS),
                    "pub_date": entry.findtext("atom:updated", "", NS),
                    "guid": entry.findtext("atom:id", link, NS),
                })
        except ET.ParseError as e:
            logger.warning("rss_parse_error", error=str(e))
        return items

    def _parse_channel_title(self, xml_text: str) -> str:
        try:
            root = ET.fromstring(xml_text)
            channel = root.find("channel")
            if channel is not None:
                return channel.findtext("title") or ""
            return root.findtext("atom:title", "", NS)
        except Exception:
            return ""
