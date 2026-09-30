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
    country: str = ""      # ISO-2, when the source declares it (e.g. GDELT)
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


# ---- rotating, rate-limited, retrying HTTP crawl layer ---------------------
# Every connector fetches through request()/fetch_json()/fetch_text() so it gets:
#   - proxy rotation from the health-scored pool (beats single-IP 429/403 blocks)
#   - per-domain minimum interval (polite, avoids self-inflicted rate limits)
#   - retry across proxies with backoff, reporting outcomes to the proxy scorer
import time as _time
from urllib.parse import urlparse

# polite minimum seconds between hits to the same host (Redis-coordinated across workers)
# A 429 pushes the whole domain's next-allowed time out by this much per attempt.
RATE_PENALTY_S = 15.0
DOMAIN_MIN_INTERVAL = {
    # GDELT publishes 1 req/5s but throttles harder in practice; 8s buys headroom
    # so a burst of concurrent topics doesn't spend its budget on 429 retries.
    "api.gdeltproject.org": 8.0, "export.arxiv.org": 3.0, "efts.sec.gov": 1.0,
    "en.wikipedia.org": 0.5, "api.stackexchange.com": 0.4, "api.github.com": 1.0,
    "hn.algolia.com": 0.3, "www.reddit.com": 2.0, "clinicaltrials.gov": 0.5,
    "news.google.com": 1.0,
}
_pool_cache: dict = {"at": 0.0, "pool": []}


def _proxy_pool() -> list[dict]:
    """Active proxies from Postgres, cached ~30s to avoid a query per request."""
    now = _time.time()
    if now - _pool_cache["at"] < 30:
        return _pool_cache["pool"]
    try:
        from app.db import SessionLocal
        from app.models import Proxy
        from app.services.credentials import decrypt_proxy
        with SessionLocal() as db:
            pool = [{"id": p.id, "url": decrypt_proxy(p.url), "tag": p.tag}
                    for p in db.query(Proxy).filter(Proxy.active.is_(True)).all()]
    except Exception:  # noqa: BLE001
        pool = []
    _pool_cache.update(at=now, pool=pool)
    return pool


_domain_locks: dict = {}


async def _respect_rate(domain: str) -> None:
    interval = DOMAIN_MIN_INTERVAL.get(domain, 0.15)
    # One lock per domain, held across the read-sleep-write. Without it the fetch
    # phase's concurrent connectors all read the same "last" timestamp, sleep the
    # same amount and then fire simultaneously — which is how GDELT (1 req/5s) was
    # getting rate-limited despite being configured at 5.0s.
    lock = _domain_locks.get(domain)
    if lock is None:
        lock = _domain_locks[domain] = asyncio.Lock()
    async with lock:
        try:
            from app.services.proxy_manager import proxy_manager
            r = proxy_manager.r
            key = f"ratelimit:{domain}"
            last = float(r.get(key) or 0)
            wait = interval - (_time.time() - last)
            if wait > 0:
                await asyncio.sleep(min(wait, interval))
            r.set(key, _time.time(), ex=3600)
        except Exception:  # noqa: BLE001
            pass  # rate limiting is best-effort; never block a fetch on Redis


def _penalize_rate(domain: str, seconds: float) -> None:
    """Push the domain's next-allowed time into the future after a 429, so every
    other coroutine waiting on this domain backs off too — not just this caller.
    A published limit is a floor, not a guarantee; this is what actually adapts."""
    try:
        from app.services.proxy_manager import proxy_manager
        proxy_manager.r.set(f"ratelimit:{domain}", _time.time() + seconds, ex=3600)
    except Exception:  # noqa: BLE001
        pass


