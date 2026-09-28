"""Meilisearch index for the feed — instant faceted filtering."""
import logging

import meilisearch

from ..config import settings

log = logging.getLogger("meili")
INDEX = "posts"

FILTERABLE = ["platform", "topic_id", "sentiment", "emotion", "lang", "domain",
              "cluster_id", "dup_group", "author_key", "bot_suspect", "is_hidden",
              "has_media", "posted_ts", "relevance", "author_verified",
              "country", "region", "topics", "entities"]
SORTABLE = ["posted_ts", "engagement_total", "relevance", "reach", "risk", "virality"]
SEARCHABLE = ["title", "text", "author_name", "author_handle", "domain", "topics", "entities"]


def client() -> meilisearch.Client:
    return meilisearch.Client(settings.meili_url, settings.meili_master_key)


def ensure_index() -> None:
    c = client()
    try:
        c.create_index(INDEX, {"primaryKey": "id"})
    except Exception:  # noqa: BLE001 - already exists
        pass
    idx = c.index(INDEX)
    idx.update_filterable_attributes(FILTERABLE)
    idx.update_sortable_attributes(SORTABLE)
    idx.update_searchable_attributes(SEARCHABLE)


def index_posts(docs: list[dict]) -> None:
    if docs:
        client().index(INDEX).add_documents(docs)


def doc_from_post(p) -> dict:
    e = p.engagement or {}
    return {
        "id": p.id, "platform": p.platform, "topic_id": p.topic_id,
        "title": p.title, "text": (p.text or "")[:2000],
        "author_key": p.author_key, "author_name": p.author_name,
        "author_handle": p.author_handle, "author_avatar": p.author_avatar,
        "author_verified": p.author_verified, "domain": p.domain,
        "url": p.url, "lang": p.lang, "sentiment": p.sentiment,
        "sentiment_score": p.sentiment_score, "relevance": p.relevance,
        "emotion": p.emotion, "entities": p.entities or [],
        "virality": p.virality, "risk": p.risk,
        "country": p.country, "region": p.region, "country_name": p.country_name,
        "topics": p.topics or [], "media": p.media or [],
        "has_media": bool(p.media), "engagement": e,
        "engagement_total": sum(v for v in
                                [e.get("likes", 0), e.get("comments", 0), e.get("shares", 0)]
                                if isinstance(v, (int, float))),
        "reach": p.reach, "emv": p.emv,
        "posted_ts": int(p.posted_at.timestamp()) if p.posted_at else 0,
        "cluster_id": p.cluster_id, "dup_group": p.dup_group,
        "bot_suspect": p.bot_suspect, "is_hidden": p.is_hidden,
        "lat": p.lat, "lon": p.lon,
    }


def search(q: str, filters: list[str], sort: str | None, page: int, per_page: int) -> dict:
    params = {
        "filter": filters or None,
        "sort": [sort] if sort else ["posted_ts:desc"],
        "page": page, "hitsPerPage": per_page,
    }
    return client().index(INDEX).search(q or "", {k: v for k, v in params.items() if v})


def delete_post(post_id: int) -> None:
    try:
        client().index(INDEX).delete_document(post_id)
    except Exception:  # noqa: BLE001
        log.warning("meili delete failed for %s", post_id)
