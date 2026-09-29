import asyncio
import html
import re
from urllib.parse import urlparse

import feedparser
from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery, to_boolean_string

from .base import Connector, RawMention, fetch_text

_TAGS = re.compile(r"<[^>]+>")

EDITIONS = [  # (hl, gl, ceid) — Malaysia first for this deployment, then EN/US
    ("en-MY", "MY", "MY:en"),
    ("ms-MY", "MY", "MY:ms"),
    ("en-US", "US", "US:en"),
]


class GoogleNews(Connector):
    """RSS search per locale edition. `when:7d` forces recency over relevance —
    without it Google floods the feed with stale-but-popular articles."""
    key = "googlenews"
    platform = "news"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        query = to_boolean_string(cq)
        if not query:
            return []
        results = await asyncio.gather(
            *[self._edition(query, hl, gl, ceid) for hl, gl, ceid in EDITIONS],
            return_exceptions=True)
        out, seen = [], set()
        for r in results:
            if isinstance(r, Exception):
                continue
            for m in r:
                if m.native_id not in seen:
                    seen.add(m.native_id)
                    out.append(m)
        return out

    async def _edition(self, query: str, hl: str, gl: str, ceid: str) -> list[RawMention]:
        text = await fetch_text("https://news.google.com/rss/search",
                                params={"q": f"{query} when:7d", "hl": hl, "gl": gl, "ceid": ceid})
        feed = feedparser.parse(text)
        out = []
        for e in feed.entries[:50]:
            link = e.get("link", "")
            source = e.get("source", {}).get("title", "") if hasattr(e, "source") else ""
            out.append(RawMention(
                platform="news", native_id=e.get("id", link),
                url=link, title=html.unescape(e.get("title", ""))[:300],
                text=_TAGS.sub(" ", html.unescape(e.get("summary", "")))[:1500],
                author_name=source, author_key=source,
                domain=urlparse(link).netloc,
                posted_at=dtparse.parse(e["published"]) if e.get("published") else None,
                lang=hl.split("-")[0]))
        return out
