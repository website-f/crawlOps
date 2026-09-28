import html
import re
from datetime import datetime, timezone

from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import TERM_CAP, Connector, RawMention, collect, fetch_json

_TAGS = re.compile(r"<[^>]+>")


class HackerNews(Connector):
    key = "hackernews"
    platform = "hackernews"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        terms = to_api_terms(cq, TERM_CAP["hackernews"])
        return await collect(self._search(t) for t in terms)

    async def _search(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://hn.algolia.com/api/v1/search_by_date",
                                params={"query": term, "tags": "(story,comment)",
                                        "hitsPerPage": 50})
        out = []
        for h in data.get("hits", []):
            title = h.get("title") or h.get("story_title") or ""
            body = _TAGS.sub(" ", html.unescape(h.get("comment_text") or "")) or title
            if not body:
                continue
            out.append(RawMention(
                platform="hackernews", native_id=h["objectID"],
                url=f"https://news.ycombinator.com/item?id={h['objectID']}",
                title=title[:300], text=body[:1500],
                author_key=h.get("author", ""), author_name=h.get("author", ""),
                author_handle=h.get("author", ""),
                posted_at=datetime.fromtimestamp(h.get("created_at_i", 0), tz=timezone.utc),
                lang="en", community="Hacker News",
                engagement={"likes": h.get("points") or 0, "comments": h.get("num_comments") or 0}))
        return out
