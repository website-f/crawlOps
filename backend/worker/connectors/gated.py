"""Specialized sources that need a key or watchlist config (entered per-source in
the Sources UI, not env). Keyless ones (App Store reviews via iTunes RSS) work
immediately; key-gated ones (Google Fact Check, Places reviews, Podcast Index)
stay dormant with a clear reason until configured. Ported from radar-intelligence.
"""
import html
import re
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dtparse

from app.services.boolean_query import CompiledQuery, to_api_terms

from .base import UA, Connector, RawMention, collect, fetch_json

_TAGS = re.compile(r"<[^>]+>")


class AppStoreReviews(Connector):
    """Keyless — iTunes customer-reviews RSS per app id. Config: {app_ids:[...], country}."""
    key = "appstore"
    platform = "appstore"
    tier = 2

    def __init__(self, app_ids: list[str] | None = None, country: str = "us"):
        self.app_ids = app_ids or []
        self.country = country

    def enabled(self) -> bool:
        return bool(self.app_ids)

    def disabled_reason(self) -> str:
        return "Connect: add App Store app IDs"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._app(a) for a in self.app_ids[:10])

    async def _app(self, app_id: str) -> list[RawMention]:
        import httpx
        url = f"https://itunes.apple.com/{self.country}/rss/customerreviews/id={app_id}/sortby=mostrecent/json"
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url, headers={"User-Agent": UA})
        entries = (r.json().get("feed", {}).get("entry", []) if r.status_code == 200 else [])
        out = []
        for e in entries:
            if "im:rating" not in e:  # first entry is app metadata
                continue
            rating = int(e.get("im:rating", {}).get("label", 3))
            out.append(RawMention(
                platform="appstore", native_id=e.get("id", {}).get("label", ""),
                url=e.get("author", {}).get("uri", {}).get("label", ""),
                title=e.get("title", {}).get("label", "")[:300],
                text=e.get("content", {}).get("label", "")[:1500],
                author_name=e.get("author", {}).get("name", {}).get("label", ""),
                author_key=str(app_id), community=f"App Store {app_id}",
                posted_at=datetime.now(timezone.utc),
                engagement={"likes": rating}))  # rating carried as a signal
        return out


class GoogleFactCheck(Connector):
    """Key-gated — Google Fact Check Tools API (free key). Config: {api_key}."""
    key = "factcheck"
    platform = "factcheck"
    tier = 2

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def enabled(self) -> bool:
        return bool(self.api_key)

    def disabled_reason(self) -> str:
        return "Connect: add a Google Fact Check Tools API key"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._q(t) for t in to_api_terms(cq, 3))

    async def _q(self, term: str) -> list[RawMention]:
        data = await fetch_json("https://factchecktools.googleapis.com/v1alpha1/claims:search",
                                params={"query": term, "key": self.api_key, "pageSize": 15})
        out = []
        for c in (data.get("claims", []) if isinstance(data, dict) else []):
            review = (c.get("claimReview") or [{}])[0]
            out.append(RawMention(
                platform="factcheck", native_id=review.get("url", c.get("text", ""))[:290],
                url=review.get("url", ""),
                title=(review.get("title") or c.get("text") or "")[:300],
                text=f"Claim: {c.get('text','')} — Rating: {review.get('textualRating','')}"[:1500],
                author_name=review.get("publisher", {}).get("name", ""),
                author_key=review.get("publisher", {}).get("site", ""),
                community="Fact Check",
                posted_at=dtparse.parse(review["reviewDate"]) if review.get("reviewDate") else None))
        return out


class PodcastIndex(Connector):
    """Key-gated — Podcast Index API. Config: {api_key, api_secret}."""
    key = "podcastindex"
    platform = "podcast"
    tier = 2

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret

    def enabled(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def disabled_reason(self) -> str:
        return "Connect: add a Podcast Index key + secret"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        import hashlib
        import time

        import httpx
        terms = to_api_terms(cq, 2)
        out = []
        for term in terms:
            ts = str(int(time.time()))
            auth = hashlib.sha1((self.api_key + self.api_secret + ts).encode()).hexdigest()
            headers = {"User-Agent": UA, "X-Auth-Key": self.api_key,
                       "X-Auth-Date": ts, "Authorization": auth}
            try:
                async with httpx.AsyncClient(timeout=20) as c:
                    r = await c.get("https://api.podcastindex.org/api/1.0/search/byterm",
                                    params={"q": term, "max": 15}, headers=headers)
                feeds = r.json().get("feeds", []) if r.status_code == 200 else []
            except Exception:  # noqa: BLE001
                continue
            for f in feeds:
                out.append(RawMention(
                    platform="podcast", native_id=str(f.get("id")),
                    url=f.get("link", ""), title=(f.get("title") or "")[:300],
                    text=(f.get("description") or "")[:1500],
                    author_name=f.get("author", ""), author_key=str(f.get("id")),
                    community="Podcast Index", posted_at=datetime.now(timezone.utc)))
        return out


class PlacesReviews(Connector):
    """Key-gated — Google Places reviews. Config: {api_key, place_ids:[...]}. Paid API."""
    key = "places"
    platform = "places"
    tier = 2

    def __init__(self, api_key: str = "", place_ids: list[str] | None = None):
        self.api_key = api_key
        self.place_ids = place_ids or []

    def enabled(self) -> bool:
        return bool(self.api_key and self.place_ids)

    def disabled_reason(self) -> str:
        return "Connect: add a Google Places API key + place IDs (paid API)"

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        return await collect(self._place(p) for p in self.place_ids[:10])

    async def _place(self, place_id: str) -> list[RawMention]:
        data = await fetch_json("https://maps.googleapis.com/maps/api/place/details/json",
                                params={"place_id": place_id, "fields": "name,reviews",
                                        "key": self.api_key})
        result = data.get("result", {}) if isinstance(data, dict) else {}
        name = result.get("name", "")
        out = []
        for rv in result.get("reviews", []):
            out.append(RawMention(
                platform="places", native_id=f"{place_id}:{rv.get('time')}",
                url=rv.get("author_url", ""), title=f"{name} review"[:300],
                text=(rv.get("text") or "")[:1500],
                author_name=rv.get("author_name", ""), author_key=place_id,
                community=name, posted_at=datetime.fromtimestamp(rv.get("time", 0), tz=timezone.utc),
                engagement={"likes": rv.get("rating", 0)}))
        return out
