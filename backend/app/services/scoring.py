"""Deterministic scoring — engagement, reach, EMV (docs/ALGORITHMS.md §8).

Radar-style: conservative, recomputable, AI never touches these numbers.
Negative coverage earns zero EMV. CPM/base tables are editable in Settings later.
"""
NEWS_PLATFORMS = {"news", "googlenews", "gdelt", "rss"}

NEWS_BASE_IMPRESSIONS = 5000
SOCIAL_ENGAGEMENT_MULTIPLIER = 30
SOCIAL_MIN_IMPRESSIONS = 200

CPM = {  # RM per 1000 impressions
    "news": 24.0, "facebook": 12.0, "instagram": 14.0, "threads": 8.0, "x": 8.0,
    "reddit": 6.0, "youtube": 10.0, "bluesky": 5.0, "mastodon": 5.0,
    "hackernews": 6.0, "telegram": 6.0, "tiktok": 14.0,
}
SENTIMENT_FACTOR = {"pos": 1.0, "neu": 0.5, "neg": 0.0}

VIEW_RATE = {  # follower -> impression heuristics when followers known
    "facebook": 0.06, "instagram": 0.09, "threads": 0.05, "x": 0.12,
    "bluesky": 0.10, "mastodon": 0.10, "tiktok": 0.15,
}


def engagement_score(e: dict | None) -> float:
    if not e:
        return 0.0
    return (e.get("likes", 0) + 2 * e.get("comments", 0)
            + 3 * e.get("shares", 0) + e.get("views", 0) / 200)


def estimate_reach(platform: str, engagement: dict | None, followers: int | None) -> int:
    if followers and platform in VIEW_RATE:
        return int(followers * VIEW_RATE[platform])
    if platform in NEWS_PLATFORMS:
        return NEWS_BASE_IMPRESSIONS
    return max(SOCIAL_MIN_IMPRESSIONS, int(engagement_score(engagement) * SOCIAL_ENGAGEMENT_MULTIPLIER))


def estimate_emv(platform: str, reach: int, sentiment: str | None,
                 cpm_table: dict | None = None) -> float:
    key = "news" if platform in NEWS_PLATFORMS else platform
    table = cpm_table or CPM
    cpm = table.get(key, 6.0)
    factor = SENTIMENT_FACTOR.get(sentiment or "neu", 0.5)
    return round(reach / 1000 * cpm * factor, 2)
