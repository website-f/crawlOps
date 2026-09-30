"""Free, no-login social watchlists via RSSHub.

TikTok / Threads / YouTube expose public *account* content through RSSHub with no
API key and no login (verified live: tiktok/user, threads/:user, youtube/user all
return items; twitter and instagram are 503 there, so they are NOT offered here).

This is a watchlist model like RSS/Telegram: you list public accounts to follow, we
pull everything they post, and the central boolean filter keeps what matches the topic.
Open keyword *search* on these platforms is login-walled — this covers accounts, not search.
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
_YT_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([\w-]{11})")


class RsshubWatch(Connector):
    """Base: fetch each configured public account's RSSHub feed."""
    platform = "base"
    route_tmpl = ""            # e.g. "/tiktok/user/@{a}" — {a} = handle without @
    tier = 2

    def __init__(self, accounts: list[str] | None = None):
        self.accounts = [a.strip() for a in (accounts or []) if a.strip()]

    def enabled(self) -> bool:
        return bool(self.accounts)

    def disabled_reason(self) -> str:
        return "Connect: add public account handles to follow (free, no login)"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._account(a) for a in self.accounts[:20])

    def _route(self, account: str) -> str:
        return self.route_tmpl.format(a=account.lstrip("@"))

    def _media(self, entry, link: str) -> list[dict]:
        media: list[dict] = []
        yt = _YT_ID.search(link or "")
        if self.platform == "youtube" and yt:
            vid = yt.group(1)
            media.append({"kind": "video", "youtube_id": vid,
                          "src_url": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                          "thumb_src": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"})
            return media
        summary = entry.get("summary", "") or (
            entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")
        img = _IMG.search(summary or "")
        if img:
            media.append({"kind": "image", "src_url": html.unescape(img.group(1))})
        for m in entry.get("media_content", []) or []:
            if m.get("url"):
                media.append({"kind": "video" if "video" in m.get("type", "") else "image",
                              "src_url": m["url"]})
        for th in entry.get("media_thumbnail", []) or []:
            if th.get("url"):
                media.append({"kind": "image", "src_url": th["url"]})
        return media[:4]

    async def _account(self, account: str) -> list[RawMention]:
        base = settings.rsshub_url.rstrip("/")
        text = await fetch_text(base + self._route(account), timeout=30, attempts=2)
        feed = feedparser.parse(text)
        handle = account.lstrip("@")
        out: list[RawMention] = []
        for e in feed.entries[:40]:
            link = e.get("link", "")
            title = html.unescape(e.get("title", ""))
            summary = e.get("summary", "") or (
                e.get("content", [{}])[0].get("value", "") if e.get("content") else "")
            body = _TAGS.sub(" ", html.unescape(summary)).strip()
            out.append(RawMention(
                platform=self.platform,
                native_id=e.get("id", link) or f"{self.platform}:{handle}:{title[:40]}",
                url=link, title=title[:300],
                text=(body or title)[:2000],
                author_name=handle, author_key=handle, author_handle=f"@{handle}",
                community=handle,
                posted_at=dtparse.parse(e["published"]) if e.get("published") else (
                    dtparse.parse(e["updated"]) if e.get("updated") else None),
                media=self._media(e, link)))
        return out


class TikTokWatch(RsshubWatch):
    key = "tiktok_watch"
    platform = "tiktok"
    route_tmpl = "/tiktok/user/@{a}"


class ThreadsWatch(RsshubWatch):
    key = "threads_watch"
    platform = "threads"
    route_tmpl = "/threads/{a}"


class YouTubeWatch(RsshubWatch):
    key = "youtube_watch"
    platform = "youtube"
    route_tmpl = "/youtube/user/@{a}"
