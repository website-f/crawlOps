from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Topic
from ..services.boolean_query import compile_query, to_boolean_string
from ..services.gateway import GatewayUnavailable, gateway

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
    if t:
        db.delete(t)
        db.commit()
    return {"ok": True}


@router.post("/{topic_id}/run-now")
def run_now(topic_id: int, db: Session = Depends(get_db)):
    """Zero out last_run_at so the worker picks the topic up on its next tick (<=30s)."""
    t = db.get(Topic, topic_id)
    if not t:
        raise HTTPException(404)
    t.last_run_at = None
    t.active = True
    db.commit()
    return {"ok": True, "note": "queued; worker picks it up within 30s"}


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
