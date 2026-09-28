from dateutil import parser as dtparse

from app.config import settings
from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import TERM_CAP, Connector, RawMention, collect, fetch_json


class YouTube(Connector):
    key = "youtube"
    platform = "youtube"

    def enabled(self) -> bool:
        return bool(settings.youtube_api_key)

    def disabled_reason(self) -> str:
        return "Set YOUTUBE_API_KEY (free Google Cloud key, 10k units/day)"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        terms = to_api_terms(cq, TERM_CAP["youtube"])
        return await collect(self._search(t) for t in terms)

    async def _search(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://www.googleapis.com/youtube/v3/search",
                                params={"part": "snippet", "q": term, "order": "date",
                                        "type": "video", "maxResults": 25,
                                        "key": settings.youtube_api_key})
        out = []
        for item in data.get("items", []):
            vid = item.get("id", {}).get("videoId")
            sn = item.get("snippet", {})
            if not vid:
                continue
            thumb = ((sn.get("thumbnails") or {}).get("high") or {}).get("url", "")
            out.append(RawMention(
                platform="youtube", native_id=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                title=(sn.get("title") or "")[:300],
                text=(sn.get("description") or sn.get("title") or "")[:1500],
                author_key=sn.get("channelId", ""), author_name=sn.get("channelTitle", ""),
                posted_at=dtparse.parse(sn["publishedAt"]) if sn.get("publishedAt") else None,
                media=[{"kind": "video", "src_url": thumb, "thumb_src": thumb,
                        "youtube_id": vid}] if thumb else [],
                community=sn.get("channelTitle", "")))
        return out
