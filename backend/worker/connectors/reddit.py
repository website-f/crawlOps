from datetime import datetime, timezone

from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import TERM_CAP, Connector, RawMention, fetch_json


class Reddit(Connector):
    """Public search JSON, no OAuth — low volume only; browser UA avoids most 403s."""
    key = "reddit"
    platform = "reddit"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        terms = to_api_terms(cq, TERM_CAP["reddit"])
        if not terms:
            return []
        q = " OR ".join(f'"{t}"' for t in terms)
        data = await fetch_json("https://www.reddit.com/search.json",
                                params={"q": q, "sort": "new", "t": "week",
                                        "limit": 100, "raw_json": 1},
                                retries=(0, 5))
        out = []
        for child in (data.get("data", {}) or {}).get("children", []):
            d = child.get("data", {})
            if not d.get("id"):
                continue
            media = []
            preview = (d.get("preview") or {}).get("images") or []
            if preview:
                src = (preview[0].get("source") or {}).get("url", "")
                if src:
                    media.append({"kind": "image", "src_url": src.replace("&amp;", "&")})
            if d.get("is_video") and (d.get("media") or {}).get("reddit_video"):
                media.append({"kind": "video",
                              "src_url": d["media"]["reddit_video"].get("fallback_url", "")})
            out.append(RawMention(
                platform="reddit", native_id=d["id"],
                url=f"https://www.reddit.com{d.get('permalink', '')}",
                title=(d.get("title") or "")[:300],
                text=(d.get("selftext") or d.get("title") or "")[:1500],
                author_key=d.get("author", ""), author_name=d.get("author", ""),
                author_handle=f"u/{d.get('author', '')}",
                posted_at=datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc),
                community=f"r/{d.get('subreddit', '')}",
                media=media,
                engagement={"likes": d.get("score") or 0, "comments": d.get("num_comments") or 0}))
        return out
