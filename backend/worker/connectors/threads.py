from dateutil import parser as dtparse

from app.config import settings
from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import TERM_CAP, Connector, RawMention, collect, fetch_json

FIELDS = ("id,text,media_type,media_url,permalink,timestamp,username,"
          "has_replies,is_quote_post,is_reply")


class Threads(Connector):
    """Official Meta keyword search — ~2,200 queries/user/day. Needs an access token
    with threads_keyword_search scope."""
    key = "threads"
    platform = "threads"

    def enabled(self) -> bool:
        return bool(settings.threads_access_token)

    def disabled_reason(self) -> str:
        return "Set THREADS_ACCESS_TOKEN (Meta app with threads_keyword_search scope)"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        terms = to_api_terms(cq, TERM_CAP["threads"])
        return await collect(self._search(t) for t in terms)

    async def _search(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://graph.threads.net/v1.0/keyword_search",
                                params={"q": term, "search_type": "RECENT", "fields": FIELDS,
                                        "access_token": settings.threads_access_token})
        out = []
        for p in data.get("data", []):
            media = []
            mtype = p.get("media_type", "")
            if p.get("media_url"):
                kind = "video" if mtype in ("VIDEO", "REELS") else "image"
                media.append({"kind": kind, "src_url": p["media_url"]})
            username = p.get("username", "")
            out.append(RawMention(
                platform="threads", native_id=p["id"],
                url=p.get("permalink", ""),
                text=(p.get("text") or "")[:1500],
                author_key=username, author_name=username, author_handle=f"@{username}",
                posted_at=dtparse.parse(p["timestamp"]) if p.get("timestamp") else None,
                media=media,
                engagement={}))  # insights need per-post calls; deferred to metrics refresher
        return out
