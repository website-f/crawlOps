"""Connector registry — keyed by Source.connector."""
from .bluesky import Bluesky
from .gdelt import Gdelt
from .googlenews import GoogleNews
from .hackernews import HackerNews
from .mastodon import Mastodon
from .reddit import Reddit
from .rss import Rss
from .telegram import Telegram
from .threads import Threads
from .youtube import YouTube

# stateless tier-1 connectors
REGISTRY = {c.key: c for c in (HackerNews, Reddit, Bluesky, Mastodon,
                               Gdelt, GoogleNews, Threads, YouTube)}


def build(connector_key: str, db=None, source_config: dict | None = None):
    """Stealth + config-driven connectors need extra args; tier-1 are stateless."""
    cfg = source_config or {}
    if connector_key == "rss":
        return Rss(feeds=cfg.get("feeds", []), rsshub_routes=cfg.get("rsshub_routes", []))
    if connector_key == "telegram":
        return Telegram(channels=cfg.get("channels", []))
    if connector_key in ("facebook_stealth", "instagram_stealth", "tiktok_stealth"):
        from ..stealth.platforms import (FacebookStealth, InstagramStealth,
                                         TikTokStealth)
        stealth = {"facebook_stealth": FacebookStealth,
                   "instagram_stealth": InstagramStealth,
                   "tiktok_stealth": TikTokStealth}
        return stealth[connector_key](db)
    cls = REGISTRY.get(connector_key)
    return cls() if cls else None
