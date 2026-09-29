"""Tier-2 RSS / RSSHub connector — watchlist model (like Radar's RSS).

Feeds are configured on the Source (config.feeds = ["https://…/rss", ...] and/or
config.rsshub_routes = ["/twitter/user/x", ...]). Ignores topic terms at fetch
time; the central boolean filter decides what's kept. Keyless.
"""
import html
import re
from urllib.parse import urlparse

import feedparser
from dateutil import parser as dtparse

from app.config import settings
from app.services.boolean_query import CompiledQuery

from .base import Connector, RawMention, collect, fetch_text

_TAGS = re.compile(r"<[^>]+>")
_IMG = re.compile(r'<img[^>]+src="([^"]+)"', re.I)


class Rss(Connector):
    key = "rss"
    platform = "news"

    def __init__(self, feeds: list[str] | None = None, rsshub_routes: list[str] | None = None):
        self.feeds = feeds or []
        self.rsshub_routes = rsshub_routes or []

    def enabled(self) -> bool:
        return bool(self.feeds or self.rsshub_routes)

    def disabled_reason(self) -> str:
        return "Add feed URLs or RSSHub routes in the source config"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        urls = list(self.feeds)
        base = settings.rsshub_url.rstrip("/")
        urls += [f"{base}{r if r.startswith('/') else '/' + r}" for r in self.rsshub_routes]
        return await collect(self._feed(u) for u in urls[:25])

    async def _feed(self, url: str) -> list[RawMention]:
        parsed = feedparser.parse(await fetch_text(url))
        feed_title = getattr(parsed.feed, "title", "") if hasattr(parsed, "feed") else ""
        out = []
        for e in parsed.entries[:50]:
            link = e.get("link", "")
            summary_raw = e.get("summary", "") or (e.get("content", [{}])[0].get("value", "") if e.get("content") else "")
            media = []
            img = _IMG.search(summary_raw or "")
            if img:
                media.append({"kind": "image", "src_url": html.unescape(img.group(1))})
            for m in e.get("media_content", []) or []:
                if m.get("url"):
                    media.append({"kind": "video" if "video" in m.get("type", "") else "image",
                                  "src_url": m["url"]})
            out.append(RawMention(
                platform="news", native_id=e.get("id", link) or link,
                url=link, title=html.unescape(e.get("title", ""))[:300],
                text=_TAGS.sub(" ", html.unescape(summary_raw))[:1500],
                author_name=feed_title or urlparse(link).netloc,
                author_key=feed_title or urlparse(link).netloc,
                domain=urlparse(link).netloc,
                posted_at=dtparse.parse(e["published"]) if e.get("published") else (
                    dtparse.parse(e["updated"]) if e.get("updated") else None),
                media=media[:2]))
        return out
