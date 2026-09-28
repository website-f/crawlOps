from urllib.parse import urlparse

from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery, to_boolean_string
from app.services.countries import fips_to_iso2

from .base import Connector, RawMention, fetch_json


class Gdelt(Connector):
    """GDELT Doc API — global news, free, boolean-capable. Enforces ~1 req/5s/IP,
    hence the patient retry ladder (Radar's lesson)."""
    key = "gdelt"
    platform = "news"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        query = to_boolean_string(cq)
        if len(query) < 3:
            return []
        data = await fetch_json("https://api.gdeltproject.org/api/v2/doc/doc",
                                params={"query": query, "mode": "artlist", "format": "json",
                                        "maxrecords": 75, "sort": "datedesc", "timespan": "3d"},
                                timeout=30, retries=(0, 7, 12, 25))
        out = []
        for a in (data.get("articles") or []) if isinstance(data, dict) else []:
            url = a.get("url", "")
            if not url:
                continue
            media = []
            if a.get("socialimage"):
                media.append({"kind": "image", "src_url": a["socialimage"]})
            out.append(RawMention(
                platform="news", native_id=url,
                url=url, title=(a.get("title") or "")[:300],
                text=(a.get("title") or "")[:1500],
                author_name=a.get("domain", ""), author_key=a.get("domain", ""),
                domain=a.get("domain") or urlparse(url).netloc,
                country=fips_to_iso2(a.get("sourcecountry", "")) or "",
                posted_at=dtparse.parse(a["seendate"]) if a.get("seendate") else None,
                lang=(a.get("language") or "")[:2].lower(),
                media=media))
        return out
