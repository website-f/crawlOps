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


def _stealth(key: str, db):
    from ..stealth.platforms import (FacebookStealth, InstagramStealth,
                                     ThreadsStealth, TikTokStealth, XStealth)
    cls = {"facebook_stealth": FacebookStealth, "instagram_stealth": InstagramStealth,
           "tiktok_stealth": TikTokStealth, "x_stealth": XStealth,
           "threads_stealth": ThreadsStealth}[key]
    return cls(db)


def build(connector_key: str, db=None, source_config: dict | None = None):
    """Config-driven + stealth connectors need extra args; tier-1 are stateless.
    `threads` returns a fallback chain: official API first, camofox crawler second."""
    cfg = source_config or {}
    if connector_key == "rss":
        return Rss(feeds=cfg.get("feeds", []), rsshub_routes=cfg.get("rsshub_routes", []))
    if connector_key == "telegram":
        return Telegram(channels=cfg.get("channels", []))
    if connector_key == "threads":
        from .fallback import FallbackConnector
        return FallbackConnector("threads", [Threads(), _stealth("threads_stealth", db)])
    if connector_key in ("facebook_stealth", "instagram_stealth", "tiktok_stealth",
                         "x_stealth", "threads_stealth"):
        return _stealth(connector_key, db)
    cls = REGISTRY.get(connector_key)
    return cls() if cls else None
