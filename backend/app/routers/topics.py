from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (AlertEvent, AlertRule, BenchmarkEntity, Cluster, Post,
                      PostMetric, Topic)
from ..services import meili
from ..services.boolean_query import compile_query, to_boolean_string
from ..services.gateway import GatewayUnavailable, gateway
from ..services.media_cache import _media_keys, delete_media_objects

router = APIRouter(prefix="/api/topics", tags=["topics"])


class TopicIn(BaseModel):
    name: str
    query: str = ""
    criteria: str = ""
    threshold: int = 55
    langs: list[str] = []
    platforms: list[str] = []
    schedule_minutes: int = 30
    active: bool = True


def _dump(t: Topic) -> dict:
    return {"id": t.id, "name": t.name, "query": t.query, "criteria": t.criteria,
            "threshold": t.threshold, "langs": t.langs, "platforms": t.platforms,
            "schedule_minutes": t.schedule_minutes, "active": t.active,
            "run_once": t.run_once,
            "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None}


@router.get("")
def list_topics(db: Session = Depends(get_db)):
    return [_dump(t) for t in db.query(Topic).order_by(Topic.id).all()]


@router.post("")
def create_topic(body: TopicIn, db: Session = Depends(get_db)):
    t = Topic(**body.model_dump())
    db.add(t)
    db.commit()
    return _dump(t)


@router.put("/{topic_id}")
def update_topic(topic_id: int, body: TopicIn, db: Session = Depends(get_db)):
    t = db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    db.commit()
    return _dump(t)


@router.delete("/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    t = db.get(Topic, topic_id)
    if not t:
        return {"ok": True}
    # reclaim cached media (MinIO objects aren't FK'd, so nothing else would free them)
    media_lists = [row[0] for row in
                   db.execute(select(Post.media).where(Post.topic_id == topic_id)).all()]
    # children first — the FKs have no ON DELETE CASCADE, so a topic that has
    # crawled anything would otherwise fail with a ForeignKeyViolation
    post_ids = select(Post.id).where(Post.topic_id == topic_id)
    rule_ids = select(AlertRule.id).where(AlertRule.topic_id == topic_id)
    db.execute(delete(PostMetric).where(PostMetric.post_id.in_(post_ids)))
    db.execute(delete(Post).where(Post.topic_id == topic_id))
    db.execute(delete(AlertEvent).where(AlertEvent.rule_id.in_(rule_ids)))
    db.execute(delete(AlertRule).where(AlertRule.topic_id == topic_id))
    db.execute(delete(Cluster).where(Cluster.topic_id == topic_id))
    db.execute(delete(BenchmarkEntity).where(BenchmarkEntity.topic_id == topic_id))
    db.delete(t)
    db.commit()
    meili.delete_topic_posts(topic_id)
    delete_media_objects(_media_keys(media_lists))
    return {"ok": True}


@router.post("/{topic_id}/run-now")
def run_now(topic_id: int, db: Session = Depends(get_db)):
    """Queue exactly ONE crawl. Does not turn on auto-run — a paused topic runs once
    and goes quiet again. The worker picks it up on its next tick (<=30s)."""
    t = db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404)
    t.run_once = True
    db.commit()
    return {"ok": True, "note": "queued one run; worker picks it up within 30s"}


@router.post("/{topic_id}/toggle-active")
def toggle_active(topic_id: int, db: Session = Depends(get_db)):
    """Flip auto-run. active=False = paused: the topic only crawls when you click
    Run now, so it stops filling storage on its own."""
    t = db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404)
    t.active = not t.active
    db.commit()
    return {"id": t.id, "active": t.active}


class BuildQueryIn(BaseModel):
    brief: str
    langs: list[str] = []


@router.post("/build-query")
async def build_query(body: BuildQueryIn):
    """AI boolean query builder (Radar-style, single-shot)."""
    prompt = (
        "You design media-monitoring boolean queries from a plain-language request.\n"
        'Return ONLY JSON: {"query": "<boolean>", "criteria": "<one-paragraph relevance criteria '
        'for an LLM judge>", "note": "<why>"}\n'
        "Boolean syntax: (term OR \"multi word\") AND (other OR words) NOT (noise OR terms). "
        "First group = the subject and its aliases/tickers/other-language names. "
        "Add NOT terms only for genuinely ambiguous names. Terms are words people actually write "
        f"— no hashtags unless the hashtag is the common form. Languages: {body.langs or ['any']}.\n\n"
        f"Request: {body.brief}"
    )
    try:
        data = await gateway.chat_json("judge", [{"role": "user", "content": prompt}], max_tokens=600)
    except GatewayUnavailable as e:
        raise HTTPException(503, f"No AI provider available: {e}") from e
    query = data.get("query", "")
    return {"query": query, "criteria": data.get("criteria", ""),
            "note": data.get("note", ""),
            "normalized": to_boolean_string(compile_query(query)),
            "updated_at": datetime.now(timezone.utc).isoformat()}
