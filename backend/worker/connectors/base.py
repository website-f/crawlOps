"""Connector contract — thin fetchers, fat central pipeline (Radar's best idea).

A connector only turns (topic query) into normalized RawMention objects.
Boolean AND/NOT filtering, dedup, enrichment, throttling all happen centrally.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from app.services.boolean_query import CompiledQuery

log = logging.getLogger("connectors")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Radar-style rate strategy as data: how many anchor terms a connector may expand
# into separate API calls per cycle.
TERM_CAP = {"hackernews": 4, "reddit": 5, "bluesky": 4, "mastodon": 3,
            "gdelt": 1, "googlenews": 1, "threads": 3, "youtube": 2}
ROUND_DELAY_S = 0.4


@dataclass
class RawMention:
    platform: str
    native_id: str
    text: str = ""
    title: str = ""
    url: str = ""
    author_key: str = ""
    author_name: str = ""
    author_handle: str = ""
    author_avatar: str = ""
    author_followers: int | None = None
    author_verified: bool = False
    posted_at: datetime | None = None
    lang: str = ""
    domain: str = ""
    community: str = ""
    media: list = field(default_factory=list)      # [{kind: image|video, src_url, ...}]
    engagement: dict = field(default_factory=dict)  # {likes, comments, shares, views, reactions{}}


class Connector:
    """Subclass and set key; implement fetch(). enabled() gates on config/keys."""
    key = "base"
    platform = "base"
    tier = 1

    def enabled(self) -> bool:
        return True

    def disabled_reason(self) -> str:
        return ""

    async def fetch(self, cq: CompiledQuery) -> list[RawMention]:
        raise NotImplementedError


async def fetch_json(url: str, params: dict | None = None, headers: dict | None = None,
                     timeout: float = 20, retries: tuple = (0,)) -> dict | list:
    last: Exception | None = None
    for delay in retries:
        if delay:
            await asyncio.sleep(delay)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                r = await client.get(url, params=params,
                                     headers={"User-Agent": UA, **(headers or {})})
            if r.status_code == 429:
                last = RuntimeError(f"429 from {url}")
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
    raise last or RuntimeError("fetch failed")


async def collect(coros) -> list[RawMention]:
    """Promise.allSettled + flatten: one term failing never kills the cycle."""
    results = await asyncio.gather(*coros, return_exceptions=True)
    out: list[RawMention] = []
    for r in results:
        if isinstance(r, Exception):
            log.warning("connector sub-fetch failed: %s", r)
        else:
            out.extend(r)
    return out
