import html
import re

from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import TERM_CAP, Connector, RawMention, collect, fetch_json

_TAGS = re.compile(r"<[^>]+>")
INSTANCES = ["https://mastodon.social"]


class Mastodon(Connector):
    """Public hashtag timelines (keyless). Multi-word terms become CamelCase-less
    joined tags, which is how tags are actually written on the fediverse."""
    key = "mastodon"
    platform = "mastodon"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        tags = []
        for t in to_api_terms(cq, TERM_CAP["mastodon"]):
            tag = re.sub(r"[^a-z0-9]", "", t.lower())
            if 2 < len(tag) <= 40:
                tags.append(tag)
        coros = [self._tag(base, tag) for base in INSTANCES for tag in tags]
        return await collect(coros)

    async def _tag(self, base: str, tag: str) -> list[RawMention]:
        data = await fetch_json(f"{base}/api/v1/timelines/tag/{tag}", params={"limit": 40})
        out = []
        for s in data if isinstance(data, list) else []:
            acct = s.get("account", {})
            media = []
            for m in s.get("media_attachments", []):
                kind = "video" if m.get("type") in ("video", "gifv") else "image"
                media.append({"kind": kind, "src_url": m.get("url", ""),
                              "thumb_src": m.get("preview_url", "")})
            out.append(RawMention(
                platform="mastodon", native_id=s.get("uri", s.get("id", "")),
                url=s.get("url", ""),
                text=_TAGS.sub(" ", html.unescape(s.get("content") or ""))[:1500],
                author_key=acct.get("acct", ""), author_name=acct.get("display_name", ""),
                author_handle=f"@{acct.get('acct', '')}", author_avatar=acct.get("avatar", ""),
                author_followers=acct.get("followers_count"),
                posted_at=dtparse.parse(s["created_at"]) if s.get("created_at") else None,
                lang=s.get("language") or "",
                media=media,
                engagement={"likes": s.get("favourites_count", 0),
                            "comments": s.get("replies_count", 0),
                            "shares": s.get("reblogs_count", 0)}))
        return out
