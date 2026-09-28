"""Nominatim geocoding with a forever-cache (docs/ALGORITHMS.md §9). Max 1 req/s.

Returns lat/lon plus country (ISO-2), country name, and region (state/admin1) so
the map can aggregate by country and state, Radar-style.
"""
import asyncio
import logging
import time

import httpx
from sqlalchemy.orm import Session

from ..models import GeoCache

log = logging.getLogger("geo")
_last_call = 0.0
_lock = asyncio.Lock()


async def geocode(db: Session, place: str) -> dict | None:
    """Returns {lat, lon, country, country_name, region, confidence} or None."""
    place = (place or "").strip()[:250]
    if not place:
        return None
    key = place.lower()
    cached = db.get(GeoCache, key)
    if cached is not None:
        if cached.lat is None:
            return None
        return {"lat": cached.lat, "lon": cached.lon, "country": cached.country,
                "country_name": cached.country_name, "region": cached.region,
                "confidence": cached.confidence}

    global _last_call
    async with _lock:  # Nominatim policy: 1 req/s
        wait = 1.1 - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get("https://nominatim.openstreetmap.org/search",
                                     params={"q": place, "format": "json", "limit": 1,
                                             "addressdetails": 1},
                                     headers={"User-Agent": "CrawlOps/1.0 (self-hosted media monitor)"})
            hits = r.json() if r.status_code == 200 else []
        except Exception:  # noqa: BLE001
            return None  # transient failure — don't poison the cache

    if hits:
        h = hits[0]
        addr = h.get("address", {}) or {}
        lat, lon = float(h["lat"]), float(h["lon"])
        conf = float(h.get("importance", 0.5) or 0.5)
        cc = (addr.get("country_code") or "").upper()[:2] or None
        result = {"lat": lat, "lon": lon, "country": cc,
                  "country_name": addr.get("country"),
                  "region": addr.get("state") or addr.get("region") or addr.get("province"),
                  "confidence": conf}
        db.merge(GeoCache(place=key, lat=lat, lon=lon, country=cc,
                          country_name=result["country_name"], region=result["region"],
                          confidence=conf))
        db.commit()
        return result
    db.merge(GeoCache(place=key, lat=None, lon=None, confidence=0.0))
    db.commit()
    return None