async def request(url: str, params: dict | None = None, headers: dict | None = None,
                  timeout: float = 25, attempts: int = 3,
                  purpose: str = "tier2") -> httpx.Response:
    """GET with proxy rotation + per-domain rate limiting + retry/backoff.
    Reports each proxy's outcome to the health scorer. Falls back to direct."""
    from app.services.proxy_manager import proxy_manager
    domain = urlparse(url).netloc
    pool = _proxy_pool()
    last: Exception | None = None
    for attempt in range(attempts):
        await _respect_rate(domain)
        proxy = None
        try:
            proxy = proxy_manager.acquire(pool, purpose=purpose) if pool else None
        except Exception:  # noqa: BLE001
            proxy = None
        client_kw = {"timeout": timeout, "follow_redirects": True}
        if proxy:
            client_kw["proxy"] = proxy["url"]
        try:
            async with httpx.AsyncClient(**client_kw) as client:
                r = await client.get(url, params=params,
                                     headers={"User-Agent": UA, **(headers or {})})
            if r.status_code in (429, 403, 451, 503) or r.status_code >= 500:
                if proxy:
                    proxy_manager.report(proxy["id"], "soft_block")
                if r.status_code == 429:
                    # make every other caller on this domain wait, not just us
                    _penalize_rate(domain, RATE_PENALTY_S * (attempt + 1))
                last = RuntimeError(f"{r.status_code} from {domain}")
                await asyncio.sleep(min(8, 1.5 * (attempt + 1)))  # backoff
                continue
            if proxy:
                proxy_manager.report(proxy["id"], "ok")
            return r
        except Exception as e:  # noqa: BLE001
            if proxy:
                proxy_manager.report(proxy["id"], "net_error")
            last = e
            await asyncio.sleep(min(5, 1.0 * (attempt + 1)))
    raise last or RuntimeError(f"fetch failed: {url}")


async def fetch_json(url: str, params: dict | None = None, headers: dict | None = None,
                     timeout: float = 25, retries: tuple = (0,), purpose: str = "tier2"):
    # `retries` kept for signature compat; attempt count is derived from it + a floor of 3
    attempts = max(3, len(retries))
    last_body = ""
    for attempt in range(attempts):
        r = await request(url, params=params, headers=headers, timeout=timeout,
                          attempts=attempts, purpose=purpose)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            # A 200 whose body isn't JSON is how some APIs report throttling — GDELT
            # answers "Please limit requests to one every 5 seconds" with status 200,
            # which used to surface as a baffling "Expecting value: line 1 column 1".
            last_body = (r.text or "").strip()[:200]
            await asyncio.sleep(min(10, 3.0 * (attempt + 1)))
    raise RuntimeError(
        f"{urlparse(url).netloc} returned non-JSON ({last_body!r})")


async def fetch_text(url: str, params: dict | None = None, headers: dict | None = None,
                     timeout: float = 25, attempts: int = 3, purpose: str = "tier2") -> str:
    r = await request(url, params=params, headers=headers, timeout=timeout,
                      attempts=attempts, purpose=purpose)
    r.raise_for_status()
    return r.text


async def fetch_text_conditional(url: str, params: dict | None = None,
                                 headers: dict | None = None, cache_key: str | None = None,
                                 timeout: float = 25, purpose: str = "tier2") -> str | None:
    """Conditional GET for pollable resources (RSS/Atom). Sends If-None-Match /
    If-Modified-Since from the last fetch; returns None when the server answers 304
    (unchanged) so the caller can skip re-parsing. Saves bandwidth + block-risk on
    feeds polled every cycle. Validators are stored in Redis, keyed by cache_key|url."""
    ck = cache_key or url
    r = None
    cond: dict[str, str] = {}
    try:
        from app.services.proxy_manager import proxy_manager
        r = proxy_manager.r
        et = r.get(f"httpcache:etag:{ck}")
        lm = r.get(f"httpcache:lm:{ck}")
        if et:
            cond["If-None-Match"] = et
        if lm:
            cond["If-Modified-Since"] = lm
    except Exception:  # noqa: BLE001
        r = None
    resp = await request(url, params=params, headers={**(headers or {}), **cond},
                         timeout=timeout, purpose=purpose)
    if resp.status_code == 304:
        return None                                   # unchanged since last poll
    resp.raise_for_status()
    if r is not None and resp.status_code == 200:
        try:                                          # remember validators for next time
            if resp.headers.get("ETag"):
                r.set(f"httpcache:etag:{ck}", resp.headers["ETag"], ex=14 * 86400)
            if resp.headers.get("Last-Modified"):
                r.set(f"httpcache:lm:{ck}", resp.headers["Last-Modified"], ex=14 * 86400)
        except Exception:  # noqa: BLE001
            pass
    return resp.text


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
