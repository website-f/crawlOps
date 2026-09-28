"""AI-driven analytics ported from radar-intelligence: discourse clusters,
causal chains, coordinated-account narratives, daily exec brief. All route through
our gateway (rotating providers); each degrades gracefully with no AI provider.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from ..models import AlertEvent, AlertRule, Post
from .gateway import GatewayUnavailable, gateway

log = logging.getLogger("ai_insights")

DISCOURSE_FAMILIES = ["price/cost", "quality/product", "scandal/controversy", "irony/meme",
                      "politics/regulation", "customer care/support", "ethics/values",
                      "innovation/technology", "business/market", "safety/risks"]


def _recent_posts(db: Session, topic_id, days, limit=60):
    f = [Post.is_hidden.is_(False),
         Post.posted_at >= datetime.now(timezone.utc) - timedelta(days=days)]
    if topic_id:
        f.append(Post.topic_id == topic_id)
    return db.query(Post).filter(and_(*f)).order_by(Post.posted_at.desc()).limit(limit).all()


async def discourse_clusters(db: Session, topic_id, days=14) -> dict:
    posts = _recent_posts(db, topic_id, days, 60)
    if not posts:
        return {"clusters": [], "note": "no posts in window"}
    sample = "\n".join(f"- {(p.title or p.text)[:140]}" for p in posts)
    prompt = ("Classify this conversation into families of discourse. Families: "
              f"{', '.join(DISCOURSE_FAMILIES)}.\n"
              'Reply ONLY JSON: {"clusters":[{"family":"...","share":0-100,'
              '"sentiment":"pos|neu|neg","example":"..."}]} — shares sum to ~100.\n\n'
              f"Conversation:\n{sample}")
    try:
        data = await gateway.chat_json("enrich", [{"role": "user", "content": prompt}], max_tokens=900)
        return {"clusters": data.get("clusters", [])}
    except GatewayUnavailable:
        return {"clusters": [], "note": "no AI provider configured — enable one in AI Engine"}


async def causal_chains(db: Session, topic_id, days=14) -> dict:
    now = datetime.now(timezone.utc)
    events = (db.query(AlertEvent).join(AlertRule, AlertRule.id == AlertEvent.rule_id)
              .filter(AlertRule.topic_id == topic_id if topic_id else True,
                      AlertEvent.fired_at >= now - timedelta(days=days))
              .order_by(AlertEvent.fired_at.desc()).limit(15).all()) if topic_id else []
    topics = (db.query(func.jsonb_array_elements_text(Post.topics).label("t"), func.count())
              .filter(Post.is_hidden.is_(False), Post.posted_at >= now - timedelta(days=days),
                      *( [Post.topic_id == topic_id] if topic_id else []))
              .group_by("t").order_by(func.count().desc()).limit(12).all())
    payload = {
        "alerts": [e.payload.get("title", "") for e in events],
        "top_topics": [t for t, _ in topics],
    }
    prompt = ("Reconstruct cause->effect chains for this monitored subject: which events/news likely "
              "drove volume spikes, sentiment shifts, or new narratives.\n"
              'Reply ONLY JSON: {"chains":[{"cause":"...","date":"","effects":["..."]}]} (3-5 chains).\n\n'
              f"Signals: {payload}")
    try:
        data = await gateway.chat_json("agent", [{"role": "user", "content": prompt}], max_tokens=900)
        return {"chains": data.get("chains", [])}
    except GatewayUnavailable:
        return {"chains": [], "note": "no AI provider configured"}


def narratives(db: Session, topic_id, days=14) -> dict:
    """Coordinated-account detection (deterministic): a dup_group pushed by many
    DISTINCT authors within the window = a coordinated narrative."""
    now = datetime.now(timezone.utc)
    f = [Post.is_hidden.is_(False), Post.posted_at >= now - timedelta(days=days),
         Post.dup_group.isnot(None)]
    if topic_id:
        f.append(Post.topic_id == topic_id)
    rows = (db.query(Post.dup_group,
                     func.count(func.distinct(Post.author_key)).label("authors"),
                     func.count().label("posts"),
                     func.min(Post.text).label("sample"),
                     func.array_agg(func.distinct(Post.platform)).label("platforms"))
            .filter(and_(*f)).group_by(Post.dup_group)
            .having(func.count(func.distinct(Post.author_key)) >= 3)
            .order_by(func.count().desc()).limit(20).all())
    out = []
    for r in rows:
        out.append({"dup_group": r.dup_group, "accounts": r.authors, "posts": r.posts,
                    "platforms": [p for p in (r.platforms or []) if p],
                    "sample": (r.sample or "")[:200],
                    "coordinated": r.authors >= 5})
    return {"narratives": out}


async def daily_brief(db: Session, topic_id, days=1) -> dict:
    from .insights import brand_health
    now = datetime.now(timezone.utc)
    f = [Post.is_hidden.is_(False), Post.posted_at >= now - timedelta(days=days)]
    if topic_id:
        f.append(Post.topic_id == topic_id)
    total = db.query(func.count()).filter(and_(*f)).scalar() or 0
    sent = dict(db.query(Post.sentiment, func.count()).filter(and_(*f)).group_by(Post.sentiment).all())
    top_topics = [t for t, _ in
                  (db.query(func.jsonb_array_elements_text(Post.topics).label("t"), func.count())
                   .filter(and_(*f)).group_by("t").order_by(func.count().desc()).limit(8).all())]
    top_posts = (db.query(Post).filter(and_(*f))
                 .order_by(func.coalesce(Post.engagement["likes"].as_float(), 0).desc()).limit(6).all())
    health = brand_health(db, topic_id, max(days, 7))
    facts = {
        "total": total, "positive": sent.get("pos", 0), "neutral": sent.get("neu", 0),
        "negative": sent.get("neg", 0), "health_score": health["score"], "grade": health["grade"],
        "top_topics": top_topics,
        "notable": [f"[{p.platform}] {(p.title or p.text)[:120]}" for p in top_posts],
    }
    prompt = ("Write a concise daily media-monitoring executive brief in markdown (max 200 words): "
              "headline takeaway, sentiment read, what's driving volume, and 1-2 recommended actions. "
              f"Base it ONLY on these facts:\n{facts}")
    try:
        content, _ = await gateway.chat("enrich", [{"role": "user", "content": prompt}], max_tokens=500)
        return {"brief": content, "facts": facts}
    except GatewayUnavailable:
        return {"brief": "", "facts": facts, "note": "no AI provider configured — showing raw facts only"}
