"""Author intelligence — find an author across platforms and see everything they've
posted about the tracked topics.

Cross-platform identity is heuristic: platforms don't share ids, so we match on the
normalized display name / handle (lowercased, @ stripped). It surfaces likely-same
accounts; it does not claim certainty. Aggregate only — no private data.
"""
import re

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Post
from ..services import meili

router = APIRouter(prefix="/api/authors", tags=["authors"])


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().lstrip("@"))


@router.get("/top")
def top_authors(topic_id: int | None = None, platform: str = "", limit: int = 40,
                db: Session = Depends(get_db)):
    """Most active authors (entry point for the author explorer)."""
    q = (db.query(Post.author_name, Post.author_handle, Post.platform,
                  func.count(Post.id).label("n"),
                  func.coalesce(func.sum(Post.reach), 0).label("reach"),
                  func.avg(Post.sentiment_score).label("sent"))
         .filter(Post.author_key != "", Post.is_hidden.is_(False)))
    if topic_id is not None:
        q = q.filter(Post.topic_id == topic_id)
    if platform:
        q = q.filter(Post.platform == platform)
    rows = (q.group_by(Post.author_name, Post.author_handle, Post.platform)
            .order_by(func.count(Post.id).desc()).limit(min(limit, 200)).all())
    return [{"author_name": r[0], "author_handle": r[1], "platform": r[2],
             "posts": r[3], "reach": int(r[4] or 0),
             "avg_sentiment": round(float(r[5]), 3) if r[5] is not None else None}
            for r in rows]


@router.get("/profile")
def author_profile(name: str = "", handle: str = "", limit: int = 60,
                   db: Session = Depends(get_db)):
    """Everything a (heuristically matched) author posted, across every platform."""
    targets = {t for t in (_norm(name), _norm(handle)) if t}
    if not targets:
        return {"identity": {"name": name, "handle": handle}, "platforms": [],
                "topics": [], "posts": [], "totals": {}}

    # candidate pool: same normalized name OR handle. Pull a bounded set, then match
    # precisely in Python (handles the @ / spacing / case variants across platforms).
    conds = []
    for t in (name, handle):
        if t:
            like = f"%{t.strip().lstrip('@')}%"
            conds.append(func.lower(Post.author_name).like(func.lower(like)))
            conds.append(func.lower(Post.author_handle).like(func.lower(like)))
    cand = (db.query(Post).filter(or_(*conds), Post.author_key != "")
            .order_by(Post.posted_at.desc().nullslast()).limit(2000).all())
    matched = [p for p in cand
               if _norm(p.author_name) in targets or _norm(p.author_handle) in targets]
    if not matched:
        return {"identity": {"name": name, "handle": handle}, "platforms": [],
                "topics": [], "posts": [], "totals": {}}

    by_platform: dict[str, dict] = {}
    topics: dict[str, int] = {}
    sent = {"pos": 0, "neu": 0, "neg": 0}
    total_reach = 0
    for p in matched:
        pl = by_platform.setdefault(p.platform, {
            "platform": p.platform, "posts": 0, "reach": 0,
            "handles": set(), "verified": False})
        pl["posts"] += 1
        pl["reach"] += int(p.reach or 0)
        if p.author_handle:
            pl["handles"].add(p.author_handle)
        pl["verified"] = pl["verified"] or bool(p.author_verified)
        total_reach += int(p.reach or 0)
        if p.sentiment in sent:
            sent[p.sentiment] += 1
        for t in (p.topics or []):
            topics[t] = topics.get(t, 0) + 1

    platforms = [{**v, "handles": sorted(v["handles"])} for v in by_platform.values()]
    platforms.sort(key=lambda x: -x["posts"])
    top_topics = sorted(topics.items(), key=lambda kv: -kv[1])[:15]
    posts = [meili.doc_from_post(p) for p in matched[:limit]]
    return {
        "identity": {"name": name, "handle": handle,
                     "display": matched[0].author_name or matched[0].author_handle},
        "platforms": platforms,
        "cross_platform": len(platforms) > 1,
        "topics": [{"topic": t, "count": c} for t, c in top_topics],
        "sentiment": sent,
        "totals": {"posts": len(matched), "reach": total_reach,
                   "platforms": len(platforms)},
        "posts": posts,
    }
