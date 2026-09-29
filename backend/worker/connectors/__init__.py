"""Connector registry — keyed by Source.connector."""
from .bluesky import Bluesky
from .gdelt import Gdelt
from .googlenews import GoogleNews
from .hackernews import HackerNews
from .mastodon import Mastodon
from .reddit import Reddit
from .research import (ArXiv, ClinicalTrials, GitHub, SecEdgar, StackExchange,
                       Wikipedia)
from .rss import Rss
from .telegram import Telegram
from .threads import Threads
from .youtube import YouTube

# stateless tier-1 connectors (no config needed)
REGISTRY = {c.key: c for c in (HackerNews, Reddit, Bluesky, Mastodon,
                               Gdelt, GoogleNews, Threads, YouTube,
                               ArXiv, SecEdgar, Wikipedia, GitHub,
                               StackExchange, ClinicalTrials)}


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
    if connector_key in ("appstore", "factcheck", "podcastindex", "places"):
        from .gated import (AppStoreReviews, GoogleFactCheck, PlacesReviews,
                            PodcastIndex)
        if connector_key == "appstore":
            return AppStoreReviews(app_ids=cfg.get("app_ids", []),
                                   country=(cfg.get("country") or "us"))
        if connector_key == "factcheck":
            return GoogleFactCheck(api_key=cfg.get("api_key", ""))
        if connector_key == "podcastindex":
            return PodcastIndex(api_key=cfg.get("api_key", ""), api_secret=cfg.get("api_secret", ""))
        if connector_key == "places":
            return PlacesReviews(api_key=cfg.get("api_key", ""), place_ids=cfg.get("place_ids", []))
    if connector_key == "threads":
        from .fallback import FallbackConnector
        return FallbackConnector("threads",
                                 [Threads(access_token=cfg.get("access_token", "")),
                                  _stealth("threads_stealth", db)])
    if connector_key == "youtube":
        return YouTube(api_key=cfg.get("api_key", ""))
    if connector_key in ("facebook_stealth", "instagram_stealth", "tiktok_stealth",
                         "x_stealth", "threads_stealth"):
        return _stealth(connector_key, db)
    cls = REGISTRY.get(connector_key)
    return cls() if cls else None
