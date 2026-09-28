from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Post, SuppressedAuthor
from ..services import meili

router = APIRouter(prefix="/api/suppression", tags=["suppression"])


class SuppressIn(BaseModel):
    platform: str
    author_key: str
    mode: str = "hide"  # hide | watch
    reason: str = ""


@router.get("")
def list_suppressed(db: Session = Depends(get_db)):
    return [{"id": s.id, "platform": s.platform, "author_key": s.author_key,
             "mode": s.mode, "reason": s.reason, "created_at": s.created_at.isoformat()}
            for s in db.query(SuppressedAuthor).order_by(SuppressedAuthor.created_at.desc()).all()]


@router.post("")
def suppress(body: SuppressIn, db: Session = Depends(get_db)):
    if body.mode not in ("hide", "watch"):
        raise HTTPException(400, "mode must be hide|watch")
    existing = (db.query(SuppressedAuthor)
                .filter_by(platform=body.platform, author_key=body.author_key).first())
    if existing:
        existing.mode, existing.reason = body.mode, body.reason
    else:
        db.add(SuppressedAuthor(**body.model_dump()))
    # retroactively flag existing posts (hide mode only)
    hide = body.mode == "hide"
    posts = (db.query(Post).filter(Post.platform == body.platform,
                                   Post.author_key == body.author_key).all())
    docs = []
    for p in posts:
        p.is_hidden = hide
        docs.append({"id": p.id, "is_hidden": hide})
    db.commit()
    if docs:
        meili.index_posts(docs)  # partial update flips visibility in search too
    return {"ok": True, "affected_posts": len(docs)}


@router.delete("/{sup_id}")
def unsuppress(sup_id: int, db: Session = Depends(get_db)):
    s = db.get(SuppressedAuthor, sup_id)
    if not s:
        raise HTTPException(404)
    posts = (db.query(Post).filter(Post.platform == s.platform,
                                   Post.author_key == s.author_key).all())
    docs = []
    for p in posts:
        p.is_hidden = False
        docs.append({"id": p.id, "is_hidden": False})
    db.delete(s)
    db.commit()
    if docs:
        meili.index_posts(docs)
    return {"ok": True, "restored_posts": len(docs)}
