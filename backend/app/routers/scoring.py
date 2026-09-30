"""Custom impact-scoring config + recompute. Changing the weights re-scores the whole
corpus in place (no AI, no re-crawl) since the score is arithmetic over stored fields."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Post
from ..services import custom_score, meili
from ..services.settings_store import get_setting, set_setting

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("")
def get_config(db: Session = Depends(get_db)):
    return get_setting(db, "scoring")


class ScoringIn(BaseModel):
    value: dict


@router.put("")
def set_config(body: ScoringIn, db: Session = Depends(get_db)):
    cfg = set_setting(db, "scoring", body.value)
    custom_score.invalidate()
    return cfg


@router.post("/recompute")
def recompute(db: Session = Depends(get_db)):
    """Re-score every post with the current weights. Batched + reindexed."""
    custom_score.invalidate()
    cfg = get_setting(db, "scoring")
    updated, batch = 0, []
    last_id = 0
    while True:
        posts = (db.query(Post).filter(Post.id > last_id)
                 .order_by(Post.id).limit(1000).all())
        if not posts:
            break
        for p in posts:
            last_id = p.id
            e = p.engagement or {}
            eng = sum(v for v in [e.get("likes", 0), e.get("comments", 0), e.get("shares", 0)]
                      if isinstance(v, (int, float)))
            p.custom_score = custom_score.compute(
                cfg, platform=p.platform, reach=p.reach, engagement_total=eng,
                relevance=p.relevance, sentiment=p.sentiment,
                verified=p.author_verified, text=f"{p.title} {p.text}")
            updated += 1
            if not p.is_hidden:
                batch.append(meili.doc_from_post(p))
        db.commit()
        if batch:
            try:
                meili.index_posts(batch)
            except Exception:  # noqa: BLE001
                pass
            batch = []
    return {"recomputed": updated}
