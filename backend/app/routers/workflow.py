"""Analyst workflow: colored tags/labels, saved views (searches), sentiment override.

Mirrors Meltwater's tagging + saved-search + manual-sentiment features. Labels live on
Post.labels (a plain list, indexed in Meili so the feed filters on them); the Tag table
is just the palette (name + color). Saved views store a feed filter set by name.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Post, SavedView, Tag
from ..services import meili

router = APIRouter(prefix="/api", tags=["workflow"])


# ---- tag palette ----
class TagIn(BaseModel):
    name: str
    color: str = "#2a78d6"


@router.get("/tags")
def list_tags(db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name, "color": t.color}
            for t in db.query(Tag).order_by(Tag.name).all()]


@router.post("/tags")
def create_tag(body: TagIn, db: Session = Depends(get_db)):
    name = body.name.strip()[:60]
    if not name:
        raise HTTPException(400, "name required")
    existing = db.query(Tag).filter(Tag.name == name).first()
    if existing:
        existing.color = body.color
        db.commit()
        return {"id": existing.id, "name": existing.name, "color": existing.color}
    t = Tag(name=name, color=body.color[:16])
    db.add(t)
    db.commit()
    return {"id": t.id, "name": t.name, "color": t.color}


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    t = db.get(Tag, tag_id)
    if not t:
        return {"ok": True}
    name = t.name
    db.delete(t)
    # pull the label off every post that carried it, and re-index those
    tagged = db.query(Post).filter(Post.labels.contains([name])).all()
    for p in tagged:
        p.labels = [x for x in (p.labels or []) if x != name]
    db.commit()
    _reindex(tagged)
    return {"ok": True, "untagged": len(tagged)}


# ---- apply labels to posts ----
class TagPostsIn(BaseModel):
    ids: list[int]
    add: list[str] = []
    remove: list[str] = []


@router.post("/posts/tag")
def tag_posts(body: TagPostsIn, db: Session = Depends(get_db)):
    """Add/remove labels on a set of posts (single or bulk)."""
    if not body.ids:
        return {"updated": 0}
    add = [a.strip()[:60] for a in body.add if a.strip()]
    remove = set(body.remove)
    posts = db.query(Post).filter(Post.id.in_(body.ids)).all()
    for p in posts:
        cur = [x for x in (p.labels or []) if x not in remove]
        for a in add:
            if a not in cur:
                cur.append(a)
        p.labels = cur
    db.commit()
    _reindex(posts)
    return {"updated": len(posts)}


# ---- manual sentiment override ----
class SentimentIn(BaseModel):
    sentiment: str          # pos | neu | neg  (empty string unlocks / clears the override)


@router.post("/posts/{post_id}/sentiment")
def override_sentiment(post_id: int, body: SentimentIn, db: Session = Depends(get_db)):
    """Correct the AI's sentiment and lock it so re-enrichment won't clobber it."""
    p = db.get(Post, post_id)
    if not p:
        raise HTTPException(404)
    if body.sentiment == "":
        p.sentiment_locked = False                    # release back to the AI
    elif body.sentiment in ("pos", "neu", "neg"):
        p.sentiment = body.sentiment
        p.sentiment_score = {"pos": 0.6, "neu": 0.0, "neg": -0.6}[body.sentiment]
        p.sentiment_locked = True
    else:
        raise HTTPException(400, "sentiment must be pos|neu|neg (or empty to unlock)")
    db.commit()
    _reindex([p])
    return {"id": p.id, "sentiment": p.sentiment, "locked": p.sentiment_locked}


# ---- saved views (searches) ----
class ViewIn(BaseModel):
    name: str
    params: dict = {}


@router.get("/views")
def list_views(db: Session = Depends(get_db)):
    return [{"id": v.id, "name": v.name, "params": v.params}
            for v in db.query(SavedView).order_by(SavedView.name).all()]


@router.post("/views")
def create_view(body: ViewIn, db: Session = Depends(get_db)):
    name = body.name.strip()[:120]
    if not name:
        raise HTTPException(400, "name required")
    v = SavedView(name=name, params=body.params)
    db.add(v)
    db.commit()
    return {"id": v.id, "name": v.name, "params": v.params}


@router.delete("/views/{view_id}")
def delete_view(view_id: int, db: Session = Depends(get_db)):
    v = db.get(SavedView, view_id)
    if v:
        db.delete(v)
        db.commit()
    return {"ok": True}


def _reindex(posts) -> None:
    try:
        docs = [meili.doc_from_post(p) for p in posts if not p.is_hidden]
        if docs:
            meili.index_posts(docs)
    except Exception:  # noqa: BLE001
        pass
