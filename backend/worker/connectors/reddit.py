import html
import re
from urllib.parse import urlparse

import feedparser
from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import TERM_CAP, Connector, RawMention, fetch_text

# Reddit hard-403s its search.json to non-OAuth datacenter IPs, but search.rss stays
# reachable (429/soft under load, which the proxy layer retries). A descriptive,
# API-guideline UA avoids the generic-browser block. Less rich than JSON (no score/
# comments), but working reddit data beats a permanently blocked connector.
REDDIT_UA = "CrawlOps/1.0 (social-listening research bot; by /u/crawlops)"
_TAGS = re.compile(r"<[^>]+>")
_SUB = re.compile(r"/r/([^/]+)/")


class Reddit(Connector):
    """Public search RSS, no OAuth — low volume; add a proxy for reliable throughput."""
    key = "reddit"
    platform = "reddit"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        terms = to_api_terms(cq, TERM_CAP["reddit"])
        if not terms:
            return []
        q = " OR ".join(f'"{t}"' for t in terms)
        text = await fetch_text("https://www.reddit.com/search.rss",
                                params={"q": q, "sort": "new", "limit": 100},
                                headers={"User-Agent": REDDIT_UA}, purpose="tier1")
        feed = feedparser.parse(text)
        out = []
        for e in feed.entries[:100]:
            link = e.get("link", "")
            thing = (e.get("id", "") or "").split("/")[-1] or link  # t3_xxxx
            content = ""
            if e.get("content"):
                content = e["content"][0].get("value", "")
            content = content or e.get("summary", "")
            sub = _SUB.search(link)
            author = (e.get("author", "") or "").lstrip("/").removeprefix("u/")
            out.append(RawMention(
                platform="reddit", native_id=thing,
                url=link, title=html.unescape(e.get("title", ""))[:300],
                text=_TAGS.sub(" ", html.unescape(content))[:1500],
                author_key=author, author_name=author, author_handle=f"u/{author}",
                domain="reddit.com",
                community=f"r/{sub.group(1)}" if sub else "reddit",
                posted_at=dtparse.parse(e["published"]) if e.get("published") else (
                    dtparse.parse(e["updated"]) if e.get("updated") else None)))
        return out
