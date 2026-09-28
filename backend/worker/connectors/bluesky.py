from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import TERM_CAP, Connector, RawMention, collect, fetch_json


class Bluesky(Connector):
    """Public AppView search — completely keyless."""
    key = "bluesky"
    platform = "bluesky"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        terms = to_api_terms(cq, TERM_CAP["bluesky"])
        return await collect(self._search(t) for t in terms)

    async def _search(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
                                params={"q": term, "limit": 50, "sort": "latest"})
        out = []
        for p in data.get("posts", []):
            author = p.get("author", {})
            record = p.get("record", {})
            uri = p.get("uri", "")
            rkey = uri.split("/")[-1] if uri else ""
            handle = author.get("handle", "")
            media = []
            embed = p.get("embed", {}) or {}
            for img in embed.get("images", []) or []:
                media.append({"kind": "image", "src_url": img.get("fullsize", ""),
                              "alt": img.get("alt", "")})
            if embed.get("$type", "").startswith("app.bsky.embed.video"):
                thumb = embed.get("thumbnail", "")
                if thumb:
                    media.append({"kind": "video", "src_url": embed.get("playlist", thumb),
                                  "thumb_src": thumb})
            out.append(RawMention(
                platform="bluesky", native_id=uri or rkey,
                url=f"https://bsky.app/profile/{handle}/post/{rkey}",
                text=(record.get("text") or "")[:1500],
                author_key=author.get("did", handle), author_name=author.get("displayName", handle),
                author_handle=f"@{handle}", author_avatar=author.get("avatar", ""),
                posted_at=dtparse.parse(record["createdAt"]) if record.get("createdAt") else None,
                lang=(record.get("langs") or [""])[0],
                media=media,
                engagement={"likes": p.get("likeCount", 0), "comments": p.get("replyCount", 0),
                            "shares": p.get("repostCount", 0)}))
        return out
